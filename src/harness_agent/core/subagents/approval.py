"""The approvals of a subagent go up to the person saying who asks (HU-09-03).

``SubagentApprover`` wraps the approver of the terminal: it adds to the details of the request the
name of the subagent that asks and hands everything else over unchanged, including the decision and
the reason of the person. A failure or a cancellation goes up as it is, so the approval gate of the
loop denies (fail closed) or the cancellation reaches the caller.
"""

from __future__ import annotations

from typing import Any

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import ApprovalResult, Approver

REQUESTER_KEY = "requested_by"
_LABEL_SESSION_CHARS = 8


def requester_label(session_id: str) -> str:
    """How the person reads who asks: ``subagente`` and the start of the child session id."""
    return f"subagente {session_id[:_LABEL_SESSION_CHARS]}"


class SubagentApprover(Approver):
    """Asks ``inner`` (the person) on behalf of a subagent, telling who asks.

    Args:
        inner: The approver of the orchestrator.
        requester: The text that names the subagent in the request (see ``requester_label``).
    """

    def __init__(self, inner: Approver, requester: str) -> None:
        self._inner = inner
        self._requester = requester

    async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
        """Forward the request with ``requested_by`` added; the original details are not changed."""
        return await self._inner.request(call, {**details, REQUESTER_KEY: self._requester})
