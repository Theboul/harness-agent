"""The ``TraceLog`` protocol of the core against its real SQLite implementation (HU-10-01).

The same assertions run against a small in-memory log (kept here: the shared doubles are protected)
and against ``SqliteTraceStore`` on a real file, so the two cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harness_agent.adapters.storage import SqliteSessionStore, SqliteTraceStore
from harness_agent.core import TraceLog, TraceRecord, TraceRow

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


class MemoryTraceLog:
    def __init__(self) -> None:
        self._records: list[TraceRecord] = []

    def record(self, record: TraceRecord) -> None:
        self._records.append(record)

    def rows(self, session_id: str, limit: int) -> list[TraceRow]:
        own = [item for item in self._records if item.session_id == session_id]
        chosen = own[-limit:] if limit > 0 else []
        return [TraceRow(**vars(item), parent_id=None) for item in chosen]

    def count(self, session_id: str) -> int:
        return len([item for item in self._records if item.session_id == session_id])


@pytest.fixture(params=["memory", "sqlite"])
def log(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[tuple[TraceLog, str]]:
    if request.param == "memory":
        yield MemoryTraceLog(), "s1"
        return
    sessions = SqliteSessionStore(tmp_path / "sessions.db")
    try:
        yield SqliteTraceStore(sessions), sessions.create_session(model="fake/test").id
    finally:
        sessions.close()


def record(session: str, name: str, **overrides: object) -> TraceRecord:
    values: dict[str, object] = {
        "session_id": session,
        "kind": "herramienta",
        "name": name,
        "started_at": T0,
        "duration_ms": 5,
        "input_tokens": None,
        "output_tokens": None,
        "result": "ok",
        "size": 3,
    }
    return TraceRecord(**{**values, **overrides})  # type: ignore[arg-type]


def test_the_implementation_is_a_trace_log(log: tuple[TraceLog, str]) -> None:
    assert log[0].count(log[1]) == 0 and log[0].rows(log[1], 10) == []


def test_the_rows_come_back_in_order_and_only_the_latest_ones_up_to_the_limit(
    log: tuple[TraceLog, str],
) -> None:
    traces, session = log
    for index in range(4):
        traces.record(record(session, f"t{index}"))

    assert [row.name for row in traces.rows(session, 10)] == ["t0", "t1", "t2", "t3"]
    assert [row.name for row in traces.rows(session, 2)] == ["t2", "t3"]
    assert traces.rows(session, 0) == []
    assert traces.count(session) == 4


def test_what_was_recorded_is_what_is_read_back_without_inventing_tokens(
    log: tuple[TraceLog, str],
) -> None:
    traces, session = log
    traces.record(record(session, "uno"))
    traces.record(record(session, "dos", input_tokens=0, output_tokens=7))

    first, second = traces.rows(session, 10)

    assert (first.input_tokens, first.output_tokens) == (None, None)
    assert (second.input_tokens, second.output_tokens) == (0, 7)
    assert (second.kind, second.result, second.size, second.duration_ms) == (
        "herramienta",
        "ok",
        3,
        5,
    )
