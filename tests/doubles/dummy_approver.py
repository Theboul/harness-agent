"""Test double: DummyApprover implementing the Approver abstract contract."""

from __future__ import annotations

from typing import Any

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import (
    ApprovalAction,
    ApprovalResult,
    Approver,
)


class DummyApprover(Approver):
    """In-memory test double for the Approver interface."""

    def __init__(
        self,
        default_action: ApprovalAction = ApprovalAction.APPROVE_ONCE,
        default_reason: str | None = None,
    ) -> None:
        self.default_action = default_action
        self.default_reason = default_reason
        self.recorded_requests: list[tuple[ToolCall, dict[str, Any]]] = []

    async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
        """Record the approval request and return the configured decision."""
        self.recorded_requests.append((call, details))
        return ApprovalResult(action=self.default_action, reason=self.default_reason)
