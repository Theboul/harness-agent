"""Detects that the agent proposes to finish and opens the correction round (HU-11-04.1).

``VerifyingRunner`` wraps the turn of the agent loop without touching it. When a turn ends as
``COMPLETED`` (the agent gave a final answer without asking for tools) it asks the verifier to
check every objective criterion. If something is wrong that the agent can fix, the framed output
of the commands is added to the history as external content and a new turn starts with the notice
of the harness as its task; otherwise it ends.

There is no counter of rounds here, on purpose: every new turn goes through the limits of the
session (turns, time and tokens) of the loop, and when one of them is reached the loop answers
``LIMIT_REACHED`` without calling the model, which ends the rounds. The runner needs a loop that
has limits (``compose()`` always gives them).

Only the standard library and ``harness_agent.core`` are used here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Generic, Protocol, TypeVar

from harness_agent.core.entities import Message, Role
from harness_agent.core.verification.feedback import compose_feedback
from harness_agent.core.verification.outcomes import VerificationReport

COMPLETED = "completed"


class TurnLike(Protocol):
    """What the runner reads of the result of a turn: its status (``TurnResult`` has it)."""

    @property
    def status(self) -> object: ...


TurnT = TypeVar("TurnT", bound=TurnLike)


class Verifier(Protocol):
    """What the runner needs from a verifier."""

    async def verify(self, session_id: str) -> VerificationReport: ...


class VerifyingRunner(Generic[TurnT]):
    """Runs a task and, each time the agent proposes to finish, verifies its criteria.

    Args:
        run_turn: Runs one turn of the agent loop for a task text over the given history.
        verifier: Verifies the criteria; ``None`` turns the runner into a plain pass-through.
        session_id: The session whose criteria are verified.
    """

    def __init__(
        self,
        run_turn: Callable[[str, list[Message]], Awaitable[TurnT]],
        verifier: Verifier | None,
        session_id: str,
    ) -> None:
        self._run_turn = run_turn
        self._verifier = verifier
        self._session_id = session_id

    async def run(self, task: str, history: list[Message]) -> TurnT:
        """Run ``task``; return the result of the last turn.

        ``history`` is the caller's list: the loop appends to it, and so does this method when it
        adds the output of a failed verification.
        """
        result = await self._run_turn(task, history)
        while self._verifier is not None and _completed(result):
            report = await self._verifier.verify(self._session_id)
            feedback = compose_feedback(report)
            if feedback is None:
                return result
            history.append(Message(Role.USER, feedback.external, is_external=True))
            result = await self._run_turn(feedback.notice, history)
        return result


def _completed(result: TurnLike) -> bool:
    status = result.status
    return getattr(status, "value", status) == COMPLETED
