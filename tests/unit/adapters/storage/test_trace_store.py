"""SqliteTraceStore on a real file (HU-10-01).

The traces have their own table and no foreign key; a missing token count stays null (never a zero),
the rows come back in order with the parent of their session, and a failure of the engine is a fixed
``SessionStoreError`` that names nothing (the core catches it: a trace never changes a call).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from harness_agent.adapters.storage import SessionStoreError, SqliteSessionStore, SqliteTraceStore
from harness_agent.core import TraceLog, TraceRecord, TraceRow

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"


def record(session: str = "s1", name: str = "fake/test", **overrides: object) -> TraceRecord:
    values: dict[str, object] = {
        "session_id": session,
        "kind": "modelo",
        "name": name,
        "started_at": T0,
        "duration_ms": 250,
        "input_tokens": 100,
        "output_tokens": 20,
        "result": "ok",
        "size": 40,
    }
    return TraceRecord(**{**values, **overrides})  # type: ignore[arg-type]


class Rig:
    def __init__(self, path: Path) -> None:
        self.store = SqliteSessionStore(path)
        self.traces = SqliteTraceStore(self.store)

    def session(self, parent: str | None = None) -> str:
        return self.store.create_session(model="fake/test", parent_id=parent).id

    def raw(self, sql: str, *parameters: object) -> list[tuple[object, ...]]:
        connection = self.store.connection()
        found = connection.execute(sql, parameters).fetchall()
        connection.commit()
        return [tuple(row) for row in found]


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    made = Rig(tmp_path / "sessions.db")
    try:
        yield made
    finally:
        made.store.close()


def test_the_store_is_a_trace_log(rig: Rig) -> None:
    log: TraceLog = rig.traces

    assert log.count("nada") == 0


def test_a_trace_comes_back_as_it_was_written(rig: Rig) -> None:
    session = rig.session()
    rig.traces.record(record(session))

    assert rig.traces.rows(session, 10) == [
        TraceRow(
            session_id=session,
            parent_id=None,
            kind="modelo",
            name="fake/test",
            started_at=T0,
            duration_ms=250,
            input_tokens=100,
            output_tokens=20,
            result="ok",
            size=40,
        )
    ]


def test_no_tokens_stay_null_and_a_real_zero_stays_a_zero(rig: Rig) -> None:
    session = rig.session()
    rig.traces.record(record(session, input_tokens=None, output_tokens=None))
    rig.traces.record(record(session, input_tokens=0, output_tokens=0))

    stored = rig.raw("SELECT tokens_entrada, tokens_salida FROM trazas ORDER BY id")
    rows = rig.traces.rows(session, 10)

    assert stored == [(None, None), (0, 0)]
    assert [(row.input_tokens, row.output_tokens) for row in rows] == [(None, None), (0, 0)]


def test_the_instants_are_stored_in_utc_and_a_naive_one_is_taken_as_utc(rig: Rig) -> None:
    session = rig.session()
    local = datetime(2026, 11, 4, 9, 0, tzinfo=timezone(timedelta(hours=-3)))
    rig.traces.record(record(session, started_at=local))
    rig.traces.record(record(session, started_at=datetime(2026, 11, 4, 12, 0)))

    stored = rig.raw("SELECT inicio FROM trazas ORDER BY id")

    assert stored == [("2026-11-04T12:00:00+00:00",), ("2026-11-04T12:00:00+00:00",)]


def test_the_rows_are_the_latest_ones_oldest_first_and_the_count_has_no_limit(rig: Rig) -> None:
    session = rig.session()
    for index in range(5):
        rig.traces.record(record(session, name=f"m{index}"))

    assert [row.name for row in rig.traces.rows(session, 3)] == ["m2", "m3", "m4"]
    assert rig.traces.count(session) == 5
    assert rig.traces.rows(session, 0) == [] and rig.traces.rows(session, -2) == []


def test_the_rows_include_the_direct_children_with_their_parent_and_nothing_else(rig: Rig) -> None:
    parent = rig.session()
    child = rig.session(parent)
    grandchild = rig.session(child)
    stranger = rig.session()
    rig.traces.record(record(parent, name="p"))
    rig.traces.record(record(child, name="h"))
    rig.traces.record(record(grandchild, name="n"))
    rig.traces.record(record(stranger, name="x"))

    rows = rig.traces.rows(parent, 10)

    assert [(row.name, row.parent_id) for row in rows] == [("p", None), ("h", parent)]
    assert rig.traces.count(parent) == 2


def test_traces_of_a_session_that_is_not_in_the_sessions_table_are_still_found(rig: Rig) -> None:
    rig.traces.record(record("fantasma"))

    assert [row.parent_id for row in rig.traces.rows("fantasma", 10)] == [None]


def test_a_failure_of_the_engine_is_a_fixed_error_that_names_nothing(rig: Rig) -> None:
    rig.raw("DROP TABLE trazas")

    for call in (
        lambda: rig.traces.record(record(SENTINEL)),
        lambda: rig.traces.rows(SENTINEL, 5),
        lambda: rig.traces.count(SENTINEL),
    ):
        with pytest.raises(SessionStoreError) as raised:
            call()
        message = str(raised.value)
        assert message == "Error del almacén de las trazas."
        assert SENTINEL not in message and "trazas" not in message.replace("las trazas", "")


def test_a_row_with_an_unreadable_instant_is_a_fixed_error(rig: Rig) -> None:
    session = rig.session()
    rig.traces.record(record(session))
    rig.raw("UPDATE trazas SET inicio = 'no es una hora'")

    with pytest.raises(SessionStoreError) as raised:
        rig.traces.rows(session, 5)

    assert str(raised.value) == "Una traza guardada está dañada y no se puede leer."


def test_a_closed_store_is_a_store_error(rig: Rig) -> None:
    rig.store.close()

    with pytest.raises(SessionStoreError):
        rig.traces.record(record())
    with pytest.raises(SessionStoreError):
        rig.traces.rows("s1", 5)


def test_a_write_that_the_engine_refuses_leaves_no_partial_row(rig: Rig) -> None:
    session = rig.session()
    rig.raw("CREATE TRIGGER refuse BEFORE INSERT ON trazas BEGIN SELECT RAISE(ABORT, 'no'); END")

    with pytest.raises(SessionStoreError):
        rig.traces.record(record(session))

    assert rig.traces.count(session) == 0
