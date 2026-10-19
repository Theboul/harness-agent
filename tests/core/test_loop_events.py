"""Event publication order, payloads and the Q4 rule of the agentic loop (HU-01-01, US4, T017).

Q4 (approved by the PO): an exception raised by ``EventBus.emit`` propagates and stops the
loop. It is never converted into a ToolResult, never retried, and never lets a later tool run.
This is deliberately different from an isolated subscriber failure (HU-01-05, owned by B),
a tool failure, a provider failure and a cancellation.
"""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.core.entities import Role
from harness_agent.core.events import Event, EventType
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.interfaces.security import PermissionDecision
from harness_agent.core.loop import TurnStatus
from tests.core.support import call, make_rig, response
from tests.doubles import FailingEventBus, RecordingTool

ET = EventType


def _types(events: list[Event]) -> list[EventType]:
    return [event.type for event in events]


def _three_step_rig() -> Any:
    tools = [RecordingTool(f"step_{i}", content=f"r{i}") for i in (1, 2, 3)]
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "step_1", secret="TOPSECRET-1")),
        response(call("c2", "step_2")),
        response(call("c3", "step_3")),
        ProviderResponse(content="all done"),
    ]
    return make_rig(script, list(tools))


async def test_event_sequence_of_a_three_step_turn() -> None:
    rig = _three_step_rig()

    result = await rig.run("start")

    assert result.status is TurnStatus.COMPLETED
    per_call = [ET.TOOL_REQUESTED, ET.PERMISSION_DECIDED, ET.TOOL_FINISHED]
    assert _types(rig.recording_bus.emitted_events) == [
        ET.USER_MESSAGE,
        *per_call,
        *per_call,
        *per_call,
        ET.ASSISTANT_MESSAGE,
    ]


async def test_assistant_text_is_published_before_the_requests_of_its_calls() -> None:
    tool = RecordingTool("step_1")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "step_1"), content="thinking"),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool])

    await rig.run()

    events = rig.recording_bus.emitted_events
    assert _types(events)[:3] == [ET.USER_MESSAGE, ET.ASSISTANT_MESSAGE, ET.TOOL_REQUESTED]
    assert events[1].payload == {"content": "thinking", "tool_call_count": 1, "final": False}
    assert events[-1].payload == {"content": "done", "tool_call_count": 0, "final": True}


async def test_payloads_follow_the_contract_and_carry_no_tool_arguments() -> None:
    rig = _three_step_rig()

    await rig.run("start")

    events = rig.recording_bus.emitted_events
    assert events[0].payload == {"content": "start"}
    assert events[0].session_id == "session-1"
    assert events[1].payload == {"call_id": "c1", "name": "step_1"}
    assert events[2].payload == {
        "call_id": "c1",
        "name": "step_1",
        "decision": "allow",
        "resolved_as": "allow",
        "reason": None,
    }
    assert events[3].payload == {
        "call_id": "c1",
        "name": "step_1",
        "is_error": False,
        "category": "ok",
    }
    assert "TOPSECRET-1" not in repr([event.payload for event in events])


async def test_rejections_publish_the_right_decision_and_category() -> None:
    tools = [RecordingTool("denied"), RecordingTool("asked"), RecordingTool("broken_policy")]
    script: list[ProviderResponse | BaseException] = [
        response(
            call("a", "denied"),
            call("b", "asked"),
            call("c", "broken_policy"),
            call("d", "ghost"),
        ),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(
        script,
        tools,
        decisions={
            "denied": PermissionDecision.DENY,
            "asked": PermissionDecision.ASK,
            "broken_policy": RuntimeError("policy crashed"),
        },
    )

    await rig.run()

    events = rig.recording_bus.emitted_events
    decided = [e.payload for e in events if e.type is ET.PERMISSION_DECIDED]
    assert [(p["call_id"], p["decision"], p["resolved_as"], p["reason"]) for p in decided] == [
        ("a", "deny", "deny", None),
        ("b", "ask", "deny", None),
        ("c", "deny", "deny", "policy_error"),
    ]
    finished = {
        e.payload["call_id"]: e.payload["category"] for e in events if e.type is ET.TOOL_FINISHED
    }
    assert finished == {
        "a": "permission_denied",
        "b": "approval_required_unavailable",
        "c": "permission_denied",
        "d": "unknown_tool",
    }
    # The unknown tool never reached the policy.
    assert [e.payload["call_id"] for e in events if e.type is ET.PERMISSION_DECIDED] == [
        "a",
        "b",
        "c",
    ]


async def test_limit_and_approval_events_are_never_published() -> None:
    rig = _three_step_rig()
    await rig.run("start")
    asked = make_rig(
        [response(call("a", "t")), ProviderResponse(content="x")],
        [RecordingTool("t")],
        decisions={"t": PermissionDecision.ASK},
    )
    await asked.run()

    forbidden = {ET.LIMIT_REACHED, ET.APPROVAL_REQUESTED, ET.APPROVAL_RESOLVED}
    for scenario in (rig, asked):
        assert not forbidden & set(_types(scenario.recording_bus.emitted_events))


async def test_the_core_never_prints(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rig = _three_step_rig()

    await rig.run("start")

    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


# ------------------------------------------------------------------------------ Q4


def _q4_rig(fail_on: ET) -> Any:
    first, second = RecordingTool("first"), RecordingTool("second")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "first"), call("c2", "second"), content="thinking"),
        ProviderResponse(content="done"),
    ]
    bus = FailingEventBus({fail_on})
    rig = make_rig(script, [first, second], bus=bus)
    return rig, bus, first, second


@pytest.mark.parametrize(
    "fail_on",
    [ET.USER_MESSAGE, ET.ASSISTANT_MESSAGE, ET.TOOL_REQUESTED, ET.PERMISSION_DECIDED],
)
async def test_q4_emit_failure_before_execution_propagates_and_runs_no_tool(fail_on: ET) -> None:
    rig, bus, first, second = _q4_rig(fail_on)

    with pytest.raises(RuntimeError, match="event bus failure") as raised:
        await rig.run()

    assert raised.value is bus.error
    assert bus.failed_attempts == [fail_on]  # a single attempt: no retry
    assert first.executions == [] and second.executions == []
    assert not any(m.role is Role.TOOL for m in rig.history)  # no fabricated ToolResult


async def test_q4_emit_failure_after_execution_does_not_repeat_or_continue() -> None:
    rig, bus, first, second = _q4_rig(ET.TOOL_FINISHED)

    with pytest.raises(RuntimeError, match="event bus failure"):
        await rig.run()

    assert bus.failed_attempts == [ET.TOOL_FINISHED]
    assert len(first.executions) == 1  # already ran once: no rollback, no repetition
    assert second.executions == []  # later calls do not run
    tool_messages = [m for m in rig.history if m.role is Role.TOOL]
    assert [m.tool_result.call_id for m in tool_messages if m.tool_result] == ["c1"]
    assert rig.provider.call_count == 1


async def test_without_subscribers_the_result_is_identical() -> None:
    plain = _three_step_rig()
    subscribed = _three_step_rig()
    seen: list[Event] = []
    for event_type in ET:
        subscribed.recording_bus.subscribe(event_type, seen.append)

    first = await plain.run("start")
    second = await subscribed.run("start")

    assert first.status == second.status and first.final_response == second.final_response
    assert first.history == second.history
    assert len(seen) == len(subscribed.recording_bus.emitted_events) > 0
