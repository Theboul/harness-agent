"""Versioned SQLite schema of the session store (HU-03-01 / T003)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.storage._schema import SCHEMA_VERSION, ensure_schema
from harness_agent.adapters.storage.errors import SchemaVersionError


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    yield connection
    connection.close()


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def user_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def insert_session(conn: sqlite3.Connection, session_id: str, status: str = "active") -> None:
    conn.execute(
        "INSERT INTO sessions (id, created_at, status) VALUES (?, ?, ?)",
        (session_id, "2026-10-23T10:00:00+00:00", status),
    )


def insert_event(conn: sqlite3.Connection, event_id: str, session_id: str, seq: int) -> None:
    conn.execute(
        "INSERT INTO events (id, session_id, seq, type, content, created_at) "
        "VALUES (?, ?, ?, 'user_message', '{}', '2026-10-23T10:00:00+00:00')",
        (event_id, session_id, seq),
    )


def test_schema_version_is_current() -> None:
    assert SCHEMA_VERSION == 4


def test_new_database_gets_both_tables_with_the_documented_columns(
    conn: sqlite3.Connection,
) -> None:
    ensure_schema(conn)

    assert columns(conn, "sessions") == [
        "id",
        "parent_id",
        "created_at",
        "model",
        "goal",
        "status",
    ]
    assert columns(conn, "events") == [
        "id",
        "session_id",
        "seq",
        "type",
        "content",
        "created_at",
        "compacted_by",
    ]
    assert user_version(conn) == SCHEMA_VERSION


def test_ensure_schema_is_idempotent_and_keeps_data(conn: sqlite3.Connection) -> None:
    ensure_schema(conn)
    insert_session(conn, "s1")
    conn.commit()

    ensure_schema(conn)

    assert conn.execute("SELECT id FROM sessions").fetchall() == [("s1",)]
    assert user_version(conn) == SCHEMA_VERSION


def test_newer_schema_version_is_refused_without_touching_the_database(tmp_path: Path) -> None:
    db = tmp_path / "future.db"
    setup = sqlite3.connect(db)
    setup.execute("CREATE TABLE marker (x INTEGER)")
    setup.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    setup.commit()
    setup.close()
    before = db.read_bytes()

    conn = sqlite3.connect(db)
    try:
        with pytest.raises(SchemaVersionError):
            ensure_schema(conn)
    finally:
        conn.close()

    assert db.read_bytes() == before


def test_foreign_database_without_version_is_refused(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE unrelated (x INTEGER)")

    with pytest.raises(SchemaVersionError):
        ensure_schema(conn)

    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    assert names == {"unrelated"}


def test_failed_creation_rolls_back_and_leaves_no_tables(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA query_only = ON")

    with pytest.raises(sqlite3.OperationalError):
        ensure_schema(conn)

    assert not conn.in_transaction
    assert conn.execute("SELECT 1 FROM sqlite_master").fetchone() is None


def test_status_outside_the_catalog_is_rejected(conn: sqlite3.Connection) -> None:
    ensure_schema(conn)

    with pytest.raises(sqlite3.IntegrityError):
        insert_session(conn, "s1", status="deleted")


@pytest.mark.parametrize("status", ["active", "completed", "interrupted"])
def test_status_inside_the_catalog_is_accepted(conn: sqlite3.Connection, status: str) -> None:
    ensure_schema(conn)

    insert_session(conn, "s1", status=status)


def test_session_id_is_unique(conn: sqlite3.Connection) -> None:
    ensure_schema(conn)
    insert_session(conn, "s1")

    with pytest.raises(sqlite3.IntegrityError):
        insert_session(conn, "s1")


def test_parent_must_exist(conn: sqlite3.Connection) -> None:
    ensure_schema(conn)

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO sessions (id, parent_id, created_at, status) "
            "VALUES ('child', 'missing', '2026-10-23T10:00:00+00:00', 'active')"
        )


def test_event_requires_an_existing_session(conn: sqlite3.Connection) -> None:
    ensure_schema(conn)

    with pytest.raises(sqlite3.IntegrityError):
        insert_event(conn, "e1", "missing", 1)


def test_event_order_is_unique_per_session(conn: sqlite3.Connection) -> None:
    ensure_schema(conn)
    insert_session(conn, "s1")
    insert_session(conn, "s2")
    insert_event(conn, "e1", "s1", 1)

    insert_event(conn, "e2", "s2", 1)
    with pytest.raises(sqlite3.IntegrityError):
        insert_event(conn, "e3", "s1", 1)
