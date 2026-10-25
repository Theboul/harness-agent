"""SQLite storage adapters: sessions, persisted events and task criteria (HU-03-01 to HU-11-01)."""

from harness_agent.adapters.storage._schema import SCHEMA_VERSION
from harness_agent.adapters.storage.errors import (
    CriteriaIntegrityError,
    CriteriaNotFound,
    DuplicateEvent,
    EventSerializationError,
    ExportError,
    ParentSessionNotFound,
    SchemaVersionError,
    SessionNotFound,
    SessionStoreError,
)
from harness_agent.adapters.storage.event_recorder import attach_event_recorder
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore, StoredSession
from harness_agent.adapters.storage.task_store import SqliteTaskStore, StartedTask

__all__ = [
    "SCHEMA_VERSION",
    "CriteriaIntegrityError",
    "CriteriaNotFound",
    "DuplicateEvent",
    "EventSerializationError",
    "ExportError",
    "ParentSessionNotFound",
    "SchemaVersionError",
    "SessionNotFound",
    "SessionStoreError",
    "SqliteSessionStore",
    "SqliteTaskStore",
    "StartedTask",
    "StoredSession",
    "attach_event_recorder",
]
