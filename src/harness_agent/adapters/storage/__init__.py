"""SQLite storage adapters: sessions (HU-03-01) and persisted events (HU-03-02)."""

from harness_agent.adapters.storage._schema import SCHEMA_VERSION
from harness_agent.adapters.storage.errors import (
    DuplicateEvent,
    EventSerializationError,
    ParentSessionNotFound,
    SchemaVersionError,
    SessionNotFound,
    SessionStoreError,
)
from harness_agent.adapters.storage.event_recorder import attach_event_recorder
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore, StoredSession

__all__ = [
    "SCHEMA_VERSION",
    "DuplicateEvent",
    "EventSerializationError",
    "ParentSessionNotFound",
    "SchemaVersionError",
    "SessionNotFound",
    "SessionStoreError",
    "SqliteSessionStore",
    "StoredSession",
    "attach_event_recorder",
]
