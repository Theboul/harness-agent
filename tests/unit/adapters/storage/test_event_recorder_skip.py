"""The ``skip`` of the recorder and the single row of ``context_compacted`` (HU-02-03 / R5).

The archive stores the summary event inside its own transaction; the recorder must not store it
again. Without ``skip`` the primary key makes the second save fail, so there are never two rows.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harness_agent.adapters.storage import (
    DuplicateEvent,
    SqliteCompactionArchive,
    SqliteSessionStore,
    attach_event_recorder,
)
from harness_agent.core import (
    CompactionCommit,
    Event,
    EventDeliveryError,
    EventType,
    InMemoryEventBus,
)

T0 = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


def make_event(event_type: EventType, session_id: str, index: int) -> Event:
    return Event(f"e{index}", session_id, event_type, T0, {"index": index})


def test_by_default_every_type_is_still_recorded() -> None:
    bus = InMemoryEventBus()
    with SqliteSessionStore(":memory:") as store:
        sid = store.create_session().id
        attach_event_recorder(bus, store)

        for n, kind in enumerate(EventType):
            bus.emit(make_event(kind, sid, n))

        assert [e.type for e in store.load_session(sid)] == list(EventType)


@pytest.mark.parametrize("how", ["positional", "keyword"])
def test_a_skipped_type_is_not_saved_and_the_others_are(how: str) -> None:
    bus = InMemoryEventBus()
    with SqliteSessionStore(":memory:") as store:
        sid = store.create_session().id
        if how == "positional":
            attach_event_recorder(bus, store, (EventType.CONTEXT_COMPACTED,))
        else:
            attach_event_recorder(bus, store, skip=(EventType.CONTEXT_COMPACTED,))

        for n, kind in enumerate(EventType):
            bus.emit(make_event(kind, sid, n))

        saved = [e.type for e in store.load_session(sid)]
        assert EventType.CONTEXT_COMPACTED not in saved
        assert saved == [kind for kind in EventType if kind is not EventType.CONTEXT_COMPACTED]


def test_an_empty_skip_changes_nothing() -> None:
    bus = InMemoryEventBus()
    with SqliteSessionStore(":memory:") as store:
        sid = store.create_session().id
        attach_event_recorder(bus, store, ())

        bus.emit(make_event(EventType.CONTEXT_COMPACTED, sid, 1))

        assert len(store.load_session(sid)) == 1


def test_skip_is_positional_or_keyword_in_the_third_place() -> None:
    parameters = list(inspect.signature(attach_event_recorder).parameters.values())

    assert [p.name for p in parameters] == ["bus", "store", "skip", "redact"]
    assert parameters[2].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters[2].default == ()
    assert parameters[3].kind is inspect.Parameter.KEYWORD_ONLY  # HU-10-02
    assert parameters[3].default is None


def compact(store: SqliteSessionStore, sid: str) -> Event:
    archive = SqliteCompactionArchive(store, clock=lambda: T0)
    receipt = archive.commit_compaction(CompactionCommit(sid, 1, 3, "resumen", "r1", "ev-r1"))
    assert receipt is not None
    return receipt.event


def rows_of_compaction(store: SqliteSessionStore, sid: str) -> int:
    return sum(1 for e in store.load_session(sid) if e.type is EventType.CONTEXT_COMPACTED)


def prepared(tmp_path: Path) -> tuple[SqliteSessionStore, str, InMemoryEventBus]:
    store = SqliteSessionStore(tmp_path / "s.db")
    sid = store.create_session().id
    bus = InMemoryEventBus()
    for n, kind in enumerate(
        [EventType.USER_MESSAGE, EventType.ASSISTANT_MESSAGE, EventType.USER_MESSAGE], start=1
    ):
        store.save_event(make_event(kind, sid, n))
    return store, sid, bus


def test_with_skip_publishing_the_saved_event_leaves_exactly_one_row(tmp_path: Path) -> None:
    store, sid, bus = prepared(tmp_path)
    try:
        attach_event_recorder(bus, store, (EventType.CONTEXT_COMPACTED,))
        event = compact(store, sid)

        bus.emit(event)  # what the compactor does after the commit

        assert rows_of_compaction(store, sid) == 1
    finally:
        store.close()


def test_without_skip_the_second_save_fails_and_there_is_still_one_row(tmp_path: Path) -> None:
    store, sid, bus = prepared(tmp_path)
    try:
        attach_event_recorder(bus, store)  # the mistake that skip prevents
        event = compact(store, sid)

        with pytest.raises(EventDeliveryError) as raised:
            bus.emit(event)

        assert any(isinstance(cause, DuplicateEvent) for cause in raised.value.exceptions)
        assert rows_of_compaction(store, sid) == 1
    finally:
        store.close()
