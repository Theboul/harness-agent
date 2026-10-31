"""Opens the review of the diff when the agent finishes a task and acts on the decision (HU-11-05).

``ReviewingRunner`` wraps the runner that verifies the criteria (HU-11-04.1) without touching the
agent loop. When a run ends as ``COMPLETED``, every objective criterion is met and the work tree
has changes, a person sees the summary and the diff and decides:

* approve: the changes are committed (only if nothing blocks the approval: the core checks it
  again whatever the reviewer returns);
* reject, with a reason: nothing is committed and the cleaned reason goes back to the agent as
  the task of a new run (which is verified and reviewed again);
* confirm or reject a semantic criterion: only a confirmation changes ``passes`` (it goes through
  the verifier, the only writer);
* no decision (end of the input): nothing is committed and nothing goes back to the agent.

There is no counter of rounds here, on purpose: every new run goes through the limits of the
session. Cancellation is never caught; anything the reviewer raises ends the run without a commit.

Only the standard library and ``harness_agent.core`` are used here.
"""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from harness_agent.core.entities import Message
from harness_agent.core.interfaces.system import TaskCriteriaItem
from harness_agent.core.review.changes import ChangeSource, ChangeSourceError
from harness_agent.core.review.decision import ChangeReviewer, Choice, ReviewDecision
from harness_agent.core.review.messages import (
    commit_message,
    criterion_rejection_notice,
    rejection_notice,
)
from harness_agent.core.review.view import Blocker, ReviewView, build_view
from harness_agent.core.verification.outcomes import Confirmation
from harness_agent.core.verification.runner import COMPLETED, TurnLike

TurnT = TypeVar("TurnT", bound=TurnLike)
TurnT_co = TypeVar("TurnT_co", covariant=True)

NO_DECISION = "Sin decisión: no se hizo commit."
CRITERIA_UNREADABLE = "No se pudieron leer los criterios: no se revisa el cambio."
NOT_A_SEMANTIC_ONE = "Solo se pueden confirmar o rechazar criterios semánticos pendientes."
STILL_BLOCKED = {
    Blocker.SEMANTIC_PENDING: (
        "Hay criterios semánticos sin confirmar: confírmalos antes de aprobar."
    ),
    Blocker.TRUNCATED: "El diff es demasiado grande para revisarlo: no se puede aprobar.",
    Blocker.NO_CHANGES: "No hay cambios que aprobar.",
}


class TaskRunner(Protocol[TurnT_co]):
    """Anything that runs a task over a history (``VerifyingRunner`` is one)."""

    async def run(self, task: str, history: list[Message]) -> TurnT_co: ...


class ReviewCriteria(Protocol):
    """Where the criteria of the task are read from (the protected store)."""

    def load_criteria(self, session_id: str) -> list[TaskCriteriaItem]: ...


class CriterionConfirmer(Protocol):
    """Marks a semantic criterion as met because a person said so (the verifier)."""

    def confirm(self, session_id: str, index: int) -> Confirmation: ...


class ReviewingRunner(Generic[TurnT]):
    """Runs a task and, when it is finished, asks a person to approve the diff.

    Args:
        inner: Runs the task (and verifies its criteria).
        source: Reads the change of the work tree and commits it.
        reviewer: Shows the review and returns the decision.
        criteria: Where the stored criteria are read from.
        confirmer: Marks a semantic criterion as confirmed.
        session_id: The session whose criteria are reviewed.
        ticket: Title of the task, for the commit message; ``None`` if untitled.
        objective: Objective of the task, for the commit message.
    """

    def __init__(
        self,
        inner: TaskRunner[TurnT],
        source: ChangeSource,
        reviewer: ChangeReviewer,
        criteria: ReviewCriteria,
        confirmer: CriterionConfirmer,
        *,
        session_id: str,
        ticket: str | None,
        objective: str,
    ) -> None:
        self._inner = inner
        self._source = source
        self._reviewer = reviewer
        self._criteria = criteria
        self._confirmer = confirmer
        self._session_id = session_id
        self._ticket = ticket
        self._objective = objective

    async def run(self, task: str, history: list[Message]) -> TurnT:
        """Run ``task``; return the result of the last run."""
        result = await self._inner.run(task, history)
        while _completed(result):
            follow_up = await self._review()
            if follow_up is None:
                return result
            result = await self._inner.run(follow_up, history)
        return result

    def _load(self) -> list[TaskCriteriaItem] | None:
        try:
            return list(self._criteria.load_criteria(self._session_id))
        except Exception:
            # Tampered or unreadable: nothing from the store can be trusted (fail closed).
            return None

    async def _review(self) -> str | None:
        """Review the change; the text for the agent if it must go back to work, else ``None``."""
        items = self._load()
        if items is None:
            self._reviewer.inform(CRITERIA_UNREADABLE)
            return None
        if not all(item.passes for item in items if item.command is not None):
            return None
        try:
            changes = await self._source.snapshot()
        except ChangeSourceError as error:
            self._reviewer.inform(error.message)
            return None
        if changes.is_empty:
            return None
        while True:
            view = build_view(self._ticket or "", changes, items)
            decision = await self._reviewer.choose(view)
            if decision.choice is Choice.APPROVE:
                if view.can_approve:
                    await self._commit()
                    return None
                self._reviewer.inform(STILL_BLOCKED[view.blockers[0]])
            elif decision.choice is Choice.REJECT:
                return rejection_notice(decision.reason)
            elif decision.choice is Choice.NONE:
                self._reviewer.inform(NO_DECISION)
                return None
            else:
                notice = self._criterion(decision, view, items)
                if notice is not None:
                    return notice
                reloaded = self._load()
                if reloaded is None:
                    self._reviewer.inform(CRITERIA_UNREADABLE)
                    return None
                items = reloaded

    async def _commit(self) -> None:
        try:
            identifier = await self._source.commit(commit_message(self._ticket, self._objective))
        except ChangeSourceError as error:
            self._reviewer.inform(error.message)
            return
        self._reviewer.inform(f"Commit hecho: {identifier}")

    def _criterion(
        self, decision: ReviewDecision, view: ReviewView, items: list[TaskCriteriaItem]
    ) -> str | None:
        """Confirm or reject a criterion; the notice for the agent when it is rejected."""
        index = decision.criterion
        if isinstance(index, bool) or not isinstance(index, int) or index not in view.pending_human:
            self._reviewer.inform(NOT_A_SEMANTIC_ONE)
            return None
        if decision.choice is Choice.REJECT_CRITERION:
            return criterion_rejection_notice(index, items[index - 1].description, decision.reason)
        if self._confirmer.confirm(self._session_id, index) is not Confirmation.CONFIRMED:
            self._reviewer.inform(f"No se pudo confirmar el criterio {index}.")
        return None


def _completed(result: TurnLike) -> bool:
    status = result.status
    return getattr(status, "value", status) == COMPLETED
