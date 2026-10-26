"""The loop waits for the approver when the policy asks, and fails closed (HU-05-03)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from harness_agent.core import ApprovalAction, ApprovalResult, Approver, ToolCall
from harness_agent.core.entities import Role
from harness_agent.core.events import EventType
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.interfaces.security import PermissionDecision
from harness_agent.core.loop import AgentLoop, TurnStatus
from tests.core.support import SESSION, Rig, call, make_rig, response
from tests.doubles import DummyApprover, FailingEventBus, RecordingTool

ASK = PermissionDecision.ASK
SENTINEL = "VALOR-DE-PRUEBA-123"


class ScriptedApprover(Approver):
    def __init__(self, *actions: ApprovalAction | BaseException) -> None:
        self._actions = list(actions)
        self.requests: list[tuple[ToolCall, dict[str, Any]]] = []

    async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
        self.requests.append((call, details))
        action = self._actions.pop(0)
        if isinstance(action, BaseException):
            raise action
        return ApprovalResult(action)


def rig_with(
    approver: Approver | None,
    script: list[ProviderResponse | BaseException],
    tool: RecordingTool,
    decision: Any = ASK,
    bus: Any = None,
) -> Rig:
    rig = make_rig(script, [tool], decisions={tool.name: decision}, bus=bus)
    rig.loop = AgentLoop(rig.provider, rig.registry, rig.policy, rig.bus, approver=approver)
    return rig


def two_calls() -> list[ProviderResponse | BaseException]:
    return [
        response(call("c1", "act", path="a.txt"), call("c2", "act", path="a.txt")),
        ProviderResponse(content="done"),
    ]


def one_call(**arguments: Any) -> list[ProviderResponse | BaseException]:
    return [response(call("c1", "act", **arguments)), ProviderResponse(content="done")]


def tool_message(result: Any) -> Any:
    return next(m for m in result.history if m.role is Role.TOOL)


def event_types(rig: Rig) -> list[EventType]:
    return [event.type for event in rig.recording_bus.emitted_events]


class TestApproved:
    async def test_events_come_in_order_and_the_tool_runs_with_the_shown_arguments(self) -> None:
        tool = RecordingTool("act")
        approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
        rig = rig_with(approver, one_call(path="a.txt"), tool)

        result = await rig.run()

        assert result.status is TurnStatus.COMPLETED
        assert tool.executions == [{"path": "a.txt"}]
        assert approver.recorded_requests[0][1]["arguments"] == {"path": "a.txt"}
        assert event_types(rig)[:6] == [
            EventType.USER_MESSAGE,
            EventType.TOOL_REQUESTED,
            EventType.PERMISSION_DECIDED,
            EventType.APPROVAL_REQUESTED,
            EventType.APPROVAL_RESOLVED,
            EventType.TOOL_FINISHED,
        ]

    async def test_permission_decided_stays_pending_and_resolved_carries_the_decision(
        self,
    ) -> None:
        rig = rig_with(DummyApprover(), one_call(path="a.txt"), RecordingTool("act"))

        await rig.run()
        events = {e.type: e.payload for e in rig.recording_bus.emitted_events}

        assert events[EventType.PERMISSION_DECIDED]["decision"] == "ask"
        assert events[EventType.PERMISSION_DECIDED]["resolved_as"] == "ask"
        assert events[EventType.APPROVAL_REQUESTED] == {
            "call_id": "c1",
            "name": "act",
            "risk": "low",
        }
        assert events[EventType.APPROVAL_RESOLVED] == {
            "call_id": "c1",
            "name": "act",
            "action": "approve_once",
            "approved": True,
            "source": "user",
        }

    async def test_payloads_never_carry_argument_values(self) -> None:
        rig = rig_with(DummyApprover(), one_call(path=SENTINEL), RecordingTool("act"))

        await rig.run()

        for event in rig.recording_bus.emitted_events:
            if event.type in (EventType.APPROVAL_REQUESTED, EventType.APPROVAL_RESOLVED):
                assert SENTINEL not in repr(event.payload)

    async def test_two_pending_calls_are_asked_one_at_a_time_in_order(self) -> None:
        approver = ScriptedApprover(ApprovalAction.APPROVE_ONCE, ApprovalAction.REJECT)
        tool = RecordingTool("act")
        rig = rig_with(approver, two_calls(), tool)

        await rig.run()

        kinds = [
            (e.type.value, e.payload.get("call_id"))
            for e in rig.recording_bus.emitted_events
            if e.type
            in (
                EventType.APPROVAL_REQUESTED,
                EventType.APPROVAL_RESOLVED,
                EventType.TOOL_FINISHED,
            )
        ]
        assert kinds == [
            ("approval_requested", "c1"),
            ("approval_resolved", "c1"),
            ("tool_finished", "c1"),
            ("approval_requested", "c2"),
            ("approval_resolved", "c2"),
            ("tool_finished", "c2"),
        ]
        assert len(tool.executions) == 1


class TestSessionApproval:
    async def test_a_repeated_call_is_resolved_from_the_session_approval(self) -> None:
        approver = ScriptedApprover(ApprovalAction.APPROVE_SESSION)
        tool = RecordingTool("act")
        rig = rig_with(approver, two_calls(), tool)

        await rig.run()
        resolved = [
            e.payload
            for e in rig.recording_bus.emitted_events
            if e.type is EventType.APPROVAL_RESOLVED
        ]

        assert [r["source"] for r in resolved] == ["user", "session_grant"]
        assert len(approver.requests) == 1
        assert len(tool.executions) == 2

    async def test_other_arguments_are_asked_again(self) -> None:
        approver = ScriptedApprover(ApprovalAction.APPROVE_SESSION, ApprovalAction.REJECT)
        script: list[ProviderResponse | BaseException] = [
            response(call("c1", "act", path="a.txt"), call("c2", "act", path="b.txt")),
            ProviderResponse(content="done"),
        ]
        tool = RecordingTool("act")
        rig = rig_with(approver, script, tool)

        await rig.run()

        assert len(approver.requests) == 2
        assert len(tool.executions) == 1

    async def test_the_approvals_last_as_long_as_the_loop(self) -> None:
        approver = ScriptedApprover(ApprovalAction.APPROVE_SESSION)
        tool = RecordingTool("act")
        script: list[ProviderResponse | BaseException] = [
            response(call("c1", "act", path="a.txt")),
            ProviderResponse(content="first"),
            response(call("c2", "act", path="a.txt")),
            ProviderResponse(content="second"),
        ]
        rig = rig_with(approver, script, tool)

        await rig.run("first")
        await rig.run("second")

        assert len(approver.requests) == 1
        assert len(tool.executions) == 2


class TestRejectedAndFailedClosed:
    async def test_a_rejection_does_not_run_the_tool_and_tells_the_model(self) -> None:
        tool = RecordingTool("act")
        rig = rig_with(DummyApprover(ApprovalAction.REJECT, SENTINEL), one_call(path="a"), tool)

        result = await rig.run()

        assert tool.executions == []
        message = tool_message(result)
        assert message.content.startswith("[approval_rejected]")
        assert message.tool_result.is_error is True
        assert SENTINEL not in message.content
        finished = next(
            e.payload for e in rig.recording_bus.emitted_events if e.type is EventType.TOOL_FINISHED
        )
        assert finished["category"] == "approval_rejected"

    async def test_a_rejection_is_published_as_not_approved(self) -> None:
        rig = rig_with(
            DummyApprover(ApprovalAction.REJECT, SENTINEL), one_call(), RecordingTool("act")
        )

        await rig.run()
        resolved = next(
            e.payload
            for e in rig.recording_bus.emitted_events
            if e.type is EventType.APPROVAL_RESOLVED
        )

        assert resolved["approved"] is False
        assert resolved["action"] == "reject"
        assert SENTINEL not in repr(resolved)

    async def test_an_approver_failure_is_a_denial(self) -> None:
        tool = RecordingTool("act")
        rig = rig_with(ScriptedApprover(RuntimeError(SENTINEL)), one_call(), tool)

        result = await rig.run()

        assert tool.executions == []
        message = tool_message(result)
        assert message.content.startswith("[approval_failed]")
        assert SENTINEL not in message.content
        resolved = next(
            e.payload
            for e in rig.recording_bus.emitted_events
            if e.type is EventType.APPROVAL_RESOLVED
        )
        assert resolved["approved"] is False
        assert resolved["action"] is None
        assert resolved["source"] == "approver_error"

    async def test_without_an_approver_the_sprint_1_behavior_remains(self) -> None:
        tool = RecordingTool("act")
        rig = rig_with(None, one_call(), tool)

        result = await rig.run()

        assert tool.executions == []
        assert tool_message(result).content.startswith("[approval_required_unavailable]")
        assert EventType.APPROVAL_REQUESTED not in event_types(rig)
        decided = next(
            e.payload
            for e in rig.recording_bus.emitted_events
            if e.type is EventType.PERMISSION_DECIDED
        )
        assert decided["resolved_as"] == "deny"

    async def test_a_denial_never_reaches_the_approver(self) -> None:
        approver = DummyApprover(ApprovalAction.APPROVE_SESSION)
        tool = RecordingTool("act")
        rig = rig_with(approver, one_call(), tool, decision=PermissionDecision.DENY)

        result = await rig.run()

        assert approver.recorded_requests == []
        assert tool.executions == []
        assert tool_message(result).content.startswith("[permission_denied]")
        assert EventType.APPROVAL_REQUESTED not in event_types(rig)

    async def test_an_approval_is_not_asked_for_an_unknown_tool_or_invalid_arguments(self) -> None:
        approver = DummyApprover()
        script: list[ProviderResponse | BaseException] = [
            response(call("c1", "missing")),
            ProviderResponse(content="done"),
        ]
        rig = rig_with(approver, script, RecordingTool("act"))

        await rig.run()

        assert approver.recorded_requests == []


class TestCancellationAndBus:
    async def test_cancelling_while_waiting_interrupts_and_never_executes(self) -> None:
        tool = RecordingTool("act")
        rig = rig_with(ScriptedApprover(asyncio.CancelledError()), one_call(path="a"), tool)

        with pytest.raises(asyncio.CancelledError):
            await rig.loop.run_turn(session_id=SESSION, task="t", history=rig.history)

        assert tool.executions == []
        interrupted = next(
            e.payload for e in rig.recording_bus.emitted_events if e.type is EventType.INTERRUPTED
        )
        assert interrupted == {"phase": "approval", "call_id": "c1"}
        assert EventType.APPROVAL_RESOLVED not in event_types(rig)

    @pytest.mark.parametrize(
        "failing",
        [EventType.APPROVAL_REQUESTED, EventType.APPROVAL_RESOLVED],
        ids=["requested", "resolved"],
    )
    async def test_a_failing_bus_stops_the_execution(self, failing: EventType) -> None:
        tool = RecordingTool("act")
        bus = FailingEventBus({failing})
        rig = rig_with(DummyApprover(), one_call(path="a"), tool, bus=bus)

        with pytest.raises(RuntimeError):
            await rig.loop.run_turn(session_id=SESSION, task="t", history=rig.history)

        assert tool.executions == []

    async def test_when_requested_cannot_be_published_nobody_is_asked(self) -> None:
        approver = DummyApprover()
        bus = FailingEventBus({EventType.APPROVAL_REQUESTED})
        rig = rig_with(approver, one_call(path="a"), RecordingTool("act"), bus=bus)

        with pytest.raises(RuntimeError):
            await rig.loop.run_turn(session_id=SESSION, task="t", history=rig.history)

        assert approver.recorded_requests == []
