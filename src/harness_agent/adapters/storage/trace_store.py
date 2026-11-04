"""SQLite store of the traces of the calls (HU-10-01).

Implements the small ``TraceLog`` protocol of the core on the connection of the session store (never
one of its own). The ``trazas`` table has no foreign key and no ``CHECK``: a trace never stops a
session, and a session never takes its traces with it. A null token count means the provider gave no
usage; it is kept as null, never turned into a zero. Messages of the engine never carry a name or a
path.

The core catches every failure of this store (a trace never changes a call), so here a failure only
has to be a fixed ``SessionStoreError``.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from harness_agent.adapters.storage.errors import SessionStoreError
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore
from harness_agent.core import TraceRecord, TraceRow

_ENGINE_ERROR = "Error del almacén de las trazas."
_DAMAGED = "Una traza guardada está dañada y no se puede leer."

# The latest ``limit`` traces of the session and of its direct children (one level: subagents).
_SCOPE = (
    "(t.sesion_id = :session OR "
    "t.sesion_id IN (SELECT id FROM sessions WHERE parent_id = :session))"
)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SqliteTraceStore:
    """Keeps the traces of the calls, in the order they were recorded.

    Args:
        store: The session store whose connection and tables are used.
    """

    def __init__(self, store: SqliteSessionStore) -> None:
        self._store = store

    def record(self, record: TraceRecord) -> None:
        """Write one trace.

        Raises:
            SessionStoreError: The store is closed or the engine failed; nothing was written.
        """
        conn = self._store.connection()
        try:
            conn.execute(
                "INSERT INTO trazas (sesion_id, tipo, nombre, inicio, duracion_ms, tokens_entrada, "
                "tokens_salida, resultado, tamano) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.session_id,
                    record.kind,
                    record.name,
                    _to_utc(record.started_at).isoformat(),
                    record.duration_ms,
                    record.input_tokens,
                    record.output_tokens,
                    record.result,
                    record.size,
                ),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise SessionStoreError(_ENGINE_ERROR) from None

    def rows(self, session_id: str, limit: int) -> list[TraceRow]:
        """The latest ``limit`` traces of the session and of its direct children, oldest first.

        Raises:
            SessionStoreError: The store is closed, the engine failed or a stored instant is
                unreadable.
        """
        conn = self._store.connection()
        try:
            found = conn.execute(
                "SELECT t.sesion_id, s.parent_id, t.tipo, t.nombre, t.inicio, t.duracion_ms, "
                "t.tokens_entrada, t.tokens_salida, t.resultado, t.tamano "
                "FROM trazas t LEFT JOIN sessions s ON s.id = t.sesion_id "
                f"WHERE {_SCOPE} ORDER BY t.id DESC LIMIT :limit",
                {"session": session_id, "limit": max(0, limit)},
            ).fetchall()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        try:
            return [
                TraceRow(
                    session_id=row[0],
                    parent_id=row[1],
                    kind=row[2],
                    name=row[3],
                    started_at=_to_utc(datetime.fromisoformat(row[4])),
                    duration_ms=row[5],
                    input_tokens=row[6],
                    output_tokens=row[7],
                    result=row[8],
                    size=row[9],
                )
                for row in reversed(found)
            ]
        except ValueError:
            raise SessionStoreError(_DAMAGED) from None

    def count(self, session_id: str) -> int:
        """How many traces ``rows`` could return for the session (no limit)."""
        conn = self._store.connection()
        try:
            row = conn.execute(
                f"SELECT COUNT(*) FROM trazas t WHERE {_SCOPE}", {"session": session_id}
            ).fetchone()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        return int(row[0])
