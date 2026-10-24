"""attach_event_recorder: the store subscribes to every event type (HU-03-02 / T008)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.adapters.storage.errors import SessionNotFound
from harness_agent.adapters.storage.event_recorder import attach_event_recorder
from harness_agent.core import (
    Event,
    EventBus,
    EventDeliveryError,
    EventType,
    InMemoryEventBus,
    SessionStore,
    SessionSummary,
)

T0 = datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc)


def make_event(event_type: EventType, session_id: str, index: int) -> Event:
    return Event(
        id=f"e{index}",
        session_id=session_id,
        type=event_type,
        timestamp=T0,
        payload={"index": index},
    )


def test_every_event_type_is_saved_in_order_before_emit_returns() -> None:
    bus = InMemoryEventBus()
    with SqliteSessionStore(":memory:") as store:
        sid = store.create_session().id
        attach_event_recorder(bus, store)
        emitted = [make_event(t, sid, n) for n, t in enumerate(EventType)]

        for event in emitted:
            bus.emit(event)
            assert store.load_session(sid)[-1] == event

        assert store.load_session(sid) == emitted
    assert len(emitted) == 17


def test_a_store_failure_reaches_the_emitter_with_its_cause() -> None:
    bus = InMemoryEventBus()
    with SqliteSessionStore(":memory:") as store:
        attach_event_recorder(bus, store)

        with pytest.raises(EventDeliveryError) as excinfo:
            bus.emit(make_event(EventType.USER_MESSAGE, "missing", 1))

    causes = excinfo.value.exceptions
    assert len(causes) == 1
    assert isinstance(causes[0], SessionNotFound)


class RecordingStore(SessionStore):
    """Test double that only records calls to the port."""

    def __init__(self) -> None:
        self.saved: list[Event] = []

    def save_event(self, event: Event) -> None:
        self.saved.append(event)

    def load_session(self, session_id: str) -> list[Event]:
        return []

    def list_sessions(self) -> list[SessionSummary]:
        return []


def test_the_recorder_only_uses_the_port() -> None:
    bus = InMemoryEventBus()
    store = RecordingStore()
    attach_event_recorder(bus, store)
    event = make_event(EventType.ASSISTANT_MESSAGE, "s", 1)

    bus.emit(event)

    assert store.saved == [event]


def test_the_recorder_accepts_any_event_bus() -> None:
    subscribed: list[EventType] = []

    class SpyBus(EventBus):
        def emit(self, event: Event) -> None:
            raise NotImplementedError

        def subscribe(self, event_type: EventType, handler: object) -> None:
            subscribed.append(event_type)

    attach_event_recorder(SpyBus(), RecordingStore())

    assert subscribed == list(EventType)
