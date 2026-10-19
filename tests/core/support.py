"""Shared builders for the agentic loop tests (HU-01-01).

Keeps the per-scenario tests short: a ``Rig`` wires an ``AgentLoop`` to the scripted test
doubles. Nothing here touches the network or the console.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from harness_agent.core.entities import Message, ToolCall
from harness_agent.core.interfaces.event_bus import EventBus
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.interfaces.security import PermissionDecision
from harness_agent.core.interfaces.tool import Tool
from harness_agent.core.loop import AgentLoop, TurnResult
from tests.doubles import (
    InMemoryToolRegistry,
    RecordingEventBus,
    ScriptedPolicy,
    ScriptedProvider,
    run_bounded,
)

SESSION = "session-1"


def call(call_id: str, name: str, **arguments: Any) -> ToolCall:
    """Build a ToolCall with keyword arguments."""
    return ToolCall(id=call_id, name=name, arguments=dict(arguments))


def response(*calls: ToolCall, content: str = "") -> ProviderResponse:
    """Build a ProviderResponse requesting the given calls."""
    return ProviderResponse(content=content, tool_calls=list(calls))


@dataclass
class Rig:
    """An AgentLoop wired to scripted doubles, plus the doubles for assertions."""

    loop: AgentLoop
    provider: ScriptedProvider
    registry: InMemoryToolRegistry
    policy: ScriptedPolicy
    bus: EventBus
    history: list[Message]

    @property
    def recording_bus(self) -> RecordingEventBus:
        assert isinstance(self.bus, RecordingEventBus)
        return self.bus

    async def run(self, task: str = "do the task", *, timeout: float = 5.0) -> TurnResult:
        """Run one bounded turn over this rig's history."""
        return await run_bounded(
            self.loop.run_turn(session_id=SESSION, task=task, history=self.history),
            provider=self.provider,
            timeout=timeout,
        )


def make_rig(
    script: list[ProviderResponse | BaseException],
    tools: Sequence[Tool],
    *,
    decisions: dict[str, Any] | None = None,
    normalizer: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    bus: EventBus | None = None,
    registry: InMemoryToolRegistry | None = None,
    policy: ScriptedPolicy | None = None,
    history: list[Message] | None = None,
    allow_invalid_ids: bool = False,
    block_on_call: int | None = None,
) -> Rig:
    """Wire a loop. By default every registered tool is ALLOWed (an explicit test choice)."""
    provider = ScriptedProvider(
        script, allow_invalid_ids=allow_invalid_ids, block_on_call=block_on_call
    )
    registry = registry or InMemoryToolRegistry(list(tools), normalizer=normalizer)
    policy = policy or ScriptedPolicy(
        decisions
        if decisions is not None
        else {tool.name: PermissionDecision.ALLOW for tool in tools}
    )
    bus = bus if bus is not None else RecordingEventBus()
    return Rig(
        loop=AgentLoop(provider, registry, policy, bus),
        provider=provider,
        registry=registry,
        policy=policy,
        bus=bus,
        history=history if history is not None else [],
    )
