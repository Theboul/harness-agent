"""SQLite storage adapters: sessions, events, criteria, compaction, essential context, messages,
the audit of the decisions and the traces of the calls."""

from harness_agent.adapters.storage._schema import SCHEMA_VERSION
from harness_agent.adapters.storage.audit_store import SqliteAuditStore
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
from harness_agent.adapters.storage.memory_store import SqliteMemoryStore
from harness_agent.adapters.storage.message_store import SqliteMessageStore
from harness_agent.adapters.storage.progress_file import ProgressFile
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore, StoredSession
from harness_agent.adapters.storage.task_store import SqliteTaskStore, StartedTask
from harness_agent.adapters.storage.trace_store import SqliteTraceStore

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
    "SqliteAuditStore",
    "SqliteCompactionArchive",
    "SqliteEssentialStore",
    "SqliteMemoryStore",
    "SqliteMessageStore",
    "SqliteSessionStore",
    "SqliteTaskStore",
    "SqliteTraceStore",
    "StartedTask",
    "StoredSession",
    "attach_event_recorder",
]
