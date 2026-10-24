"""SqliteSessionStore: opening, closing and session creation (HU-03-01 / T004 onwards)."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NoReturn

import pytest

from harness_agent.adapters.storage._schema import SCHEMA_VERSION
from harness_agent.adapters.storage.errors import (
    ParentSessionNotFound,
    SchemaVersionError,
    SessionStoreError,
)
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore, StoredSession
from harness_agent.core import SessionSummary

FIXED_NOW = datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"


class Ids:
    """Deterministic identifier factory: ``id-1``, ``id-2``..."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self) -> str:
        self.count += 1
        return f"id-{self.count}"


def make_store(
    path: str | Path = ":memory:",
    *,
    now: datetime = FIXED_NOW,
) -> SqliteSessionStore:
    return SqliteSessionStore(path, clock=lambda: now, id_factory=Ids())


def table_names(db: Path) -> set[str]:
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


# --- T004: opening and closing -------------------------------------------------------------------


def test_opening_creates_missing_directories_and_the_schema(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "deeper" / "sessions.db"

    SqliteSessionStore(db).close()

    assert {"sessions", "events"} <= table_names(db)


def test_accepts_a_string_path(tmp_path: Path) -> None:
    db = tmp_path / "sessions.db"

    SqliteSessionStore(str(db)).close()

    assert db.exists()


def test_reopening_the_same_file_is_harmless(tmp_path: Path) -> None:
    db = tmp_path / "sessions.db"
    SqliteSessionStore(db).close()

    SqliteSessionStore(db).close()

    assert {"sessions", "events"} <= table_names(db)


def test_in_memory_database_works() -> None:
    with SqliteSessionStore(":memory:"):
        pass


def test_close_is_idempotent() -> None:
    store = SqliteSessionStore(":memory:")

    store.close()
    store.close()


def test_store_is_a_context_manager_that_closes_on_exit() -> None:
    with SqliteSessionStore(":memory:") as store:
        assert isinstance(store, SqliteSessionStore)

    with pytest.raises(SessionStoreError):
        store.list_sessions()


def test_a_file_that_is_not_a_database_is_a_domain_error_without_the_path(
    tmp_path: Path,
) -> None:
    db = tmp_path / f"folder-{SENTINEL}.db"
    db.write_bytes(b"this is not a sqlite database" * 50)

    with pytest.raises(SessionStoreError) as excinfo:
        SqliteSessionStore(db)

    assert SENTINEL not in str(excinfo.value)


def test_a_directory_that_cannot_be_created_is_a_domain_error(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory", encoding="utf-8")

    with pytest.raises(SessionStoreError):
        SqliteSessionStore(blocker / "sessions.db")


# --- T005: create_session and get_session --------------------------------------------------------


def test_create_session_returns_an_active_session_with_id_and_utc_timestamp() -> None:
    with make_store() as store:
        session = store.create_session()

    assert session == StoredSession(
        id="id-1",
        status="active",
        created_at=FIXED_NOW,
        model=None,
        goal=None,
        parent_id=None,
    )


def test_create_session_keeps_model_and_goal() -> None:
    with make_store() as store:
        session = store.create_session(model="fake/test", goal="Arreglar el ticket 42")

    assert session.model == "fake/test"
    assert session.goal == "Arreglar el ticket 42"


def test_get_session_returns_what_was_created() -> None:
    with make_store() as store:
        created = store.create_session(model="m", goal="g")

        assert store.get_session(created.id) == created


def test_get_session_of_an_unknown_id_is_none() -> None:
    with make_store() as store:
        assert store.get_session("missing") is None


def test_stored_session_is_immutable() -> None:
    with make_store() as store:
        session = store.create_session()

    with pytest.raises(FrozenInstanceError):
        session.status = "completed"  # type: ignore[misc]


def test_naive_clock_value_is_taken_as_utc() -> None:
    naive = datetime(2026, 10, 23, 10, 30)
    with make_store(now=naive) as store:
        session = store.create_session()

    assert session.created_at == FIXED_NOW
    assert session.created_at.tzinfo is not None


def test_aware_clock_value_is_converted_to_utc() -> None:
    plus_two = datetime(2026, 10, 23, 12, 30, tzinfo=timezone(timedelta(hours=2)))
    with make_store(now=plus_two) as store:
        created = store.create_session()
        read = store.get_session(created.id)

    assert created.created_at == FIXED_NOW
    assert read is not None
    assert read.created_at == FIXED_NOW
    assert read.created_at.utcoffset() == timedelta(0)


def test_default_ids_are_unique_and_the_default_clock_is_utc() -> None:
    with SqliteSessionStore(":memory:") as store:
        first = store.create_session()
        second = store.create_session()

    assert first.id
    assert first.id != second.id
    assert first.created_at.utcoffset() == timedelta(0)


def test_special_characters_are_stored_and_read_unchanged() -> None:
    goal = '\'; DROP TABLE sessions; --  ñandú ☃ "comillas"'
    with make_store() as store:
        created = store.create_session(model="a'b", goal=goal)

        read = store.get_session(created.id)
        assert read is not None
        assert read.goal == goal
        assert read.model == "a'b"
        assert len(store.list_sessions()) == 1


# --- T006: list_sessions and persistence ---------------------------------------------------------


def test_list_sessions_is_empty_on_a_new_database() -> None:
    with make_store() as store:
        assert store.list_sessions() == []


def test_list_sessions_returns_summaries_in_creation_order() -> None:
    times = iter([FIXED_NOW + timedelta(seconds=n) for n in (0, 1, 2)])
    with SqliteSessionStore(":memory:", clock=lambda: next(times), id_factory=Ids()) as store:
        store.create_session(model="m1", goal="g1")
        store.create_session()
        store.create_session(model="m3")

        summaries = store.list_sessions()

    assert [s.id for s in summaries] == ["id-1", "id-2", "id-3"]
    assert all(isinstance(s, SessionSummary) for s in summaries)
    assert summaries[0] == SessionSummary(
        id="id-1", status="active", created_at=FIXED_NOW, model="m1", goal="g1"
    )
    assert summaries[1].model is None


def test_list_sessions_order_is_stable_with_equal_timestamps() -> None:
    with make_store() as store:
        for _ in range(5):
            store.create_session()

        assert [s.id for s in store.list_sessions()] == [f"id-{n}" for n in range(1, 6)]


def test_sessions_survive_closing_and_reopening_the_file(tmp_path: Path) -> None:
    db = tmp_path / "sessions.db"
    with make_store(db) as store:
        created = store.create_session(model="m", goal="g")

    with make_store(db) as reopened:
        assert reopened.get_session(created.id) == created
        assert [s.id for s in reopened.list_sessions()] == [created.id]


def test_one_hundred_sessions_have_distinct_ids_and_are_fast(tmp_path: Path) -> None:
    with SqliteSessionStore(tmp_path / "sessions.db") as store:
        durations: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            store.create_session()
            durations.append(time.perf_counter() - start)

        sessions = store.list_sessions()

    assert len({s.id for s in sessions}) == 100
    assert all(s.status == "active" for s in sessions)
    assert sorted(durations)[len(durations) // 2] < 0.1


# --- T007: parent sessions -----------------------------------------------------------------------


def test_child_session_keeps_the_parent_id() -> None:
    with make_store() as store:
        parent = store.create_session()
        child = store.create_session(parent_id=parent.id)

        assert child.parent_id == parent.id
        assert store.get_session(child.id) == child
        assert parent.parent_id is None


def test_missing_parent_is_rejected_and_nothing_is_created() -> None:
    with make_store() as store:
        with pytest.raises(ParentSessionNotFound) as excinfo:
            store.create_session(parent_id=SENTINEL)

        assert SENTINEL not in str(excinfo.value)
        assert store.list_sessions() == []


def test_three_level_chain_is_read_back() -> None:
    with make_store() as store:
        root = store.create_session()
        middle = store.create_session(parent_id=root.id)
        leaf = store.create_session(parent_id=middle.id)

        read_leaf = store.get_session(leaf.id)
        read_middle = store.get_session(middle.id)

    assert read_leaf is not None
    assert read_leaf.parent_id == middle.id
    assert read_middle is not None
    assert read_middle.parent_id == root.id


# --- T008: engine errors, closed store, future schema --------------------------------------------


def test_every_operation_on_a_closed_store_is_a_domain_error() -> None:
    store = make_store()
    store.close()

    with pytest.raises(SessionStoreError):
        store.create_session()
    with pytest.raises(SessionStoreError):
        store.get_session("x")
    with pytest.raises(SessionStoreError):
        store.list_sessions()


class BrokenConnection:
    """Stand-in whose every statement fails like a damaged database would."""

    def execute(self, *args: object, **kwargs: object) -> NoReturn:
        raise sqlite3.OperationalError(f"disk I/O error {SENTINEL}")

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None


def break_connection(store: SqliteSessionStore) -> None:
    store._conn = BrokenConnection()  # type: ignore[assignment]


@pytest.mark.parametrize(
    "operation",
    [
        lambda s: s.create_session(model=SENTINEL, goal=SENTINEL),
        lambda s: s.create_session(parent_id=SENTINEL),
        lambda s: s.get_session(SENTINEL),
        lambda s: s.list_sessions(),
    ],
    ids=["create_session", "create_child_session", "get_session", "list_sessions"],
)
def test_engine_errors_become_domain_errors_without_the_input(
    operation: Callable[[SqliteSessionStore], object],
) -> None:
    store = make_store()
    break_connection(store)

    with pytest.raises(SessionStoreError) as excinfo:
        operation(store)

    assert SENTINEL not in str(excinfo.value)
    assert excinfo.value.__cause__ is None


def test_a_future_schema_version_is_refused_and_the_file_is_untouched(tmp_path: Path) -> None:
    db = tmp_path / "future.db"
    setup = sqlite3.connect(db)
    setup.execute("CREATE TABLE marker (x INTEGER)")
    setup.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    setup.commit()
    setup.close()
    before = db.read_bytes()

    with pytest.raises(SchemaVersionError):
        SqliteSessionStore(db)

    assert db.read_bytes() == before
