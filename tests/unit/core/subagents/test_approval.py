"""The approvals of a subagent go up to the person saying who asks (HU-09-03 / T003)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from harness_agent.core import ApprovalAction, ApprovalResult, Approver, ToolCall
from harness_agent.core.subagents.approval import REQUESTER_KEY, SubagentApprover, requester_label
from tests.doubles import DummyApprover

CALL = ToolCall("c1", "shell", {"command": "ls"})


def test_the_label_names_the_subagent_by_the_start_of_its_session() -> None:
    assert requester_label("abcdefgh-ijkl-mnop") == "subagente abcdefgh"
    assert requester_label("corto") == "subagente corto"


async def test_the_request_reaches_the_person_with_who_asks_and_everything_else() -> None:
    inner = DummyApprover(ApprovalAction.APPROVE_SESSION)
    approver = SubagentApprover(inner, "subagente abcdefgh")
    details: dict[str, Any] = {"tool": "shell", "risk": "high", "effect": "Ejecuta"}

    result = await approver.request(CALL, details)

    assert result == ApprovalResult(ApprovalAction.APPROVE_SESSION)
    asked_call, asked_details = inner.recorded_requests[0]
    assert asked_call == CALL
    assert asked_details == {**details, REQUESTER_KEY: "subagente abcdefgh"}
    assert REQUESTER_KEY not in details  # the original is not touched


async def test_the_decision_and_the_reason_of_the_person_come_back_as_they_are() -> None:
    inner = DummyApprover(ApprovalAction.REJECT, "no gracias")

    result = await SubagentApprover(inner, "subagente x").request(CALL, {})

    assert result == ApprovalResult(ApprovalAction.REJECT, "no gracias")


async def test_a_failure_of_the_person_side_goes_up_for_the_gate_to_deny() -> None:
    class Broken(Approver):
        async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
            raise RuntimeError("sin terminal")

    with pytest.raises(RuntimeError):
        await SubagentApprover(Broken(), "subagente x").request(CALL, {})


async def test_a_cancellation_goes_up() -> None:
    class Cancelling(Approver):
        async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await SubagentApprover(Cancelling(), "subagente x").request(CALL, {})


def test_the_approver_is_an_approver() -> None:
    assert isinstance(SubagentApprover(DummyApprover(), "subagente x"), Approver)
