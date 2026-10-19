"""Pin the real contract signatures consumed by the agentic loop (HU-01-01, T001).

The loop (``harness_agent.core.loop``) consumes existing shared contracts without
changing them. These tests fail loudly if any of those signatures drift, so the
loop design in ``specs/005-basic-agent-loop/plan.md`` stays aligned with the code.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing

from harness_agent.core.entities import ToolCall
from harness_agent.core.events import Event, EventType
from harness_agent.core.interfaces.event_bus import EventBus
from harness_agent.core.interfaces.provider import Provider, ProviderResponse
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy
from harness_agent.core.interfaces.tool import Tool, ToolRegistry

LOOP_EVENT_TYPES = {
    "USER_MESSAGE",
    "ASSISTANT_MESSAGE",
    "TOOL_REQUESTED",
    "PERMISSION_DECIDED",
    "TOOL_FINISHED",
    "PROVIDER_ERROR",
    "INTERRUPTED",
}


def _params(func: typing.Callable[..., object]) -> list[str]:
    return [name for name in inspect.signature(func).parameters if name != "self"]


def test_provider_complete_is_async_with_messages_and_tools() -> None:
    assert inspect.iscoroutinefunction(Provider.complete)
    assert _params(Provider.complete) == ["messages", "tools"]
    hints = typing.get_type_hints(Provider.complete)
    assert hints["return"] is ProviderResponse


def test_tool_run_is_async_and_takes_args() -> None:
    assert inspect.iscoroutinefunction(Tool.run)
    assert _params(Tool.run) == ["args"]


def test_registry_methods_are_synchronous_with_expected_parameters() -> None:
    for method in (ToolRegistry.get, ToolRegistry.list, ToolRegistry.validate_args):
        assert not inspect.iscoroutinefunction(method)
    assert _params(ToolRegistry.get) == ["name"]
    assert _params(ToolRegistry.list) == []
    assert _params(ToolRegistry.validate_args) == ["name", "args"]
    hints = typing.get_type_hints(ToolRegistry.validate_args)
    assert typing.get_origin(hints["return"]) is dict


def test_policy_evaluate_is_synchronous_and_returns_decision() -> None:
    assert not inspect.iscoroutinefunction(PermissionPolicy.evaluate)
    assert _params(PermissionPolicy.evaluate) == ["call"]
    assert typing.get_type_hints(PermissionPolicy.evaluate)["return"] is PermissionDecision


def test_event_bus_emit_is_synchronous() -> None:
    assert not inspect.iscoroutinefunction(EventBus.emit)
    assert _params(EventBus.emit) == ["event"]


def test_event_catalog_has_17_members_including_those_used_by_the_loop() -> None:
    names = {member.name for member in EventType}
    assert len(names) == 17
    assert LOOP_EVENT_TYPES <= names


def test_tool_call_is_frozen_but_arguments_dict_is_mutable() -> None:
    assert dataclasses.is_dataclass(ToolCall)
    call = ToolCall(id="c1", name="t", arguments={"a": 1})
    try:
        call.id = "other"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("ToolCall must be frozen")
    call.arguments["a"] = 2  # frozen does not protect the inner dict (R-07)
    assert call.arguments == {"a": 2}


def test_event_create_factory_builds_events_with_session_and_payload() -> None:
    event = Event.create("s1", EventType.USER_MESSAGE, {"content": "hi"})
    assert event.session_id == "s1"
    assert event.type is EventType.USER_MESSAGE
    assert event.payload == {"content": "hi"}
