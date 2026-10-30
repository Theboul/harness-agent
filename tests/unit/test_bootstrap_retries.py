"""The composition root wraps the provider with retries and records each one (HU-07-04 / T012).

The provider is a ``FakeProvider`` and the wait is injected: nothing waits and nothing leaves the
machine. The record of a retry is an existing event (``provider_error``, reason ``retry``).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.providers.errors import RateLimited
from harness_agent.adapters.providers.retrying_provider import RetryingProvider
from harness_agent.bootstrap import Composition
from harness_agent.config import HarnessConfig, Retries
from harness_agent.core import Event, EventType, ProviderResponse, ProviderTimeout, QuotaExceeded
from harness_agent.core.loop import TurnStatus
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import SENTINEL, build, make_config, one_turn
from tests.unit.test_bootstrap_resume import drive, live

OK = ProviderResponse(content="listo")


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


def configured(tmp_path: Path, **retries: float) -> HarnessConfig:
    config = make_config(tmp_path)
    return dataclasses.replace(config, retries=Retries(**retries))  # type: ignore[arg-type]


def listen(composition: Composition) -> list[Event]:
    seen: list[Event] = []
    composition.bus.subscribe(EventType.PROVIDER_ERROR, seen.append)
    return seen


async def test_the_provider_of_the_loop_retries_a_passing_failure(
    tmp_path: Path, opened: list[Composition]
) -> None:
    inner = FakeProvider([RateLimited("a"), ProviderTimeout("b"), OK])
    waits = Waits()
    composition = build(
        opened,
        configured(tmp_path),
        inner,
        retry_sleep=waits,
    )

    result = await one_turn(composition)

    assert result.status is TurnStatus.COMPLETED
    assert inner.call_count == 3
    assert waits.seconds == [2.0, 4.0]


async def test_the_configured_policy_is_the_one_applied(
    tmp_path: Path, opened: list[Composition]
) -> None:
    inner = FakeProvider([ProviderTimeout("a"), ProviderTimeout("b"), ProviderTimeout("c"), OK])
    waits = Waits()
    config = configured(tmp_path, max_attempts=3, base_delay=1.0, max_delay=1.5)
    composition = build(opened, config, inner, retry_sleep=waits)

    result = await one_turn(composition)

    assert result.status is TurnStatus.PROVIDER_FAILED
    assert waits.seconds == [1.0, 1.5]
    assert inner.call_count == 3


async def test_one_attempt_turns_the_retries_off(tmp_path: Path, opened: list[Composition]) -> None:
    inner = FakeProvider([ProviderTimeout("a"), OK])
    waits = Waits()
    config = configured(tmp_path, max_attempts=1)
    composition = build(opened, config, inner, retry_sleep=waits)

    result = await one_turn(composition)

    assert result.status is TurnStatus.PROVIDER_FAILED
    assert inner.call_count == 1 and waits.seconds == []


async def test_the_wrapper_is_the_provider_the_loop_uses(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = build(opened, make_config(tmp_path), FakeProvider([OK]))

    assert isinstance(composition.loop._provider, RetryingProvider)


async def test_each_retry_is_a_provider_error_event_with_no_data_of_the_error(
    tmp_path: Path, opened: list[Composition]
) -> None:
    inner = FakeProvider([RateLimited(f"texto {SENTINEL}"), ProviderTimeout(SENTINEL), OK])
    composition = build(
        opened,
        configured(tmp_path),
        inner,
        retry_sleep=Waits(),
    )
    seen = listen(composition)

    await one_turn(composition)

    assert [dict(event.payload) for event in seen] == [
        {
            "reason": "retry",
            "error_type": "RateLimited",
            "attempt": 1,
            "max_attempts": 5,
            "delay_seconds": 2.0,
        },
        {
            "reason": "retry",
            "error_type": "ProviderTimeout",
            "attempt": 2,
            "max_attempts": 5,
            "delay_seconds": 4.0,
        },
    ]
    assert {event.session_id for event in seen} == {composition.session_id}
    assert SENTINEL not in repr([event.payload for event in seen])


async def test_the_retry_events_are_stored_with_the_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    inner = FakeProvider([ProviderTimeout("a"), OK])
    composition = build(
        opened,
        configured(tmp_path),
        inner,
        retry_sleep=Waits(),
    )

    await one_turn(composition)

    rows = (
        composition.store.connection()
        .execute("SELECT session_id, type FROM events WHERE type = 'provider_error'")
        .fetchall()
    )
    assert [tuple(row) for row in rows] == [(composition.session_id, "provider_error")]


async def test_a_permanent_failure_is_not_recorded_as_a_retry(
    tmp_path: Path, opened: list[Composition]
) -> None:
    inner = FakeProvider([QuotaExceeded(SENTINEL)])
    composition = build(
        opened,
        configured(tmp_path),
        inner,
        retry_sleep=Waits(),
    )
    seen = listen(composition)

    await one_turn(composition)

    assert [event.payload["reason"] for event in seen] == ["provider_exception"]


async def test_a_retry_after_resuming_goes_to_the_session_that_is_active(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = await live(tmp_path, opened)
    inner = FakeProvider([ProviderTimeout("a"), OK])
    composition = build(
        opened,
        make_config(tmp_path, workspace=tmp_path / "trabajo", model="openai/modelo-de-prueba"),
        inner,
        system_name="Linux",
        retry_sleep=Waits(),
    )
    seen = listen(composition)

    await drive(composition, f"/reanudar {past}", "sigue")

    assert [event.payload["reason"] for event in seen] == ["retry"]
    assert [event.session_id for event in seen] == [past]
    assert past != composition.session_id


async def test_resuming_works_for_a_composition_without_a_cursor(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = await live(tmp_path, opened)
    composition = build(
        opened,
        make_config(tmp_path, workspace=tmp_path / "trabajo", model="openai/modelo-de-prueba"),
        FakeProvider([OK]),
        system_name="Linux",
    )
    without_cursor = dataclasses.replace(composition, session_cursor=None)

    _, shown = await drive(without_cursor, f"/reanudar {past}")

    assert "No se pudo" not in shown
