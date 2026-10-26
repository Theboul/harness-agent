"""Session limits in the agentic loop (HU-01-06, US1-US3).

AC-01 (literal): "Dado un límite de N turnos, cuando el bucle lo alcanza, entonces se detiene,
emite un evento y explica el motivo."
AC-02 (literal): "Dado un límite de consumo, cuando se supera, entonces el sistema se detiene
antes de la siguiente llamada al modelo."
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from harness_agent.core.entities import Role, TokenUsage
from harness_agent.core.events import EventType
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.limits import SessionLimits
from harness_agent.core.loop import AgentLoop, TurnStatus
from tests.core.support import SESSION, Rig, call, make_rig
from tests.doubles import FailingEventBus, RecordingTool


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _calls(count: int, usage: TokenUsage | None = None) -> list[ProviderResponse | BaseException]:
    """A provider that keeps asking for the tool ``t`` ``count`` times."""
    return [
        ProviderResponse(content="", tool_calls=[call(f"c{i}", "t")], usage=usage)
        for i in range(count)
    ]


def _rig(
    script: list[ProviderResponse | BaseException],
    limits: SessionLimits | None,
    clock: FakeClock | None = None,
    tool: RecordingTool | None = None,
) -> Rig:
    rig = make_rig(script, [tool or RecordingTool("t", content="ok")])
    rig.loop = AgentLoop(
        rig.provider, rig.registry, rig.policy, rig.bus, limits=limits, clock=clock
    )
    return rig


def _limit_events(rig: Rig) -> list[dict[str, Any]]:
    return [
        dict(event.payload)
        for event in rig.recording_bus.emitted_events
        if event.type is EventType.LIMIT_REACHED
    ]


class TestTurnLimit:
    async def test_the_loop_stops_after_exactly_n_calls_to_the_model(self) -> None:
        rig = _rig(_calls(10), SessionLimits(max_turns=3, max_seconds=999, max_tokens=999_999))
        result = await rig.run("go")
        assert result.status is TurnStatus.LIMIT_REACHED
        assert rig.provider.call_count == 3
        assert result.final_response is None
        assert result.error is not None and "turns" in result.error

    async def test_the_history_keeps_the_task_and_adds_no_assistant_message(self) -> None:
        rig = _rig(_calls(10), SessionLimits(max_turns=1, max_seconds=999, max_tokens=999_999))
        result = await rig.run("go")
        roles = [message.role for message in result.history]
        assert roles == [Role.USER, Role.ASSISTANT, Role.TOOL]
        assert result.history[0].content == "go"

    async def test_a_task_that_ends_before_the_limit_completes_normally(self) -> None:
        script = [*_calls(1), ProviderResponse(content="done")]
        rig = _rig(script, SessionLimits(max_turns=3, max_seconds=999, max_tokens=999_999))
        result = await rig.run()
        assert result.status is TurnStatus.COMPLETED
        assert _limit_events(rig) == []

    async def test_the_last_allowed_call_may_still_complete(self) -> None:
        script = [ProviderResponse(content="done")]
        rig = _rig(script, SessionLimits(max_turns=1, max_seconds=999, max_tokens=999_999))
        assert (await rig.run()).status is TurnStatus.COMPLETED

    async def test_an_exhausted_session_keeps_stopping_the_next_tasks(self) -> None:
        rig = _rig(_calls(10), SessionLimits(max_turns=2, max_seconds=999, max_tokens=999_999))
        await rig.run("first")
        calls_after_first = rig.provider.call_count
        second = await rig.run("second")
        assert second.status is TurnStatus.LIMIT_REACHED
        assert rig.provider.call_count == calls_after_first
        assert [m.content for m in second.history if m.role is Role.USER] == ["first", "second"]
        assert len(_limit_events(rig)) == 2

    async def test_without_limits_nothing_is_applied(self) -> None:
        rig = _rig([*_calls(40), ProviderResponse(content="done")], None)
        result = await rig.run()
        assert result.status is TurnStatus.COMPLETED
        assert rig.provider.call_count == 41


class TestTokenLimit:
    async def test_the_loop_stops_before_the_next_call_once_the_budget_is_used(self) -> None:
        usage = TokenUsage(input_tokens=40, output_tokens=10)
        rig = _rig(_calls(10, usage), SessionLimits(max_turns=99, max_seconds=999, max_tokens=100))
        result = await rig.run()
        assert result.status is TurnStatus.LIMIT_REACHED
        assert rig.provider.call_count == 2
        assert _limit_events(rig) == [{"limit": "tokens", "used": 100, "maximum": 100}]

    async def test_the_response_that_went_over_the_budget_is_kept_and_its_tools_run(self) -> None:
        tool = RecordingTool("t", content="ok")
        usage = TokenUsage(input_tokens=500, output_tokens=0)
        rig = _rig(_calls(5, usage), SessionLimits(99, 999, 100), tool=tool)
        result = await rig.run()
        assert result.status is TurnStatus.LIMIT_REACHED
        assert rig.provider.call_count == 1
        assert len(tool.executions) == 1
        assert result.history[-1].role is Role.TOOL

    async def test_a_response_without_usage_does_not_break_the_loop(self) -> None:
        rig = _rig(_calls(3, None), SessionLimits(max_turns=2, max_seconds=999, max_tokens=1))
        result = await rig.run()
        assert result.status is TurnStatus.LIMIT_REACHED
        assert _limit_events(rig)[0]["limit"] == "turns"


class TestTimeLimit:
    async def test_the_loop_stops_when_the_task_took_the_maximum_time(self) -> None:
        clock = FakeClock()

        class SlowTool(RecordingTool):
            async def run(self, args: dict[str, Any]) -> Any:
                clock.now += 6
                return await super().run(args)

        rig = _rig(_calls(10), SessionLimits(99, 10, 999_999), clock, SlowTool("t", content="ok"))
        result = await rig.run()
        assert result.status is TurnStatus.LIMIT_REACHED
        assert rig.provider.call_count == 2
        assert _limit_events(rig) == [{"limit": "time", "used": 12, "maximum": 10}]

    async def test_the_wait_between_tasks_does_not_count(self) -> None:
        clock = FakeClock()
        script = [ProviderResponse(content="a"), ProviderResponse(content="b")]
        rig = _rig(script, SessionLimits(99, 10, 999_999), clock)
        assert (await rig.run("one")).status is TurnStatus.COMPLETED
        clock.now += 10_000
        assert (await rig.run("two")).status is TurnStatus.COMPLETED

    async def test_a_cancelled_task_still_adds_its_time(self) -> None:
        clock = FakeClock()
        limits = SessionLimits(99, 10, 999_999)
        rig = make_rig([ProviderResponse(content="never")], [RecordingTool("t")], block_on_call=0)
        rig.loop = AgentLoop(
            rig.provider, rig.registry, rig.policy, rig.bus, limits=limits, clock=clock
        )
        task = asyncio.ensure_future(
            rig.loop.run_turn(session_id=SESSION, task="x", history=rig.history)
        )
        await asyncio.wait_for(rig.provider.blocked.wait(), 5)
        clock.now += 20
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # The 20 s of the cancelled task are already spent for the rest of the session.
        result = await rig.loop.run_turn(session_id=SESSION, task="z", history=[])
        assert result.status is TurnStatus.LIMIT_REACHED
        assert _limit_events(rig)[-1]["limit"] == "time"


class TestEvent:
    async def test_one_event_with_only_the_limit_used_and_maximum(self) -> None:
        rig = _rig(_calls(10), SessionLimits(max_turns=2, max_seconds=999, max_tokens=999_999))
        await rig.run()
        assert _limit_events(rig) == [{"limit": "turns", "used": 2, "maximum": 2}]

    async def test_the_event_is_published_before_the_result_returns(self) -> None:
        rig = _rig(_calls(10), SessionLimits(max_turns=1, max_seconds=999, max_tokens=999_999))
        await rig.run()
        types = [event.type for event in rig.recording_bus.emitted_events]
        assert types[-1] is EventType.LIMIT_REACHED

    async def test_a_failing_bus_propagates_the_error(self) -> None:
        limits = SessionLimits(max_turns=1, max_seconds=999, max_tokens=999_999)
        rig = _rig(_calls(5), limits)
        bus = FailingEventBus(fail_on={EventType.LIMIT_REACHED})
        rig.loop = AgentLoop(rig.provider, rig.registry, rig.policy, bus, limits=limits)
        with pytest.raises(RuntimeError, match="event bus failure"):
            await rig.run()
        assert bus.failed_attempts == [EventType.LIMIT_REACHED]
