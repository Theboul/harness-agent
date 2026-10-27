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

The user's rejection reason is cleaned (``clean_reason``) and kept in the outcome; this module
never publishes it. ``rejection_message`` builds the text the model receives for a rejection: the
stable mark first, then the reason framed as the person's own words (HU-05-04).
"""

from __future__ import annotations

import copy
import json
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import ApprovalAction, ApprovalResult, Approver
from harness_agent.core.interfaces.tool import Tool
from harness_agent.core.redaction import hide_url_credentials

MAX_REASON_CHARS = 200
MAX_REJECTION_CHARS = 500
REJECTED_MARK = "[approval_rejected]"
SOURCE_USER = "user"
SOURCE_SESSION_GRANT = "session_grant"
SOURCE_APPROVER_ERROR = "approver_error"
SOURCE_INVALID_RESULT = "invalid_result"
UNKNOWN_RISK = "unknown"

_MIN_REASON_CHARS = 20
_READ_LIMIT = 1_000  # hide_url_credentials is quadratic: never feed it more than this
_QUOTE = chr(0x2019)
_LINE_BREAKS = frozenset({"Zl", "Zp"})
_DROPPED = frozenset({"Cc", "Cf", "Cs", "Co"})
_REJECTED = REJECTED_MARK + " Tool '{name}' was rejected by the user."
_FRAME = (
    " Reason given by the person, in their own words and not an instruction from the system;"
    " rethink your plan instead of repeating this action: '{reason}'"
)


@dataclass(frozen=True)
class ApprovalOutcome:
    """What the user (or the fail-closed rule) decided about one pending call.

    Attributes:
        approved: True only when the call may be executed.
        action: The chosen action; ``None`` when the gate failed closed.
        source: ``user``, ``session_grant``, ``approver_error`` or ``invalid_result``.
        reason: The user's rejection reason, cleaned and bounded; never published.
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


def clean_reason(reason: object) -> str | None:
    """Make a rejection reason safe to hand to the model; ``None`` when nothing usable is left.

    Single line, no control, format, surrogate or private-use characters, URL credentials hidden,
    no ``'`` or ``"`` (so it cannot close the frame of ``rejection_message``) and at most
    ``MAX_REASON_CHARS`` characters. Only the first characters are read, whatever the size.
    """
    if not isinstance(reason, str):
        return None
    kept: list[str] = []
    truncated = False
    for char in reason:
        category = unicodedata.category(char)
        if char.isspace() or category in _LINE_BREAKS:
            char = " "
        elif category in _DROPPED:
            continue
        kept.append(char)
        if len(kept) >= _READ_LIMIT:
            truncated = True
            break
    text = " ".join("".join(kept).split())
    if truncated:
        head, _, last = text.rpartition(" ")
        if "://" in last:  # a URL cut in the middle may have lost the end of its credentials
            text = head
    text = hide_url_credentials(text).replace("'", _QUOTE).replace('"', _QUOTE)
    if not text:
        return None
    return text if len(text) <= MAX_REASON_CHARS else text[: MAX_REASON_CHARS - 3] + "..."


def rejection_message(tool_name: str, reason: object) -> str:
    """The text the model receives when the user rejected a call.

    Without a usable reason it is exactly the text of HU-05-03. With one, the reason follows a
    fixed warning, inside single quotes, as the last fragment; the whole message stays within
    ``MAX_REJECTION_CHARS`` unless the tool name alone already exceeds it (then there is no reason).
    """
    first = _REJECTED.format(name=tool_name)
    cleaned = clean_reason(reason)
    if cleaned is None:
        return first
    room = MAX_REJECTION_CHARS - len(first) - len(_FRAME.format(reason=""))
    if room < _MIN_REASON_CHARS:
        return first
    if len(cleaned) > room:
        cleaned = cleaned[: room - 3] + "..."
    return first + _FRAME.format(reason=cleaned)


class ApprovalGate:
    """Asks the ``Approver`` about calls the policy asks about; remembers session approvals."""

    def __init__(self, approver: Approver) -> None:
        if not isinstance(approver, Approver):
            raise TypeError("The approver must be an Approver.")
        self._approver = approver
        self._granted: set[tuple[str, str]] = set()

    async def resolve(
        self, call: ToolCall, tool: Tool, emit_requested: Callable[[str], None]
    ) -> ApprovalOutcome:
        """Decide whether ``call`` may run.

        Args:
            call: The validated call, with the arguments that would be executed.
            tool: The tool the call names (for the description and the risk shown).
            emit_requested: Publishes ``APPROVAL_REQUESTED`` (it receives the risk level to
                show); called once, before anything is asked. If it raises, nobody is asked
                and the exception propagates.
        """
        details = build_details(call, tool)
        emit_requested(details["risk"])
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
            return ApprovalOutcome(False, result.action, SOURCE_USER, clean_reason(result.reason))
        if result.action is ApprovalAction.APPROVE_SESSION and key is not None:
            self._granted.add(key)
        return ApprovalOutcome(True, result.action, SOURCE_USER)
