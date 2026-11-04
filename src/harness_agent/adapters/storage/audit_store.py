"""SQLite store of the audit of the decisions (HU-05-05).

Implements the small ``AuditLog`` protocol of the core on the connection of the session store
(never one of its own). The ``auditoria`` table has no foreign key and no ``CHECK``: the rows are
evidence and nothing that happens to a session may stop them or erase them. What arrives is already
redacted and shortened by the core; this adapter only writes and reads rows. Messages of the engine
never carry a name, an argument or a path.

A failure of the engine is **not** swallowed here: it rises as ``SessionStoreError`` and the core
lets it reach the bus, so a decision that cannot be recorded stops the tool (the audit fails
closed).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from harness_agent.adapters.storage.errors import SessionStoreError
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore
from harness_agent.core import AuditEntry, AuditRow

_ENGINE_ERROR = "Error del almacén de la auditoría."
_DAMAGED = "Un registro de la auditoría está dañado y no se puede leer."

# The latest ``limit`` rows of the session and of its direct children (one level: subagents).
_SCOPE = (
    "(a.sesion_id = :session OR "
    "a.sesion_id IN (SELECT id FROM sessions WHERE parent_id = :session))"
)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SqliteAuditStore:
    """Keeps the audit rows of the decisions, in the order they were recorded.

    Args:
        store: The session store whose connection and tables are used.
    """

    def __init__(self, store: SqliteSessionStore) -> None:
        self._store = store

    def record_decision(self, entry: AuditEntry) -> None:
        """Write one row.

        Raises:
            SessionStoreError: The store is closed or the engine failed; nothing was written.
        """
        conn = self._store.connection()
        try:
            conn.execute(
                "INSERT INTO auditoria (sesion_id, llamada_id, herramienta, argumentos, decision, "
                "resolucion, razon, origen, decidida) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.session_id,
                    entry.call_id,
                    entry.tool,
                    entry.arguments,
                    entry.decision,
                    entry.resolution,
                    entry.reason,
                    entry.origin,
                    _to_utc(entry.decided_at).isoformat(),
                ),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise SessionStoreError(_ENGINE_ERROR) from None

    def record_resolution(
        self,
        session_id: str,
        call_id: str,
        resolution: str,
        action: str | None,
        source: str | None,
        resolved_at: datetime,
    ) -> None:
        """Complete the latest row of that session and call; without one nothing happens.

        Raises:
            SessionStoreError: The store is closed or the engine failed; nothing was changed.
        """
        conn = self._store.connection()
        try:
            conn.execute(
                "UPDATE auditoria SET resolucion = ?, accion = ?, fuente = ?, resuelta = ? "
                "WHERE id = (SELECT MAX(id) FROM auditoria WHERE sesion_id = ? AND llamada_id = ?)",
                (
                    resolution,
                    action,
                    source,
                    _to_utc(resolved_at).isoformat(),
                    session_id,
                    call_id,
                ),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise SessionStoreError(_ENGINE_ERROR) from None

    def rows(self, session_id: str, limit: int) -> list[AuditRow]:
        """The latest ``limit`` rows of the session and of its direct children, oldest first.

        Raises:
            SessionStoreError: The store is closed, the engine failed or a stored instant is
                unreadable.
        """
        conn = self._store.connection()
        try:
            found = conn.execute(
                "SELECT a.sesion_id, s.parent_id, a.llamada_id, a.herramienta, a.argumentos, "
                "a.decision, a.resolucion, a.razon, a.accion, a.fuente, a.origen, a.decidida, "
                "a.resuelta FROM auditoria a LEFT JOIN sessions s ON s.id = a.sesion_id "
                f"WHERE {_SCOPE} ORDER BY a.id DESC LIMIT :limit",
                {"session": session_id, "limit": max(0, limit)},
            ).fetchall()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        try:
            return [
                AuditRow(
                    session_id=row[0],
                    parent_id=row[1],
                    call_id=row[2],
                    tool=row[3],
                    arguments=row[4],
                    decision=row[5],
                    resolution=row[6],
                    reason=row[7],
                    action=row[8],
                    source=row[9],
                    origin=row[10],
                    decided_at=_to_utc(datetime.fromisoformat(row[11])),
                    resolved_at=None
                    if row[12] is None
                    else _to_utc(datetime.fromisoformat(row[12])),
                )
                for row in reversed(found)
            ]
        except ValueError:
            raise SessionStoreError(_DAMAGED) from None

    def count(self, session_id: str) -> int:
        """How many rows ``rows`` could return for the session (no limit)."""
        conn = self._store.connection()
        try:
            row = conn.execute(
                f"SELECT COUNT(*) FROM auditoria a WHERE {_SCOPE}", {"session": session_id}
            ).fetchone()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        return int(row[0])
