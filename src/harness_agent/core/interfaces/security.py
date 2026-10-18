"""Security and user approval interfaces for HARNESS.

Enforces fail-closed permission policy decisions (deny/ask/allow) and
asynchronous bidirectional communication for human authorization (V-01, V-02).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from harness_agent.core.entities import ToolCall


class PermissionDecision(str, Enum):
    """Result of evaluating a tool invocation against the permission policy.

    DENY: Tool execution is forbidden; an error is returned to the context.
    ASK: Execution requires explicit human confirmation via Approver.
    ALLOW: Tool execution is permitted immediately without prompting.
    """

    DENY = "deny"
    ASK = "ask"
    ALLOW = "allow"


class ApprovalAction(str, Enum):
    """User decision on an approval request.

    APPROVE_ONCE: Execute the tool call this single time.
    APPROVE_SESSION: Execute this call and allow matching future calls this session.
    REJECT: Deny execution with an optional reason provided to the model.
    """

    APPROVE_ONCE = "approve_once"
    APPROVE_SESSION = "approve_session"
    REJECT = "reject"


@dataclass(frozen=True)
class ApprovalResult:
    """Outcome of human interaction with an approval prompt.

    Attributes:
        action: The decided ApprovalAction.
        reason: Optional human-provided rejection justification or guidance.
    """

    action: ApprovalAction
    reason: str | None = None


class PermissionPolicy(ABC):
    """Abstract Base Class for tool authorization policies.

    Evaluates whether a tool call may proceed. Fails closed (evaluates to ASK
    if no matching rule is defined).
    """

    @abstractmethod
    def evaluate(self, call: ToolCall) -> PermissionDecision:
        """Evaluate a tool invocation against active security rules.

        Args:
            call: The ToolCall requested by the model.

        Returns:
            PermissionDecision (DENY, ASK, or ALLOW).
        """
        ...


class Approver(ABC):
    """Abstract Base Class for human-in-the-loop authorization.

    Provides a bidirectional channel to prompt the user and obtain an approval decision.
    Firmas asíncronas provisionales sujetas a SPK-02.
    """

    @abstractmethod
    async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
        """Prompt the user for authorization before tool execution.

        Args:
            call: The pending ToolCall to be authorized.
            details: Human-readable context and environmental implications.

        Returns:
            ApprovalResult with chosen action and optional rejection reason.
        """
        ...
