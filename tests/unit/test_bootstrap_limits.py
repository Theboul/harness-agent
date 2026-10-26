"""The composition root gives the loop the configured session limits (HU-01-06 / T010)."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition
from harness_agent.config import Limits
from harness_agent.core import EventType, TokenUsage, ToolCall
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.loop import TurnStatus
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config, one_turn


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def endless(count: int) -> FakeProvider:
    """A provider that keeps asking for a tool nobody registered (the loop rejects it)."""
    return FakeProvider(
        [
            ProviderResponse(
                tool_calls=[ToolCall(id=f"c{i}", name="inexistente", arguments={})],
                usage=None,
            )
            for i in range(count)
        ]
    )


class TestTheComposedLoopAppliesTheLimits:
    async def test_the_configured_turn_limit_stops_the_loop(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        config = make_config(tmp_path)
        config = dataclasses.replace(config, limits=Limits(max_turns=2))
        provider = endless(10)
        composition = build(opened, config, provider)
        events: list[dict[str, object]] = []
        composition.bus.subscribe(EventType.LIMIT_REACHED, lambda e: events.append(dict(e.payload)))

        result = await one_turn(composition)

        assert result.status is TurnStatus.LIMIT_REACHED
        assert provider.call_count == 2
        assert events == [{"limit": "turns", "used": 2, "maximum": 2}]

    async def test_the_defaults_are_active_in_the_real_start_up(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = endless(60)
        composition = build(opened, make_config(tmp_path), provider)

        result = await one_turn(composition)

        assert result.status is TurnStatus.LIMIT_REACHED
        assert provider.call_count == Limits().max_turns == 30

    async def test_the_run_budget_is_max_tokens_and_not_the_cap_of_one_call(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        usage = TokenUsage(input_tokens=60, output_tokens=0)
        script = [
            ProviderResponse(
                tool_calls=[ToolCall(id=f"c{i}", name="inexistente", arguments={})], usage=usage
            )
            for i in range(5)
        ]

        # A small per-call cap does not exhaust a large run budget...
        roomy = dataclasses.replace(
            make_config(tmp_path), limits=Limits(max_tokens=100_000, max_output_tokens=5)
        )
        provider = FakeProvider(script[:3] + [ProviderResponse(content="listo")])
        result = await one_turn(build(opened, roomy, provider))
        assert result.status is TurnStatus.COMPLETED

        # ...and a small run budget stops the loop whatever the per-call cap is.
        tight = dataclasses.replace(
            make_config(tmp_path), limits=Limits(max_tokens=100, max_output_tokens=4096)
        )
        provider = FakeProvider(list(script))
        result = await one_turn(build(opened, tight, provider))
        assert result.status is TurnStatus.LIMIT_REACHED
        assert provider.call_count == 2
