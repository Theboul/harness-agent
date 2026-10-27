"""SqliteCompactionArchive on a real file (HU-02-03 / T007, contracts/store_protocol.md E1 to E5).

The events are saved with ``save_event`` like the recorder does; the archive then reads the
messages and covers a range in one transaction. Failures are real SQLite errors raised by
triggers, so the rollback is the engine's and not a simulation.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harness_agent.adapters.storage import (
    DuplicateEvent,
    SessionStoreError,
    SqliteCompactionArchive,
    SqliteSessionStore,
)
from harness_agent.core import CompactionCommit, Event, EventType

T0 = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"
E = EventType

# The events of E1 of the contract: (seq, type).
E1_TYPES = [
    E.USER_MESSAGE,
    E.ASSISTANT_MESSAGE,
    E.TOOL_REQUESTED,
    E.PERMISSION_DECIDED,
    E.TOOL_FINISHED,
    E.ASSISTANT_MESSAGE,
    E.USER_MESSAGE,
    E.ASSISTANT_MESSAGE,
    E.USER_MESSAGE,
    E.ASSISTANT_MESSAGE,
]


class Rig:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.store = SqliteSessionStore(path)
        self.session = self.store.create_session().id
        self.archive = SqliteCompactionArchive(self.store, clock=lambda: T0)
        self.counter = 0

    def add(self, kind: EventType, payload: dict[str, object] | None = None) -> None:
        self.counter += 1
        self.store.save_event(
            Event(
                id=f"ev-{self.counter}",
                session_id=self.session,
                type=kind,
                timestamp=T0,
                payload=payload if payload is not None else {"n": self.counter},
            )
        )

    def add_all(self, kinds: list[EventType]) -> None:
        for kind in kinds:
            self.add(kind)

    def commit(
        self, through: int, *, protected: int = 1, summary_id: str = "r1", event_id: str = "ev-r1"
    ) -> object:
        return self.archive.commit_compaction(
            CompactionCommit(
                self.session, protected, through, "Se migró el módulo.", summary_id, event_id
            )
        )

    def raw(self, sql: str, *parameters: object) -> list[tuple[object, ...]]:
        connection = sqlite3.connect(self.path)
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def snapshot(self) -> dict[str, list[tuple[object, ...]]]:
        return {
            table: self.raw(f"SELECT * FROM {table} ORDER BY 1")
            for table in ("sessions", "events", "resumenes")
        }

    def close(self) -> None:
        self.store.close()


@pytest.fixture
def rig(tmp_path: Path):  # type: ignore[no-untyped-def]
    opened = Rig(tmp_path / "sessions.db")
    yield opened
    opened.close()


@pytest.fixture
def e1(rig: Rig) -> Rig:
    rig.add_all(E1_TYPES)
    return rig


# --- message_events -------------------------------------------------------------------------------


def test_message_events_returns_only_the_three_kinds_in_order(e1: Rig) -> None:
    found = e1.archive.message_events(e1.session)

    assert [(m.seq, m.kind, m.covered) for m in found] == [
        (1, "user", False),
        (2, "assistant", False),
        (5, "tool", False),
        (6, "assistant", False),
        (7, "user", False),
        (8, "assistant", False),
        (9, "user", False),
        (10, "assistant", False),
    ]


def test_message_events_of_another_session_or_an_empty_one(e1: Rig) -> None:
    other = e1.store.create_session().id

    assert e1.archive.message_events(other) == []
    assert e1.archive.message_events("no-existe") == []


# --- E1: one compaction ---------------------------------------------------------------------------


def test_e1_the_range_the_events_marked_and_the_event_of_the_summary(e1: Rig) -> None:
    receipt = e1.commit(6)

    assert (receipt.desde, receipt.hasta, receipt.eventos) == (2, 6, 5)  # type: ignore[attr-defined]
    assert receipt.summary_id == "r1"  # type: ignore[attr-defined]
    event = receipt.event  # type: ignore[attr-defined]
    assert event.id == "ev-r1" and event.session_id == e1.session
    assert event.type is EventType.CONTEXT_COMPACTED
    assert event.payload == {"desde": 2, "hasta": 6, "eventos": 5}
    assert e1.raw("SELECT seq FROM events WHERE compacted_by = 'r1' ORDER BY seq") == [
        (2,),
        (3,),
        (4,),
        (5,),
        (6,),
    ]
    assert e1.raw("SELECT seq FROM events WHERE compacted_by IS NULL ORDER BY seq") == [
        (1,),
        (7,),
        (8,),
        (9,),
        (10,),
        (11,),
    ]
    (row,) = e1.raw("SELECT seq, type, content FROM events WHERE id = 'ev-r1'")
    assert row[:2] == (11, "context_compacted")
    assert json.loads(str(row[2])) == {"desde": 2, "hasta": 6, "eventos": 5}
    assert e1.raw(
        "SELECT id, sesion_id, evento_desde, evento_hasta, texto, creado FROM resumenes"
    ) == [("r1", e1.session, 2, 6, "Se migró el módulo.", T0.isoformat())]
    assert event.timestamp == T0


def test_the_event_of_the_summary_carries_no_text(e1: Rig) -> None:
    e1.commit(6)

    (content,) = e1.raw("SELECT content FROM events WHERE type = 'context_compacted'")[0]
    assert "migró" not in str(content)


def test_ac02_nothing_is_deleted_and_only_compacted_by_changes(e1: Rig) -> None:
    before = e1.raw(
        "SELECT id, session_id, seq, type, content, created_at FROM events ORDER BY seq"
    )
    loaded_before = e1.store.load_session(e1.session)

    e1.commit(6)

    after = e1.raw(
        "SELECT id, session_id, seq, type, content, created_at FROM events WHERE type != "
        "'context_compacted' ORDER BY seq"
    )
    assert after == before  # every column but compacted_by is what it was
    loaded = e1.store.load_session(e1.session)
    assert loaded[:-1] == loaded_before
    assert loaded[-1].type is EventType.CONTEXT_COMPACTED and len(loaded) == len(loaded_before) + 1


def test_events_that_are_not_messages_inside_the_range_are_covered(e1: Rig) -> None:
    e1.commit(6)

    covered = {
        int(str(row[0])): str(row[1])
        for row in e1.raw("SELECT seq, type FROM events WHERE compacted_by = 'r1'")
    }
    assert covered[3] == "tool_requested" and covered[4] == "permission_decided"


# --- E2: idempotence ------------------------------------------------------------------------------


def test_e2_the_same_commit_twice_writes_nothing_the_second_time(e1: Rig) -> None:
    e1.commit(6)
    before = e1.snapshot()

    again = e1.commit(6, summary_id="r2", event_id="ev-r2")

    assert again is None
    assert e1.snapshot() == before
    assert e1.raw("SELECT count(*) FROM resumenes") == [(1,)]
    assert e1.raw("SELECT count(*) FROM events") == [(11,)]


def test_a_range_with_nothing_to_cover_writes_nothing(e1: Rig) -> None:
    before = e1.snapshot()

    assert e1.commit(1) is None  # only the protected request lies at or before it
    assert e1.snapshot() == before


# --- E3: a second compaction ----------------------------------------------------------------------


def test_e3_the_second_compaction_skips_the_event_of_the_summary_and_the_request(e1: Rig) -> None:
    e1.commit(6)
    e1.add_all(
        [E.USER_MESSAGE, E.ASSISTANT_MESSAGE, E.USER_MESSAGE, E.ASSISTANT_MESSAGE]  # seq 12 to 15
    )
    e1.add_all(
        [E.USER_MESSAGE, E.ASSISTANT_MESSAGE, E.USER_MESSAGE, E.ASSISTANT_MESSAGE]
    )  # 16 to 19

    receipt = e1.commit(16, summary_id="r2", event_id="ev-r2")

    assert (receipt.desde, receipt.hasta, receipt.eventos) == (7, 16, 9)  # type: ignore[attr-defined]
    covered = [
        row[0] for row in e1.raw("SELECT seq FROM events WHERE compacted_by = 'r2' ORDER BY seq")
    ]
    assert covered == [7, 8, 9, 10, 12, 13, 14, 15, 16]
    assert 11 not in covered and 1 not in covered  # the first summary event and the request
    assert e1.raw("SELECT seq FROM events WHERE id = 'ev-r2'") == [(20,)]
    first = e1.raw("SELECT evento_desde, evento_hasta FROM resumenes WHERE id = 'r1'")
    second = e1.raw("SELECT evento_desde, evento_hasta FROM resumenes WHERE id = 'r2'")
    assert first == [(2, 6)] and second == [(7, 16)]
    assert e1.raw("SELECT count(*) FROM events WHERE compacted_by = 'r1'") == [(5,)]


# --- E5: an assistant message without content -----------------------------------------------------


def test_e5_the_real_events_of_an_empty_assistant_message(rig: Rig) -> None:
    rig.add_all(
        [
            E.USER_MESSAGE,
            E.TOOL_REQUESTED,
            E.PERMISSION_DECIDED,
            E.TOOL_FINISHED,
            E.ASSISTANT_MESSAGE,
        ]
    )

    kinds = [(m.seq, m.kind) for m in rig.archive.message_events(rig.session)]
    receipt = rig.commit(4)

    assert kinds == [(1, "user"), (4, "tool"), (5, "assistant")]
    assert (receipt.desde, receipt.hasta, receipt.eventos) == (2, 4, 3)  # type: ignore[attr-defined]
    assert rig.raw("SELECT seq FROM events WHERE compacted_by = 'r1' ORDER BY seq") == [
        (2,),
        (3,),
        (4,),
    ]
    assert rig.raw("SELECT compacted_by FROM events WHERE seq = 5") == [(None,)]


# --- E4: rollback ---------------------------------------------------------------------------------

TRIGGERS = {
    "insert of the summary": (
        "CREATE TRIGGER boom BEFORE INSERT ON resumenes BEGIN SELECT RAISE(ABORT, 'inyectado'); END"
    ),
    "update of the marks": (
        "CREATE TRIGGER boom BEFORE UPDATE OF compacted_by ON events "
        "BEGIN SELECT RAISE(ABORT, 'inyectado'); END"
    ),
    "insert of the event": (
        "CREATE TRIGGER boom BEFORE INSERT ON events WHEN NEW.type = 'context_compacted' "
        "BEGIN SELECT RAISE(ABORT, 'inyectado'); END"
    ),
}


@pytest.mark.parametrize("step", list(TRIGGERS))
def test_e4_a_failure_in_any_step_leaves_the_database_identical(e1: Rig, step: str) -> None:
    before = e1.snapshot()
    e1.store.connection().execute(TRIGGERS[step])
    e1.store.connection().commit()

    with pytest.raises(SessionStoreError) as raised:
        e1.commit(6)

    assert e1.snapshot() == before
    assert e1.raw("SELECT count(*) FROM events WHERE compacted_by IS NOT NULL") == [(0,)]
    assert not e1.store.connection().in_transaction
    assert "inyectado" not in str(raised.value) and SENTINEL not in str(raised.value)


def test_after_a_rollback_the_same_commit_works(e1: Rig) -> None:
    e1.store.connection().execute(TRIGGERS["insert of the event"])
    e1.store.connection().commit()
    with pytest.raises(SessionStoreError):
        e1.commit(6)
    e1.store.connection().execute("DROP TRIGGER boom")
    e1.store.connection().commit()

    receipt = e1.commit(6)

    assert receipt is not None and receipt.eventos == 5  # type: ignore[attr-defined]


def test_a_duplicate_event_id_is_refused_and_nothing_is_left_behind(e1: Rig) -> None:
    before = e1.snapshot()

    with pytest.raises(DuplicateEvent):
        e1.commit(6, event_id="ev-3")  # that identifier is already an event of the session

    assert e1.snapshot() == before


def test_a_duplicate_summary_id_is_refused_and_nothing_is_left_behind(e1: Rig) -> None:
    e1.commit(6)
    e1.add_all([E.USER_MESSAGE, E.ASSISTANT_MESSAGE])
    before = e1.snapshot()

    with pytest.raises(SessionStoreError):
        e1.commit(13, summary_id="r1", event_id="ev-r2")

    assert e1.snapshot() == before


def test_the_error_never_carries_the_text_of_the_summary(e1: Rig) -> None:
    e1.store.connection().execute(TRIGGERS["insert of the summary"])
    e1.store.connection().commit()

    with pytest.raises(SessionStoreError) as raised:
        e1.archive.commit_compaction(
            CompactionCommit(e1.session, 1, 6, "Resumen " + SENTINEL, "r1", "ev-r1")
        )

    assert SENTINEL not in str(raised.value) and SENTINEL not in repr(raised.value.args)
    assert raised.value.__cause__ is None


def test_a_closed_store_fails_with_the_store_error(e1: Rig) -> None:
    e1.store.close()

    with pytest.raises(SessionStoreError):
        e1.archive.message_events(e1.session)
    with pytest.raises(SessionStoreError):
        e1.commit(6)


# --- R17: the connection of the store -------------------------------------------------------------


def test_r17_the_archive_never_opens_a_connection_of_its_own(
    e1: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> sqlite3.Connection:
        raise AssertionError("the archive must use the connection of the store")

    monkeypatch.setattr(sqlite3, "connect", forbidden)

    e1.archive.message_events(e1.session)
    receipt = e1.commit(6)

    assert receipt is not None


def test_r17_saving_events_before_and_after_compacting_on_the_same_database(e1: Rig) -> None:
    e1.commit(6)
    e1.add(E.USER_MESSAGE)  # save_event after the commit: no lock is left behind
    e1.add(E.ASSISTANT_MESSAGE)

    assert e1.raw("SELECT max(seq) FROM events") == [(13,)]
    assert not e1.store.connection().in_transaction


def test_r17_another_connection_reads_the_result_after_the_commit(e1: Rig) -> None:
    e1.commit(6)

    reader = sqlite3.connect(e1.path)
    try:
        assert reader.execute("SELECT count(*) FROM resumenes").fetchone() == (1,)
        assert reader.execute(
            "SELECT count(*) FROM events WHERE compacted_by = 'r1'"
        ).fetchone() == (5,)
    finally:
        reader.close()


def test_the_default_clock_is_utc_now(tmp_path: Path) -> None:
    store = SqliteSessionStore(tmp_path / "default.db")
    try:
        session = store.create_session().id
        for n, kind in enumerate([E.USER_MESSAGE, E.ASSISTANT_MESSAGE, E.USER_MESSAGE], start=1):
            store.save_event(Event(f"x{n}", session, kind, T0, {}))
        receipt = SqliteCompactionArchive(store).commit_compaction(
            CompactionCommit(session, 1, 3, "resumen", "r1", "ev-r1")
        )
        assert receipt is not None
        assert receipt.event.timestamp.tzinfo is not None
        assert abs((datetime.now(timezone.utc) - receipt.event.timestamp).total_seconds()) < 60
    finally:
        store.close()


def test_a_naive_time_from_the_clock_is_taken_as_utc(tmp_path: Path) -> None:
    store = SqliteSessionStore(tmp_path / "naive.db")
    try:
        session = store.create_session().id
        for n, kind in enumerate([E.USER_MESSAGE, E.ASSISTANT_MESSAGE], start=1):
            store.save_event(Event(f"n{n}", session, kind, T0, {}))
        archive = SqliteCompactionArchive(store, clock=lambda: datetime(2026, 10, 27, 12, 0))

        receipt = archive.commit_compaction(CompactionCommit(session, 1, 2, "resumen", "r1", "ev"))

        assert receipt is not None and receipt.event.timestamp == T0
    finally:
        store.close()


def test_an_engine_error_while_reading_is_a_store_error_without_details(e1: Rig) -> None:
    e1.store.connection().execute("ALTER TABLE events RENAME TO events_moved")

    with pytest.raises(SessionStoreError) as raised:
        e1.archive.message_events(e1.session)

    assert "events" not in str(raised.value).replace("compactación", "")
    assert raised.value.__cause__ is None
