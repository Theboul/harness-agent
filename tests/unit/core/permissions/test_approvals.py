"""ApprovalGate: one-time approval, rejection, session scope and fail-closed behavior (HU-05-03)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from harness_agent.core import (
    ApprovalAction,
    ApprovalGate,
    ApprovalOutcome,
    ApprovalResult,
    Approver,
    RiskLevel,
    ToolCall,
)
from tests.doubles import DummyApprover, DummyTool

SENTINEL = "VALOR-DE-PRUEBA-123"


class RaisingApprover(Approver):
    def __init__(self, error: BaseException) -> None:
        self._error = error

    async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
        raise self._error


class WrongResultApprover(Approver):
    def __init__(self, result: object) -> None:
        self._result = result

    async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
        return self._result  # type: ignore[return-value]


class ScriptedApprover(Approver):
    """Answers one scripted action per request and records what it was asked."""

    def __init__(self, *actions: ApprovalAction) -> None:
        self._actions = list(actions)
        self.requests: list[tuple[ToolCall, dict[str, Any]]] = []

    async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
        self.requests.append((call, details))
        return ApprovalResult(self._actions.pop(0))


def make_call(name: str = "shell", **arguments: Any) -> ToolCall:
    return ToolCall(id="call-1", name=name, arguments=dict(arguments))


def make_tool(name: str = "shell") -> DummyTool:
    return DummyTool(name=name, description="Runs a command", risk=RiskLevel.HIGH)


def noop(risk: str) -> None:
    return None


async def resolve(
    gate: ApprovalGate,
    call: ToolCall,
    tool: DummyTool | None = None,
    emit: Callable[[str], None] = noop,
) -> ApprovalOutcome:
    return await gate.resolve(call, tool or make_tool(call.name), emit)


class TestConstruction:
    def test_requires_an_approver(self) -> None:
        with pytest.raises(TypeError):
            ApprovalGate(object())  # type: ignore[arg-type]


class TestOnce:
    async def test_approve_once_is_approved_and_leaves_no_trace(self) -> None:
        approver = ScriptedApprover(ApprovalAction.APPROVE_ONCE, ApprovalAction.REJECT)
        gate = ApprovalGate(approver)
        first = await resolve(gate, make_call(command="ls"))
        second = await resolve(gate, make_call(command="ls"))

        assert first == ApprovalOutcome(True, ApprovalAction.APPROVE_ONCE, "user", None)
        assert second.approved is False
        assert len(approver.requests) == 2

    async def test_the_approver_receives_the_details_and_a_copy_of_the_call(self) -> None:
        approver = DummyApprover()
        gate = ApprovalGate(approver)
        call = make_call(command="ls", options={"all": True})

        await resolve(gate, call)
        asked_call, details = approver.recorded_requests[0]

        assert details == {
            "tool": "shell",
            "arguments": {"command": "ls", "options": {"all": True}},
            "effect": "Runs a command",
            "risk": "high",
        }
        details["arguments"]["options"]["all"] = False
        asked_call.arguments["command"] = "changed"
        assert call.arguments == {"command": "ls", "options": {"all": True}}

    async def test_details_survive_a_tool_that_cannot_describe_itself(self) -> None:
        class Mute(DummyTool):
            @property
            def description(self) -> str:
                raise RuntimeError("boom")

            @property
            def risk(self) -> RiskLevel:
                raise RuntimeError("boom")

        approver = DummyApprover()
        await ApprovalGate(approver).resolve(make_call(), Mute(name="shell"), noop)

        details = approver.recorded_requests[0][1]
        assert details["effect"] == ""
        assert details["risk"] == "unknown"


class TestReject:
    async def test_reject_is_not_approved_and_keeps_a_bounded_reason(self) -> None:
        reason = "x" * 900
        gate = ApprovalGate(DummyApprover(ApprovalAction.REJECT, reason))

        outcome = await resolve(gate, make_call())

        assert outcome.approved is False
        assert outcome.action is ApprovalAction.REJECT
        assert outcome.source == "user"
        assert outcome.reason is not None
        assert len(outcome.reason) <= 200

    async def test_reject_without_reason_has_none(self) -> None:
        outcome = await resolve(ApprovalGate(DummyApprover(ApprovalAction.REJECT)), make_call())

        assert outcome.reason is None

    async def test_a_reason_that_is_not_text_is_dropped(self) -> None:
        gate = ApprovalGate(WrongResultApprover(ApprovalResult(ApprovalAction.REJECT, 5)))  # type: ignore[arg-type]

        outcome = await resolve(gate, make_call())

        assert outcome.approved is False
        assert outcome.reason is None


class TestFailClosed:
    async def test_an_ordinary_exception_is_a_denial_without_the_message(self) -> None:
        gate = ApprovalGate(RaisingApprover(RuntimeError(SENTINEL)))

        outcome = await resolve(gate, make_call())

        assert outcome == ApprovalOutcome(False, None, "approver_error", None)
        assert SENTINEL not in repr(outcome)

    @pytest.mark.parametrize(
        "result",
        [None, "approve_once", ApprovalAction.APPROVE_ONCE, ApprovalResult("approve_once")],  # type: ignore[arg-type]
        ids=["none", "text", "bare-action", "action-not-an-enum"],
    )
    async def test_an_invalid_result_is_a_denial(self, result: object) -> None:
        gate = ApprovalGate(WrongResultApprover(result))

        outcome = await resolve(gate, make_call())

        assert outcome == ApprovalOutcome(False, None, "invalid_result", None)

    async def test_cancellation_propagates_and_is_not_an_approval(self) -> None:
        gate = ApprovalGate(RaisingApprover(asyncio.CancelledError()))

        with pytest.raises(asyncio.CancelledError):
            await resolve(gate, make_call())

    async def test_requested_is_emitted_before_asking(self) -> None:
        order: list[str] = []

        class Recording(Approver):
            async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
                order.append("request")
                return ApprovalResult(ApprovalAction.APPROVE_ONCE)

        await resolve(
            ApprovalGate(Recording()), make_call(), emit=lambda risk: order.append("emit")
        )

        assert order == ["emit", "request"]

    async def test_a_failing_emit_means_nobody_is_asked(self) -> None:
        approver = DummyApprover()

        def failing(risk: str) -> None:
            raise RuntimeError("bus down")

        with pytest.raises(RuntimeError):
            await resolve(ApprovalGate(approver), make_call(), emit=failing)

        assert approver.recorded_requests == []


class TestSessionScope:
    async def test_approve_session_is_remembered_for_the_exact_arguments(self) -> None:
        approver = ScriptedApprover(ApprovalAction.APPROVE_SESSION)
        gate = ApprovalGate(approver)

        first = await resolve(gate, make_call(command="pip install requests"))
        second = await resolve(gate, make_call(command="pip install requests"))

        assert first == ApprovalOutcome(True, ApprovalAction.APPROVE_SESSION, "user", None)
        assert second == ApprovalOutcome(
            True, ApprovalAction.APPROVE_SESSION, "session_grant", None
        )
        assert len(approver.requests) == 1

    async def test_the_order_of_the_keys_does_not_matter(self) -> None:
        approver = ScriptedApprover(ApprovalAction.APPROVE_SESSION)
        gate = ApprovalGate(approver)

        await resolve(gate, make_call(a=1, b={"y": 2, "x": 1}))
        again = await resolve(gate, make_call(b={"x": 1, "y": 2}, a=1))

        assert again.source == "session_grant"

    async def test_other_arguments_ask_again(self) -> None:
        approver = ScriptedApprover(ApprovalAction.APPROVE_SESSION, ApprovalAction.REJECT)
        gate = ApprovalGate(approver)

        await resolve(gate, make_call(command="pip install requests"))
        other = await resolve(gate, make_call(command="pip install flask"))

        assert other.approved is False
        assert len(approver.requests) == 2

    async def test_another_tool_asks_again(self) -> None:
        approver = ScriptedApprover(ApprovalAction.APPROVE_SESSION, ApprovalAction.REJECT)
        gate = ApprovalGate(approver)

        await resolve(gate, make_call("shell", command="ls"))
        other = await resolve(gate, make_call("write_file", command="ls"))

        assert other.approved is False

    async def test_no_arguments_only_covers_no_arguments(self) -> None:
        approver = ScriptedApprover(ApprovalAction.APPROVE_SESSION, ApprovalAction.REJECT)
        gate = ApprovalGate(approver)

        await resolve(gate, make_call())
        other = await resolve(gate, make_call(command="ls"))

        assert other.approved is False

    async def test_arguments_that_cannot_be_serialized_are_approved_but_not_remembered(
        self,
    ) -> None:
        approver = ScriptedApprover(ApprovalAction.APPROVE_SESSION, ApprovalAction.REJECT)
        gate = ApprovalGate(approver)

        first = await resolve(gate, make_call(blob=object()))
        second = await resolve(gate, make_call(blob=object()))

        assert first.approved is True
        assert second.approved is False
        assert len(approver.requests) == 2

    async def test_a_session_match_still_emits_requested(self) -> None:
        gate = ApprovalGate(ScriptedApprover(ApprovalAction.APPROVE_SESSION))
        emitted: list[str] = []

        await resolve(gate, make_call(command="ls"), emit=lambda risk: emitted.append("a"))
        await resolve(gate, make_call(command="ls"), emit=lambda risk: emitted.append("b"))

        assert emitted == ["a", "b"]

    async def test_a_new_gate_does_not_inherit_the_session_approvals(self) -> None:
        await resolve(
            ApprovalGate(ScriptedApprover(ApprovalAction.APPROVE_SESSION)),
            make_call(command="ls"),
        )
        fresh = ApprovalGate(ScriptedApprover(ApprovalAction.REJECT))

        outcome = await resolve(fresh, make_call(command="ls"))

        assert outcome.approved is False
