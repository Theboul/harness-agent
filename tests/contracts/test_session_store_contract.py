"""Contract shared by every SessionStore implementation (HU-03-02 / T005).

Runs against the in-memory double and the SQLite adapter. Only what both implementations
guarantee is checked here: creating sessions on the fly is a double-only convenience and is not
part of the contract.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from typing import Any

import pytest

from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.core import Event, EventType, SessionStore
from tests.doubles.in_memory_store import InMemorySessionStore

T0 = datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc)

StoreFixture = tuple[SessionStore, Callable[[], str]]


def make_event(event_id: str, session_id: str, payload: dict[str, Any] | None = None) -> Event:
    return Event(
        id=event_id,
        session_id=session_id,
        type=EventType.USER_MESSAGE,
        timestamp=T0,
        payload={"text": "hola"} if payload is None else payload,
    )


@pytest.fixture(params=["in-memory", "sqlite"])
def harness(request: pytest.FixtureRequest) -> Iterator[StoreFixture]:
    """A store plus a function that returns a session id the store accepts."""
    counter = itertools.count(1)
    if request.param == "in-memory":
        yield InMemorySessionStore(), lambda: f"session-{next(counter)}"
        return
    with SqliteSessionStore(":memory:") as sqlite_store:
        yield sqlite_store, lambda: sqlite_store.create_session().id


def test_events_come_back_in_saving_order(harness: StoreFixture) -> None:
    store, new_session = harness
    sid = new_session()
    events = [make_event(f"e{n}", sid, {"n": n}) for n in range(5)]
    for event in events:
        store.save_event(event)

    assert store.load_session(sid) == events


def test_sessions_do_not_mix(harness: StoreFixture) -> None:
    store, new_session = harness
    one, two = new_session(), new_session()
    store.save_event(make_event("a1", one))
    store.save_event(make_event("b1", two))
    store.save_event(make_event("a2", one))

    assert [e.id for e in store.load_session(one)] == ["a1", "a2"]
    assert [e.id for e in store.load_session(two)] == ["b1"]


def test_unknown_session_loads_as_empty(harness: StoreFixture) -> None:
    store, _ = harness

    assert store.load_session("missing") == []


def test_loaded_events_are_equal_to_the_saved_ones(harness: StoreFixture) -> None:
    store, new_session = harness
    sid = new_session()
    saved = Event(
        id="e1",
        session_id=sid,
        type=EventType.TOOL_REQUESTED,
        timestamp=T0,
        payload={"name": "leer_archivo", "nested": {"ok": True, "items": [1, 2, None]}},
    )
    store.save_event(saved)

    (loaded,) = store.load_session(sid)
    assert loaded == saved
    assert loaded.timestamp.tzinfo is not None


def test_both_implementations_satisfy_the_port(harness: StoreFixture) -> None:
    store, _ = harness

    assert isinstance(store, SessionStore)
