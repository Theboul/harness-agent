"""Human approval of the actions that the policy asks about (HU-05-03).

``ApprovalGate`` sits between the agent loop and the ``Approver`` port. The loop calls it only
when the policy decided ``ASK``; a denial never reaches it, so an approval (one-time or for the
session) can never override a denial.

* ``resolve`` publishes the request through the callback it receives (the gate does not know the
  bus), then either finds a matching session approval or asks the ``Approver``.
* A session approval covers one tool with exactly the same arguments (compared by their canonical
  JSON form); it lives in memory as long as the gate does.
* It fails closed: an approver that raises an ordinary exception, or answers with something that
  is not an ``ApprovalResult``, produces a denial. ``asyncio.CancelledError`` is never caught.

The user's rejection reason is kept (bounded) in the outcome so a later story can hand it to the
model; this module never publishes it.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import ApprovalAction, ApprovalResult, Approver
from harness_agent.core.interfaces.tool import Tool

MAX_REASON_CHARS = 200
SOURCE_USER = "user"
SOURCE_SESSION_GRANT = "session_grant"
SOURCE_APPROVER_ERROR = "approver_error"
SOURCE_INVALID_RESULT = "invalid_result"
UNKNOWN_RISK = "unknown"


@dataclass(frozen=True)
class ApprovalOutcome:
    """What the user (or the fail-closed rule) decided about one pending call.

    Attributes:
        approved: True only when the call may be executed.
        action: The chosen action; ``None`` when the gate failed closed.
        source: ``user``, ``session_grant``, ``approver_error`` or ``invalid_result``.
        reason: The user's rejection reason, bounded; never published.
    """

    approved: bool
    action: ApprovalAction | None
    source: str
    reason: str | None = None


def _safe(read: Callable[[], str], default: str) -> str:
    """Read a property of the tool; a tool that cannot describe itself never blocks the prompt."""
    try:
        value = read()
    except Exception:
        return default
    return value if isinstance(value, str) else default


def build_details(call: ToolCall, tool: Tool) -> dict[str, Any]:
    """What the approver shows: the tool, a copy of its arguments, its effect and its risk."""
    try:
        risk = tool.risk.value
    except Exception:
        risk = UNKNOWN_RISK
    return {
        "tool": call.name,
        "arguments": copy.deepcopy(call.arguments),
        "effect": _safe(lambda: tool.description, ""),
        "risk": risk if isinstance(risk, str) else UNKNOWN_RISK,
    }


def _grant_key(call: ToolCall) -> tuple[str, str] | None:
    """Tool name plus canonical arguments; ``None`` when the arguments cannot be compared."""
    try:
        return call.name, json.dumps(call.arguments, sort_keys=True)
    except (TypeError, ValueError):
        return None


def _bounded_reason(reason: object) -> str | None:
    if not isinstance(reason, str) or not reason:
        return None
    return reason if len(reason) <= MAX_REASON_CHARS else reason[: MAX_REASON_CHARS - 3] + "..."


class ApprovalGate:
    """Asks the ``Approver`` about calls the policy asks about; remembers session approvals."""

    def __init__(self, approver: Approver) -> None:
        if not isinstance(approver, Approver):
            raise TypeError("The approver must be an Approver.")
        self._approver = approver
        self._granted: set[tuple[str, str]] = set()

    async def resolve(
        self, call: ToolCall, tool: Tool, emit_requested: Callable[[], None]
    ) -> ApprovalOutcome:
        """Decide whether ``call`` may run.

        Args:
            call: The validated call, with the arguments that would be executed.
            tool: The tool the call names (for the description and the risk shown).
            emit_requested: Publishes ``APPROVAL_REQUESTED``; called once, before anything is
                asked. If it raises, nobody is asked and the exception propagates.
        """
        details = build_details(call, tool)
        emit_requested()
        key = _grant_key(call)
        if key is not None and key in self._granted:
            return ApprovalOutcome(True, ApprovalAction.APPROVE_SESSION, SOURCE_SESSION_GRANT)
        try:
            result = await self._approver.request(copy.deepcopy(call), details)
        except Exception:
            return ApprovalOutcome(False, None, SOURCE_APPROVER_ERROR)
        if not isinstance(result, ApprovalResult) or not isinstance(result.action, ApprovalAction):
            return ApprovalOutcome(False, None, SOURCE_INVALID_RESULT)
        if result.action is ApprovalAction.REJECT:
            return ApprovalOutcome(
                False, result.action, SOURCE_USER, _bounded_reason(result.reason)
            )
        if result.action is ApprovalAction.APPROVE_SESSION and key is not None:
            self._granted.add(key)
        return ApprovalOutcome(True, result.action, SOURCE_USER)
