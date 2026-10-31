"""The review view: what the person sees, built from the real change and the stored criteria.

Pure and total. Criteria come from the protected store, never from the agent; the verification
command and the evidence are not shown. Only the standard library and ``harness_agent.core``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from harness_agent.core.interfaces.system import TaskCriteriaItem
from harness_agent.core.review.changes import ChangeSet
from harness_agent.core.verification.feedback import one_line

MAX_DESCRIPTION_CHARS = 120


class ReviewCriterionState(str, Enum):
    """The state of one criterion in the review."""

    MET = "cumplido"
    PENDING = "pendiente"
    PENDING_HUMAN = "pendiente_humano"
    CONFIRMED_HUMAN = "confirmado_humano"


class Blocker(str, Enum):
    """Why the change cannot be approved yet."""

    SEMANTIC_PENDING = "criterio_semantico_pendiente"
    TRUNCATED = "diff_demasiado_grande"
    NO_CHANGES = "sin_cambios"


@dataclass(frozen=True)
class CriterionView:
    """One criterion as shown: its position (from 1), description and state."""

    index: int
    description: str
    state: ReviewCriterionState


@dataclass(frozen=True)
class ReviewView:
    """Everything the person needs to decide."""

    ticket: str
    changes: ChangeSet
    criteria: tuple[CriterionView, ...]
    blockers: tuple[Blocker, ...] = ()

    @property
    def can_approve(self) -> bool:
        return not self.blockers

    @property
    def objective_total(self) -> int:
        return sum(1 for c in self.criteria if _is_objective(c))

    @property
    def objective_met(self) -> int:
        return sum(1 for c in self.criteria if c.state is ReviewCriterionState.MET)

    @property
    def pending_human(self) -> tuple[int, ...]:
        """Positions of the semantic criteria nobody has confirmed yet."""
        return tuple(
            c.index for c in self.criteria if c.state is ReviewCriterionState.PENDING_HUMAN
        )


def _is_objective(criterion: CriterionView) -> bool:
    return criterion.state in (ReviewCriterionState.MET, ReviewCriterionState.PENDING)


def _state(item: TaskCriteriaItem) -> ReviewCriterionState:
    if item.command is None:
        return (
            ReviewCriterionState.CONFIRMED_HUMAN
            if item.passes
            else ReviewCriterionState.PENDING_HUMAN
        )
    return ReviewCriterionState.MET if item.passes else ReviewCriterionState.PENDING


def build_view(ticket: str, changes: ChangeSet, items: Sequence[TaskCriteriaItem]) -> ReviewView:
    """The view of ``changes`` and the stored ``items`` (in the order of the task)."""
    criteria = tuple(
        CriterionView(index, one_line(item.description, MAX_DESCRIPTION_CHARS), _state(item))
        for index, item in enumerate(items, start=1)
    )
    blockers: list[Blocker] = []
    if changes.is_empty:
        blockers.append(Blocker.NO_CHANGES)
    if any(c.state is ReviewCriterionState.PENDING_HUMAN for c in criteria):
        blockers.append(Blocker.SEMANTIC_PENDING)
    if changes.truncated:
        blockers.append(Blocker.TRUNCATED)
    return ReviewView(ticket, changes, criteria, tuple(blockers))
