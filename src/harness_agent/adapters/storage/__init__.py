"""SQLite storage adapters: sessions, events, criteria, compaction, essential context, messages."""

from harness_agent.adapters.storage._schema import SCHEMA_VERSION
from harness_agent.adapters.storage.compaction_archive import SqliteCompactionArchive
from harness_agent.adapters.storage.criteria_export import EXPORT_FILE_NAME
from harness_agent.adapters.storage.errors import (
    CriteriaIntegrityError,
    CriteriaNotFound,
    DuplicateEvent,
    EventSerializationError,
    ExportError,
    ParentSessionNotFound,
    ProgressWriteError,
    SchemaVersionError,
    SessionNotFound,
    SessionStoreError,
)
from harness_agent.adapters.storage.essential_store import SqliteEssentialStore
from harness_agent.adapters.storage.event_recorder import attach_event_recorder
from harness_agent.adapters.storage.message_store import SqliteMessageStore
from harness_agent.adapters.storage.progress_file import ProgressFile
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore, StoredSession
from harness_agent.adapters.storage.task_store import SqliteTaskStore, StartedTask

__all__ = [
    "EXPORT_FILE_NAME",
    "SCHEMA_VERSION",
    "CriteriaIntegrityError",
    "CriteriaNotFound",
    "DuplicateEvent",
    "EventSerializationError",
    "ExportError",
    "ParentSessionNotFound",
    "ProgressFile",
    "ProgressWriteError",
    "SchemaVersionError",
    "SessionNotFound",
    "SessionStoreError",
    "SqliteCompactionArchive",
    "SqliteEssentialStore",
    "SqliteMessageStore",
    "SqliteSessionStore",
    "SqliteTaskStore",
    "StartedTask",
    "StoredSession",
    "attach_event_recorder",
]
