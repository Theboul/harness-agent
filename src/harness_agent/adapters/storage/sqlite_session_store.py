"""SQLite session store: schema bootstrap and session creation (HU-03-01).

This adapter owns the ``sessions`` and ``events`` tables. It does not subclass the
``SessionStore`` port yet: persisting and loading events (``save_event`` / ``load_session``)
arrives with HU-03-02. Creating a session is an adapter operation because the port has no
``create_session``.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Self

from harness_agent.adapters.storage._schema import ensure_schema
from harness_agent.adapters.storage.errors import (
    ParentSessionNotFound,
    SchemaVersionError,
    SessionStoreError,
)
from harness_agent.core import SessionSummary

_IN_MEMORY = ":memory:"
_ENGINE_ERROR = "Error del almacén de sesiones."
_OPEN_ERROR = "No se pudo abrir el almacén de sesiones."
_CLOSED_ERROR = "El almacén de sesiones está cerrado."
_PARENT_ERROR = "La sesión padre indicada no existe."
_ACTIVE = "active"

_SESSION_COLUMNS = "id, status, created_at, model, goal, parent_id"


@dataclass(frozen=True)
class StoredSession:
    """A session as stored, including its parent link (subagent sessions).

    Attributes:
        id: Unique session identifier.
        status: Lifecycle state (``active``, ``completed`` or ``interrupted``).
        created_at: UTC timestamp of creation.
        model: Optional model identifier.
        goal: Optional goal or task statement.
        parent_id: Identifier of the parent session, or ``None`` for a top-level session.
    """

    id: str
    status: str
    created_at: datetime
    model: str | None = None
    goal: str | None = None
    parent_id: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _to_utc(value: datetime) -> datetime:
    """Naive values are taken as UTC; aware values are converted to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _stored_session(row: tuple[str, str, str, str | None, str | None, str | None]) -> StoredSession:
    return StoredSession(
        id=row[0],
        status=row[1],
        created_at=datetime.fromisoformat(row[2]),
        model=row[3],
        goal=row[4],
        parent_id=row[5],
    )


class SqliteSessionStore:
    """Sessions and event tables on a SQLite file (or ``:memory:``).

    Args:
        path: Database file; missing parent directories are created. ``":memory:"`` is valid.
        clock: Returns the current time; naive values are taken as UTC.
        id_factory: Returns a new unique session identifier.

    Raises:
        SchemaVersionError: The database was written with an unknown schema version.
        SessionStoreError: The database could not be opened.
    """

    def __init__(
        self,
        path: str | os.PathLike[str],
        *,
        clock: Callable[[], datetime] = _utc_now,
        id_factory: Callable[[], str] = _new_id,
    ) -> None:
        self._clock = clock
        self._id_factory = id_factory
        self._conn: sqlite3.Connection | None = None
        location = os.fspath(path)
        try:
            if location != _IN_MEMORY:
                Path(location).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(location)
        except (OSError, sqlite3.Error):
            raise SessionStoreError(_OPEN_ERROR) from None
        try:
            ensure_schema(conn)
        except SchemaVersionError:
            conn.close()
            raise
        except sqlite3.Error:
            conn.close()
            raise SessionStoreError(_OPEN_ERROR) from None
        self._conn = conn

    def create_session(
        self,
        *,
        model: str | None = None,
        goal: str | None = None,
        parent_id: str | None = None,
    ) -> StoredSession:
        """Create an ``active`` session and return it.

        Raises:
            ParentSessionNotFound: ``parent_id`` is given but no such session exists.
            SessionStoreError: The store is closed or the engine failed.
        """
        conn = self._connection()
        session = StoredSession(
            id=self._id_factory(),
            status=_ACTIVE,
            created_at=_to_utc(self._clock()),
            model=model,
            goal=goal,
            parent_id=parent_id,
        )
        try:
            if parent_id is not None:
                found = conn.execute("SELECT 1 FROM sessions WHERE id = ?", (parent_id,))
                if found.fetchone() is None:
                    raise ParentSessionNotFound(_PARENT_ERROR)
            conn.execute(
                f"INSERT INTO sessions ({_SESSION_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    session.id,
                    session.status,
                    session.created_at.isoformat(),
                    session.model,
                    session.goal,
                    session.parent_id,
                ),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise SessionStoreError(_ENGINE_ERROR) from None
        return session

    def get_session(self, session_id: str) -> StoredSession | None:
        """Return the session with that identifier, or ``None`` if it does not exist."""
        conn = self._connection()
        try:
            row = conn.execute(
                f"SELECT {_SESSION_COLUMNS} FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        return None if row is None else _stored_session(row)

    def list_sessions(self) -> list[SessionSummary]:
        """Return every session, oldest first."""
        conn = self._connection()
        try:
            rows = conn.execute(
                f"SELECT {_SESSION_COLUMNS} FROM sessions ORDER BY created_at, rowid"
            ).fetchall()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        summaries: list[SessionSummary] = []
        for row in rows:
            stored = _stored_session(row)
            summaries.append(
                SessionSummary(
                    id=stored.id,
                    status=stored.status,
                    created_at=stored.created_at,
                    model=stored.model,
                    goal=stored.goal,
                )
            )
        return summaries

    def close(self) -> None:
        """Close the connection. Safe to call more than once."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise SessionStoreError(_CLOSED_ERROR)
        return self._conn
