"""Runs one shell command under the permission policy of the session (HU-11-08.2).

The call has the shape of a shell call of the agent (same tool name and arguments), so every
wrapper of the policy chain decides the same way: ``DENY`` never runs and never reaches the
approver, ``ASK`` goes to the approval gate and, with none, does not run; an error or an unknown
answer of the policy is ``DENY`` (fail closed). The events are the ones of the catalog.
Cancellation is never caught.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from harness_agent.core.entities import ToolCall
from harness_agent.core.events import EventType
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy
from harness_agent.core.interfaces.tool import Tool
from harness_agent.core.permissions.approvals import ApprovalGate
from harness_agent.core.verification.outcomes import CommandOutcome, CommandRunner

Emit = Callable[[EventType, dict[str, Any]], None]


class RunStatus(str, Enum):
    """RAN: the command ran; the others say why it did not."""

    RAN = "ejecutado"
    DENIED = "denegado"
    NO_APPROVER = "sin_aprobador"
    NOT_APPROVED = "no_aprobado"
    ERROR = "error"


@dataclass(frozen=True)
class GatedResult:
    """The outcome is ``None`` unless the status is ``RAN``."""

    status: RunStatus
    outcome: CommandOutcome | None = None


class GatedCommandRunner:
    """Policy, then approval, then execution of one shell command.

    Args:
        policy: The permission policy of the session (the same chain the agent loop uses).
        tool: The shell tool, only to describe the request to the approver.
        run: Runs the call of the shell tool and says what happened.
        emit: Publishes an event for the session.
        gate: Asks the person when the policy asks; ``None`` means nothing that is asked runs.
        tool_name: Name of the shell tool, as the policy knows it.
        command_argument: Name of its argument with the command text.
        timeout_argument: Name of its argument with the time limit.
    """

    def __init__(
        self,
        policy: PermissionPolicy,
        tool: Tool,
        run: CommandRunner,
        emit: Emit,
        *,
        gate: ApprovalGate | None,
        tool_name: str,
        command_argument: str,
        timeout_argument: str,
    ) -> None:
        self._policy = policy
        self._tool = tool
        self._run = run
        self._emit = emit
        self._gate = gate
        self._tool_name = tool_name
        self._command_argument = command_argument
        self._timeout_argument = timeout_argument

    async def run(self, call_id: str, command: str, timeout_seconds: int | None) -> GatedResult:
        """Run ``command`` if the policy (and the person, when asked) allow it."""
        arguments: dict[str, Any] = {self._command_argument: command}
        if timeout_seconds is not None:
            arguments[self._timeout_argument] = timeout_seconds
        call = ToolCall(id=call_id, name=self._tool_name, arguments=arguments)
        refused = await self._permission(call)
        if refused is not None:
            return GatedResult(refused)
        try:
            outcome: object = await self._run(call)
        except Exception:
            return GatedResult(RunStatus.ERROR)
        if not isinstance(outcome, CommandOutcome):
            return GatedResult(RunStatus.ERROR)
        return GatedResult(RunStatus.RAN, outcome)

    async def _permission(self, call: ToolCall) -> RunStatus | None:
        try:
            decision: object = self._policy.evaluate(call)
        except Exception:
            decision = None
        if decision is PermissionDecision.ALLOW:
            self._decided(call, "allow", "allow", None)
            return None
        if decision is PermissionDecision.ASK:
            gate = self._gate
            self._decided(call, "ask", "ask" if gate is not None else "deny", None)
            if gate is None:
                return RunStatus.NO_APPROVER
            return await self._ask(gate, call)
        reason = None if decision is PermissionDecision.DENY else "policy_error"
        self._decided(call, "deny", "deny", reason)
        return RunStatus.DENIED

    async def _ask(self, gate: ApprovalGate, call: ToolCall) -> RunStatus | None:
        outcome = await gate.resolve(
            call,
            self._tool,
            lambda risk: self._emit(
                EventType.APPROVAL_REQUESTED,
                {"call_id": call.id, "name": call.name, "risk": risk},
            ),
        )
        action = None if outcome.action is None else outcome.action.value
        self._emit(
            EventType.APPROVAL_RESOLVED,
            {
                "call_id": call.id,
                "name": call.name,
                "action": action,
                "approved": outcome.approved,
                "source": outcome.source,
            },
        )
        return None if outcome.approved else RunStatus.NOT_APPROVED

    def _decided(self, call: ToolCall, decision: str, resolved_as: str, reason: str | None) -> None:
        self._emit(
            EventType.PERMISSION_DECIDED,
            {
                "call_id": call.id,
                "name": call.name,
                "decision": decision,
                "resolved_as": resolved_as,
                "reason": reason,
            },
        )
