"""Test double: ScriptedPolicy (HU-01-01, T003).

A PermissionPolicy whose decisions are scripted per tool name. It is NOT HU-05-01
(owned by C). Anything not mapped is DENY: the double never applies a permissive default.
"""

from __future__ import annotations

from typing import Any

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy


class ScriptedPolicy(PermissionPolicy):
    """Policy double mapping tool names to a decision, an exception, or a raw value."""

    def __init__(self, decisions: dict[str, Any] | None = None) -> None:
        self._decisions = dict(decisions or {})
        self.received: list[ToolCall] = []

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        """Record the evaluated call and return the scripted outcome (default DENY)."""
        self.received.append(call)
        outcome = self._decisions.get(call.name, PermissionDecision.DENY)
        if isinstance(outcome, BaseException):
            raise outcome
        decision: PermissionDecision = outcome
        return decision
