"""SqliteSessionStore: save_event and load_session (HU-03-02 / T003, T004)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, NoReturn

import pytest

from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.adapters.storage.errors import (
    DuplicateEvent,
    EventSerializationError,
    SessionNotFound,
    SessionStoreError,
)
from harness_agent.core import Event, EventType, SessionStore

T0 = datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"


def make_event(
    event_id: str,
    session_id: str,
    event_type: EventType = EventType.USER_MESSAGE,
    payload: dict[str, Any] | None = None,
    timestamp: datetime = T0,
) -> Event:
    return Event(
        id=event_id,
        session_id=session_id,
        type=event_type,
        timestamp=timestamp,
        payload={"text": "hola"} if payload is None else payload,
    )


@pytest.fixture
def store() -> SqliteSessionStore:
    return SqliteSessionStore(":memory:")


def event_rows(store: SqliteSessionStore) -> list[tuple[str, str, int]]:
    assert store._conn is not None
    rows = store._conn.execute("SELECT id, session_id, seq FROM events ORDER BY rowid").fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


# --- T003: save_event ----------------------------------------------------------------------------


def test_the_store_implements_the_session_store_port(store: SqliteSessionStore) -> None:
    assert isinstance(store, SessionStore)


def test_events_get_consecutive_orders_per_session(store: SqliteSessionStore) -> None:
    first = store.create_session().id
    second = store.create_session().id

    store.save_event(make_event("e1", first))
    store.save_event(make_event("e2", second))
    store.save_event(make_event("e3", first))

    assert event_rows(store) == [("e1", first, 1), ("e2", second, 1), ("e3", first, 2)]


def test_unknown_session_is_rejected_and_nothing_is_saved(store: SqliteSessionStore) -> None:
    with pytest.raises(SessionNotFound) as excinfo:
        store.save_event(make_event("e1", SENTINEL))

    assert SENTINEL not in str(excinfo.value)
    assert event_rows(store) == []
    assert store._conn is not None
    assert not store._conn.in_transaction


def test_duplicate_event_id_is_rejected_and_the_original_stays(
    store: SqliteSessionStore,
) -> None:
    sid = store.create_session().id
    store.save_event(make_event("e1", sid, payload={"text": "original"}))

    with pytest.raises(DuplicateEvent) as excinfo:
        store.save_event(make_event("e1", sid, payload={"text": "otro"}))

    assert "e1" not in str(excinfo.value)
    assert [e.payload for e in store.load_session(sid)] == [{"text": "original"}]
    store.save_event(make_event("e2", sid))
    assert event_rows(store) == [("e1", sid, 1), ("e2", sid, 2)]


def circular() -> dict[str, Any]:
    loop: dict[str, Any] = {}
    loop["self"] = loop
    return loop


@pytest.mark.parametrize(
    "payload",
    [
        {"obj": object()},
        {"value": float("nan")},
        {"value": float("inf")},
        circular(),
        {"bytes": b"abc"},
    ],
    ids=["object", "nan", "inf", "circular", "bytes"],
)
def test_unserializable_payload_is_rejected_before_any_transaction(
    store: SqliteSessionStore, payload: dict[str, Any]
) -> None:
    sid = store.create_session().id
    payload = {**payload, "secret": SENTINEL}

    with pytest.raises(EventSerializationError) as excinfo:
        store.save_event(make_event("e1", sid, payload=payload))

    assert SENTINEL not in str(excinfo.value)
    assert event_rows(store) == []
    assert store._conn is not None
    assert not store._conn.in_transaction


class FailingInsertConnection:
    """Proxy that fails the INSERT of an event once, like a full disk would."""

    def __init__(self, real: sqlite3.Connection) -> None:
        self._real = real
        self.fail_next_insert = True

    def execute(self, sql: str, *args: Any) -> sqlite3.Cursor:
        if self.fail_next_insert and sql.lstrip().upper().startswith("INSERT INTO EVENTS"):
            self.fail_next_insert = False
            raise sqlite3.OperationalError(f"database or disk is full {SENTINEL}")
        return self._real.execute(sql, *args)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


def test_engine_failure_rolls_back_and_keeps_the_order_without_gaps(
    store: SqliteSessionStore,
) -> None:
    sid = store.create_session().id
    store.save_event(make_event("e1", sid))
    assert store._conn is not None
    store._conn = FailingInsertConnection(store._conn)  # type: ignore[assignment]

    with pytest.raises(SessionStoreError) as excinfo:
        store.save_event(make_event("e2", sid))

    assert SENTINEL not in str(excinfo.value)
    assert excinfo.value.__cause__ is None
    store.save_event(make_event("e3", sid))
    assert event_rows(store) == [("e1", sid, 1), ("e3", sid, 2)]


def test_keyboard_interrupt_during_a_save_rolls_back_and_propagates(
    store: SqliteSessionStore,
) -> None:
    sid = store.create_session().id
    assert store._conn is not None
    real = store._conn

    class Interrupting(FailingInsertConnection):
        def execute(self, sql: str, *args: Any) -> NoReturn | sqlite3.Cursor:
            if sql.lstrip().upper().startswith("INSERT INTO EVENTS"):
                raise KeyboardInterrupt
            return self._real.execute(sql, *args)

    store._conn = Interrupting(real)  # type: ignore[assignment]

    with pytest.raises(KeyboardInterrupt):
        store.save_event(make_event("e1", sid))

    assert not real.in_transaction
    assert event_rows(store) == []


def test_save_event_on_a_closed_store_is_a_domain_error() -> None:
    closed = SqliteSessionStore(":memory:")
    closed.close()

    with pytest.raises(SessionStoreError):
        closed.save_event(make_event("e1", "s"))


def test_two_stores_on_one_file_never_repeat_an_order(tmp_path: Path) -> None:
    db = tmp_path / "sessions.db"
    with SqliteSessionStore(db) as a, SqliteSessionStore(db) as b:
        sid = a.create_session().id
        for index in range(5):
            a.save_event(make_event(f"a{index}", sid))
            b.save_event(make_event(f"b{index}", sid))

        orders = [row[2] for row in event_rows(a)]

    assert orders == list(range(1, 11))


# --- T004: load_session --------------------------------------------------------------------------


def test_events_come_back_identical_and_in_order(store: SqliteSessionStore) -> None:
    sid = store.create_session().id
    saved = [
        make_event("e1", sid, EventType.USER_MESSAGE, {"text": "hola"}),
        make_event("e2", sid, EventType.TOOL_REQUESTED, {"name": "leer_archivo", "n": 3}),
        make_event("e3", sid, EventType.ASSISTANT_MESSAGE, {"nested": {"ok": True, "x": None}}),
    ]
    for event in saved:
        store.save_event(event)

    assert store.load_session(sid) == saved


def test_order_follows_saving_not_the_timestamp(store: SqliteSessionStore) -> None:
    sid = store.create_session().id
    late = make_event("e1", sid, timestamp=T0 + timedelta(hours=1))
    early = make_event("e2", sid, timestamp=T0)
    store.save_event(late)
    store.save_event(early)

    assert [e.id for e in store.load_session(sid)] == ["e1", "e2"]


def test_sessions_do_not_mix(store: SqliteSessionStore) -> None:
    one = store.create_session().id
    two = store.create_session().id
    store.save_event(make_event("a1", one))
    store.save_event(make_event("b1", two))
    store.save_event(make_event("a2", one))

    assert [e.id for e in store.load_session(one)] == ["a1", "a2"]
    assert [e.id for e in store.load_session(two)] == ["b1"]


def test_unknown_or_empty_session_loads_as_empty(store: SqliteSessionStore) -> None:
    empty = store.create_session().id

    assert store.load_session(empty) == []
    assert store.load_session("missing") == []


def test_unicode_and_large_payloads_are_intact(store: SqliteSessionStore) -> None:
    sid = store.create_session().id
    payload = {"text": "ñandú ☃ 日本語 \"comillas\" 'simples'", "big": "x" * 200_000}
    store.save_event(make_event("e1", sid, payload=payload))

    assert store.load_session(sid)[0].payload == payload


def test_tuples_come_back_as_lists(store: SqliteSessionStore) -> None:
    sid = store.create_session().id
    store.save_event(make_event("e1", sid, payload={"pair": (1, 2)}))

    assert store.load_session(sid)[0].payload == {"pair": [1, 2]}


def test_a_thousand_events_keep_their_order_and_values(tmp_path: Path) -> None:
    with SqliteSessionStore(tmp_path / "sessions.db") as big:
        sid = big.create_session().id
        for index in range(1000):
            big.save_event(make_event(f"e{index}", sid, payload={"n": index}))

        loaded = big.load_session(sid)

    assert [e.id for e in loaded] == [f"e{n}" for n in range(1000)]
    assert [e.payload["n"] for e in loaded] == list(range(1000))


def insert_raw(store: SqliteSessionStore, sid: str, event_type: str, content: str) -> None:
    assert store._conn is not None
    store._conn.execute(
        "INSERT INTO events (id, session_id, seq, type, content, created_at) "
        "VALUES ('raw', ?, 1, ?, ?, '2026-10-23T10:30:00+00:00')",
        (sid, event_type, content),
    )
    store._conn.commit()


@pytest.mark.parametrize(
    ("event_type", "content"),
    [
        ("not_an_event_type", "{}"),
        ("user_message", "{not json"),
        ("user_message", "[1, 2]"),
    ],
    ids=["unknown-type", "invalid-json", "not-an-object"],
)
def test_a_damaged_row_is_a_domain_error(
    store: SqliteSessionStore, event_type: str, content: str
) -> None:
    sid = store.create_session().id
    insert_raw(store, sid, event_type, content)

    with pytest.raises(SessionStoreError):
        store.load_session(sid)


def test_load_session_translates_engine_errors(store: SqliteSessionStore) -> None:
    class Broken:
        def execute(self, *args: object, **kwargs: object) -> NoReturn:
            raise sqlite3.OperationalError(f"boom {SENTINEL}")

    store._conn = Broken()  # type: ignore[assignment]

    with pytest.raises(SessionStoreError) as excinfo:
        store.load_session(SENTINEL)

    assert SENTINEL not in str(excinfo.value)


def test_load_session_on_a_closed_store_is_a_domain_error() -> None:
    closed = SqliteSessionStore(":memory:")
    closed.close()

    with pytest.raises(SessionStoreError):
        closed.load_session("s")
