"""Public API of ``harness_agent.adapters.storage`` (HU-03-01 / T010, HU-03-02 / T010)."""

from __future__ import annotations

import harness_agent.adapters.storage as storage

EXPECTED = {
    "EXPORT_FILE_NAME",
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
    "SqliteCompactionArchive",
    "SqliteEssentialStore",
    "SqliteMessageStore",
    "SqliteSessionStore",
    "SqliteTaskStore",
    "StartedTask",
    "StoredSession",
    "attach_event_recorder",
}


def test_all_lists_exactly_the_public_names() -> None:
    assert set(storage.__all__) == EXPECTED


def test_every_public_name_is_importable_from_the_package() -> None:
    for name in EXPECTED:
        assert hasattr(storage, name), name
