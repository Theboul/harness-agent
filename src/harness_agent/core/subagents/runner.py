"""The runner of subagents (HU-09-01, HU-09-03, HU-09-04): implements the ``SubagentRunner`` port.

One delegation is: build the task, create the child session under the active session of the
orchestrator, run the loop of the child on an empty history, and translate how the turn ended into
a brief structured result. The transcript of the child stays in a list that only this call holds;
the orchestrator receives the result and nothing else. Every failure is a fixed code (see
``result``): what the child or the provider said about it is never copied.

The runner does not build the loop nor touch the store: ``bootstrap.py`` hands it ``ChildSessions``
(creates the session row) and ``ChildLoop`` (runs an ``AgentLoop`` with the registry view, the
policy of the orchestrator and the limits of the subagent). A cancellation is never caught.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol

from harness_agent.core.entities import Message, Role
from harness_agent.core.events import Event, EventType
from harness_agent.core.interfaces.connections import SubagentResult, SubagentRunner
from harness_agent.core.interfaces.event_bus import EventBus
from harness_agent.core.subagents.result import (
    INVALID_PROVIDER_RESPONSE,
    INVALID_RESULT,
    NO_CHILD_SESSION,
    PROVIDER_FAILED,
    SUBAGENT_FAILED,
    failure_output,
    limit_code,
    parse_result,
    partial_output,
    shorten_output,
)
from harness_agent.core.subagents.task import build_task

MAX_STORED_GOAL_CHARS = 200

_COMPLETED = "completed"
_LIMIT_REACHED = "limit_reached"
_PROVIDER_FAILED = "provider_failed"
_INVALID_PROVIDER_RESPONSE = "invalid_provider_response"


class ChildSessions(Protocol):
    """Creates the child session row (implemented in ``bootstrap.py`` over the session store)."""

    def create(self, parent_id: str, goal: str) -> str:
        """Create a session whose parent is ``parent_id`` and return its identifier."""
        ...


class ChildTurn(Protocol):
    """How a turn of the child loop ended; ``TurnResult`` of the loop complies."""

    @property
    def status(self) -> str: ...

    @property
    def final_response(self) -> str | None: ...

    @property
    def history(self) -> Sequence[Message]: ...

    @property
    def error(self) -> str | None: ...


ChildLoop = Callable[[str, str, list[Message]], Awaitable[ChildTurn]]
"""Runs the child: receives its session id, its task and the (empty) history it fills."""


def _identity(text: str) -> str:
    return text


def _last_text(history: Sequence[Message]) -> str | None:
    for message in reversed(history):
        if message.role is Role.ASSISTANT and message.content.strip():
            return message.content
    return None


class LoopSubagentRunner(SubagentRunner):
    """Delegates a task to a subagent that runs in its own child session and loop.

    Args:
        sessions: Creates the child session.
        run_child: Runs the loop of the child on the history it receives.
        bus: Where ``SUBAGENT_STARTED`` and ``SUBAGENT_FINISHED`` are published (informational).
        parent_session: The session that is active now; the child session hangs from it.
        redact: Hides secrets in every text of the result and in the goal that is stored.
    """

    def __init__(
        self,
        sessions: ChildSessions,
        run_child: ChildLoop,
        bus: EventBus,
        parent_session: Callable[[], str],
        *,
        redact: Callable[[str], str] = _identity,
    ) -> None:
        self._sessions = sessions
        self._run_child = run_child
        self._bus = bus
        self._parent_session = parent_session
        self._redact = redact

    async def execute(
        self,
        profile: str,
        goal: str,
        context: list[Message],
        output_schema: dict[str, Any],
    ) -> SubagentResult:
        """Run the delegation and return the brief result; see the module docstring."""
        task = build_task(goal, context, output_schema)
        try:
            parent_id = self._parent_session()
            child_id = self._sessions.create(parent_id, self._stored_goal(goal))
        except Exception:
            return SubagentResult("", failure_output(NO_CHILD_SESSION), True)
        self._announce(
            parent_id,
            EventType.SUBAGENT_STARTED,
            {"child_session_id": child_id, "profile": profile},
        )
        try:
            turn = await self._run_child(child_id, task, [])
            output, is_error, partial = self._translate(turn, output_schema)
        except Exception:
            output, is_error, partial = failure_output(SUBAGENT_FAILED), True, False
        output = self._hide(output)
        status = "partial" if partial else "failed" if is_error else "completed"
        self._announce(
            parent_id,
            EventType.SUBAGENT_FINISHED,
            {
                "child_session_id": child_id,
                "status": status,
                "is_error": is_error,
                "partial": partial,
            },
        )
        return SubagentResult(child_id, output, is_error)

    def _stored_goal(self, goal: str) -> str:
        return " ".join(self._redact(goal).split())[:MAX_STORED_GOAL_CHARS]

    @staticmethod
    def _translate(
        turn: ChildTurn, output_schema: dict[str, Any]
    ) -> tuple[dict[str, Any], bool, bool]:
        """``(output, is_error, partial)`` for how the turn ended; unknown endings are errors."""
        status = turn.status
        if status == _COMPLETED:
            parsed = parse_result(turn.final_response or "", output_schema)
            if parsed is None:
                return failure_output(INVALID_RESULT), True, False
            output = shorten_output(parsed)
            return output, output["error"] is not None, False
        if status == _LIMIT_REACHED:
            return partial_output(_last_text(turn.history), limit_code(turn.error)), False, True
        if status == _PROVIDER_FAILED:
            return failure_output(PROVIDER_FAILED), True, False
        if status == _INVALID_PROVIDER_RESPONSE:
            return failure_output(INVALID_PROVIDER_RESPONSE), True, False
        return failure_output(SUBAGENT_FAILED), True, False

    def _hide(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._redact(value)
        if isinstance(value, list):
            return [self._hide(item) for item in value]
        if isinstance(value, dict):
            return {key: self._hide(item) for key, item in value.items()}
        return value

    def _announce(self, parent_id: str, kind: EventType, payload: dict[str, Any]) -> None:
        """Publish an informational event; a subscriber that fails does not stop the delegation."""
        try:
            self._bus.emit(Event.create(parent_id, kind, payload))
        except Exception:
            pass
