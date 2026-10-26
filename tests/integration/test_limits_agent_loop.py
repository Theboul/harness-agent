"""Session limits through the real loop, bus and terminal render (HU-01-06 / T011).

AC-01 and AC-02 end to end: the loop stops, the event is published and the user reads why.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from harness_agent.cli import attach_renderer
from harness_agent.core import (
    EventType,
    InMemoryEventBus,
    InMemoryToolRegistry,
    SessionLimits,
    TokenUsage,
    ToolCall,
    ToolResult,
)
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.interfaces.security import PermissionDecision
from harness_agent.core.loop import AgentLoop, TurnStatus
from tests.doubles import FakeProvider, RecordingTool, ScriptedPolicy

SESSION = "sesion-limites"


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class SlowTool(RecordingTool):
    def __init__(self, clock: Clock) -> None:
        super().__init__("t", content="ok")
        self._clock = clock

    async def run(self, args: dict[str, Any]) -> ToolResult:
        self._clock.now += 7
        return await super().run(args)


def endless(count: int, tokens: int = 0) -> FakeProvider:
    usage = TokenUsage(input_tokens=tokens, output_tokens=0) if tokens else None
    return FakeProvider(
        [
            ProviderResponse(tool_calls=[ToolCall(f"c{i}", "t", {})], usage=usage)
            for i in range(count)
        ]
    )


def build(
    provider: FakeProvider, limits: SessionLimits, clock: Clock | None = None
) -> tuple[AgentLoop, io.StringIO, list[Any]]:
    tool = SlowTool(clock) if clock is not None else RecordingTool("t", content="ok")
    registry = InMemoryToolRegistry()
    registry.register(tool)
    policy = ScriptedPolicy({"t": PermissionDecision.ALLOW})
    bus = InMemoryEventBus()
    screen = io.StringIO()
    attach_renderer(bus, screen)
    events: list[Any] = []
    for event_type in EventType:
        bus.subscribe(event_type, events.append)
    loop = AgentLoop(provider, registry, policy, bus, limits=limits, clock=clock)
    return loop, screen, events


@pytest.mark.parametrize(
    ("limits", "tokens", "use_clock", "expected_call_count", "words"),
    [
        (SessionLimits(3, 999, 999_999), 0, False, 3, "máximo de 3 turnos"),
        (SessionLimits(99, 999, 100), 60, False, 2, "presupuesto de 100 tokens"),
        (SessionLimits(99, 10, 999_999), 0, True, 2, "tiempo máximo de 10 segundos"),
    ],
)
async def test_each_limit_stops_the_loop_and_tells_the_user_why(
    limits: SessionLimits,
    tokens: int,
    use_clock: bool,
    expected_call_count: int,
    words: str,
) -> None:
    clock = Clock() if use_clock else None
    provider = endless(10, tokens)
    loop, screen, events = build(provider, limits, clock)

    result = await loop.run_turn(session_id=SESSION, task="hazlo", history=[])

    assert result.status is TurnStatus.LIMIT_REACHED
    assert provider.call_count == expected_call_count
    assert [e.type.value for e in events].count("limit_reached") == 1
    assert words in screen.getvalue()


async def test_after_the_stop_the_user_gets_control_and_the_next_task_stops_too() -> None:
    provider = endless(10)
    loop, screen, _ = build(provider, SessionLimits(2, 999, 999_999))
    history: list[Any] = []

    first = await loop.run_turn(session_id=SESSION, task="uno", history=history)
    second = await loop.run_turn(session_id=SESSION, task="dos", history=history)

    assert first.status is second.status is TurnStatus.LIMIT_REACHED
    assert provider.call_count == 2
    assert screen.getvalue().count("Límite:") == 2
