"""Sanity tests for the loop-specific test doubles (HU-01-01, T002-T004).

The doubles are not HU-00-03/HU-01-02/HU-01-05/HU-05-01; these tests only prove they
honor the real abstract contracts and the safety defaults the loop tests rely on.
"""

from __future__ import annotations

import asyncio

import pytest

from harness_agent.core.entities import ToolCall
from harness_agent.core.events import Event, EventType
from harness_agent.core.interfaces.event_bus import EventBus
from harness_agent.core.interfaces.provider import Provider, ProviderResponse
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy
from harness_agent.core.interfaces.tool import Tool, ToolRegistry
from tests.doubles import (
    BlockingTool,
    FailingEventBus,
    FailingTool,
    InMemoryToolRegistry,
    RaisingTool,
    RecordingTool,
    ScriptedPolicy,
    ScriptedProvider,
    ScriptExhausted,
    run_bounded,
)


def test_doubles_satisfy_the_real_abstract_contracts() -> None:
    assert isinstance(ScriptedProvider([]), Provider)
    assert isinstance(InMemoryToolRegistry(), ToolRegistry)
    assert isinstance(ScriptedPolicy(), PermissionPolicy)
    assert isinstance(FailingEventBus(set()), EventBus)
    for tool in (RecordingTool(), FailingTool(), RaisingTool(), BlockingTool()):
        assert isinstance(tool, Tool)


async def test_scripted_provider_replays_then_fails_explicitly_when_exhausted() -> None:
    provider = ScriptedProvider([ProviderResponse(content="done")])
    first = await provider.complete([])
    assert first.content == "done"
    with pytest.raises(ScriptExhausted):
        await provider.complete([])
    assert provider.exhausted is True
    with pytest.raises(AssertionError, match="exhausted"):
        await run_bounded(asyncio.sleep(0), provider=provider)


async def test_scripted_provider_records_copies_of_received_messages() -> None:
    provider = ScriptedProvider([ProviderResponse(content="x")])
    messages: list[object] = []
    await provider.complete(messages)  # type: ignore[arg-type]
    messages.append("later mutation")
    assert provider.received == [[]]


def test_scripted_provider_rejects_invalid_ids_unless_explicitly_allowed() -> None:
    duplicate = [
        ProviderResponse(tool_calls=[ToolCall("c1", "t")]),
        ProviderResponse(tool_calls=[ToolCall("c1", "t")]),
    ]
    with pytest.raises(ValueError, match="unique"):
        ScriptedProvider(list(duplicate))
    with pytest.raises(ValueError, match="non-empty"):
        ScriptedProvider([ProviderResponse(tool_calls=[ToolCall("", "t")])])
    ScriptedProvider(list(duplicate), allow_invalid_ids=True)


async def test_run_bounded_times_out_on_an_endless_await() -> None:
    with pytest.raises(TimeoutError):
        await run_bounded(asyncio.Event().wait(), timeout=0.05)


def test_scripted_policy_defaults_to_deny_and_records_calls() -> None:
    policy = ScriptedPolicy({"known": PermissionDecision.ALLOW})
    unknown = ToolCall("c1", "unmapped")
    assert policy.evaluate(unknown) is PermissionDecision.DENY
    assert policy.evaluate(ToolCall("c2", "known")) is PermissionDecision.ALLOW
    assert [call.id for call in policy.received] == ["c1", "c2"]


def test_in_memory_registry_does_not_mutate_input_and_can_normalize() -> None:
    tool = RecordingTool("t")
    registry = InMemoryToolRegistry(
        [tool], normalizer=lambda _name, args: {**args, "normalized": True}
    )
    original = {"a": 1}
    effective = registry.validate_args("t", original)
    assert original == {"a": 1}
    assert effective == {"a": 1, "normalized": True}
    assert registry.get("t") is tool and registry.get("missing") is None


def test_failing_bus_raises_only_for_configured_types_and_counts_attempts() -> None:
    bus = FailingEventBus({EventType.TOOL_FINISHED})
    bus.emit(Event.create("s", EventType.USER_MESSAGE))
    with pytest.raises(RuntimeError):
        bus.emit(Event.create("s", EventType.TOOL_FINISHED))
    assert bus.failed_attempts == [EventType.TOOL_FINISHED]
    assert [event.type for event in bus.emitted_events] == [EventType.USER_MESSAGE]
