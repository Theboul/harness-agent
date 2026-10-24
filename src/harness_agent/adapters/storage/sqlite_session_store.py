"""SQLite session store: schema bootstrap, sessions and events (HU-03-01, HU-03-02).

This adapter owns the ``sessions`` and ``events`` tables and implements the ``SessionStore``
port: every event is saved in its own durable transaction (``save_event``) and read back in
saving order (``load_session``). Creating a session is an adapter operation because the port has
no ``create_session``; a session must exist before its first event.
"""

from __future__ import annotations

import json
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
    DuplicateEvent,
    EventSerializationError,
    ParentSessionNotFound,
    SchemaVersionError,
    SessionNotFound,
    SessionStoreError,
)
from harness_agent.core import Event, EventType, SessionStore, SessionSummary

_IN_MEMORY = ":memory:"
_ENGINE_ERROR = "Error del almacén de sesiones."
_OPEN_ERROR = "No se pudo abrir el almacén de sesiones."
_CLOSED_ERROR = "El almacén de sesiones está cerrado."
_PARENT_ERROR = "La sesión padre indicada no existe."
_SESSION_ERROR = "La sesión indicada no existe."
_DUPLICATE_ERROR = "Ya existe un evento con ese identificador."
_SERIALIZATION_ERROR = "El contenido del evento no se puede guardar como JSON."
_CORRUPT_ERROR = "Un evento guardado está dañado y no se puede leer."
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


def _serialize_payload(payload: dict[str, object]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise EventSerializationError(_SERIALIZATION_ERROR) from None


def _event_from_row(row: tuple[str, str, str, str, str]) -> Event:
    try:
        payload = json.loads(row[3])
        if not isinstance(payload, dict):
            raise ValueError
        return Event(
            id=row[0],
            session_id=row[1],
            type=EventType(row[2]),
            timestamp=datetime.fromisoformat(row[4]),
            payload=payload,
        )
    except ValueError:
        raise SessionStoreError(_CORRUPT_ERROR) from None


class SqliteSessionStore(SessionStore):
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
            conn.execute("PRAGMA synchronous = FULL")
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

    def save_event(self, event: Event) -> None:
        """Save one event in its own durable transaction.

        The event gets the next order number of its session; either the whole write is
        committed or nothing is.

        Raises:
            EventSerializationError: The payload cannot be represented as JSON.
            SessionNotFound: The event's session does not exist.
            DuplicateEvent: An event with the same identifier is already saved.
            SessionStoreError: The store is closed or the engine failed.
        """
        conn = self._connection()
        content = _serialize_payload(event.payload)
        try:
            conn.execute("BEGIN IMMEDIATE")
            if (
                conn.execute("SELECT 1 FROM sessions WHERE id = ?", (event.session_id,)).fetchone()
                is None
            ):
                raise SessionNotFound(_SESSION_ERROR)
            if (
                conn.execute("SELECT 1 FROM events WHERE id = ?", (event.id,)).fetchone()
                is not None
            ):
                raise DuplicateEvent(_DUPLICATE_ERROR)
            seq = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id = ?",
                (event.session_id,),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO events (id, session_id, seq, type, content, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event.id,
                    event.session_id,
                    seq,
                    event.type.value,
                    content,
                    _to_utc(event.timestamp).isoformat(),
                ),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise SessionStoreError(_ENGINE_ERROR) from None
        except BaseException:
            conn.rollback()
            raise

    def load_session(self, session_id: str) -> list[Event]:
        """Return the events of a session in saving order (empty if there are none).

        Raises:
            SessionStoreError: The store is closed, the engine failed or a stored event is
                damaged.
        """
        conn = self._connection()
        try:
            rows = conn.execute(
                "SELECT id, session_id, type, content, created_at FROM events "
                "WHERE session_id = ? ORDER BY seq",
                (session_id,),
            ).fetchall()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        return [_event_from_row(row) for row in rows]

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
