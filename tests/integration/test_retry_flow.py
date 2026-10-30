"""A real turn through the composed system survives a passing failure (HU-07-04 / T014).

The provider is a ``FakeProvider`` and the wait is injected. Everything else is the real
composition: the loop, the bus, the SQLite store and the terminal of the session.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.providers.errors import RateLimited
from harness_agent.bootstrap import Composition, run_session
from harness_agent.core import EventType, ProviderResponse, ProviderUnavailable, QuotaExceeded
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import SENTINEL, build, make_config


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class Waits:
    def __init__(self) -> None:
        self.seconds: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)


async def session(composition: Composition, line: str) -> tuple[int, str]:
    output = io.StringIO()
    code = await run_session(
        composition, input_stream=io.StringIO(f"{line}\n/salir\n"), output=output
    )
    return code, output.getvalue()


async def test_a_session_goes_on_after_a_rate_limit_and_a_503(
    tmp_path: Path, opened: list[Composition]
) -> None:
    provider = FakeProvider(
        [RateLimited(SENTINEL), ProviderUnavailable(SENTINEL), ProviderResponse(content="hecho")]
    )
    waits = Waits()
    composition = build(opened, make_config(tmp_path), provider, retry_sleep=waits)

    code, shown = await session(composition, "haz algo")

    assert code == 0
    assert "hecho" in shown
    assert SENTINEL not in shown
    assert provider.call_count == 3
    assert waits.seconds == [2.0, 4.0]


async def test_the_retries_leave_one_stored_event_each_and_nothing_else_changes(
    tmp_path: Path, opened: list[Composition]
) -> None:
    provider = FakeProvider([RateLimited("x"), ProviderResponse(content="hecho")])
    composition = build(opened, make_config(tmp_path), provider, retry_sleep=Waits())

    await session(composition, "haz algo")

    rows = composition.store.connection().execute("SELECT type FROM events ORDER BY 1").fetchall()
    types = [row[0] for row in rows]
    assert types.count(EventType.PROVIDER_ERROR.value) == 1
    assert EventType.ASSISTANT_MESSAGE.value in types


async def test_a_failure_that_does_not_pass_ends_the_turn_as_it_did_before(
    tmp_path: Path, opened: list[Composition]
) -> None:
    provider = FakeProvider([QuotaExceeded("cuota"), ProviderResponse(content="nunca")])
    waits = Waits()
    composition = build(opened, make_config(tmp_path), provider, retry_sleep=waits)

    _, shown = await session(composition, "haz algo")

    assert provider.call_count == 1 and waits.seconds == []
    assert "nunca" not in shown


async def test_a_passing_failure_that_does_not_pass_gives_up_with_the_last_error(
    tmp_path: Path, opened: list[Composition]
) -> None:
    provider = FakeProvider([ProviderUnavailable(SENTINEL)] * 5)
    waits = Waits()
    composition = build(opened, make_config(tmp_path), provider, retry_sleep=waits)
    stored: list[dict[str, object]] = []
    composition.bus.subscribe(EventType.PROVIDER_ERROR, lambda e: stored.append(dict(e.payload)))

    await session(composition, "haz algo")

    assert provider.call_count == 5
    assert waits.seconds == [2.0, 4.0, 8.0, 16.0]
    assert [p["reason"] for p in stored] == ["retry"] * 4 + ["provider_exception"]
    assert stored[-1]["error_type"] == "ProviderUnavailable"
