"""What an approved commit leaves behind, and the port that is told about it (HU-11-06).

``ReviewingRunner`` makes the commit only after a person approved the diff (HU-11-05). The next
step of the ticket (the Pull Request) hangs from that approval through ``CommitObserver``: it opens
no review of its own and it only receives what the person has just seen.

Only the standard library and ``harness_agent.core`` are used here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from harness_agent.core.interfaces.system import TaskCriteriaItem
from harness_agent.core.review.changes import ChangeSet


@dataclass(frozen=True)
class ApprovedChange:
    """A change that was approved by a person and committed by the harness.

    Attributes:
        ticket: Title of the task; ``None`` if untitled.
        objective: Objective of the task.
        commit_id: Short id of the commit the harness made.
        changes: The change as the repository saw it when it was approved.
        criteria: The stored criteria (with their evidence) at that moment.
    """

    ticket: str | None
    objective: str
    commit_id: str
    changes: ChangeSet
    criteria: tuple[TaskCriteriaItem, ...]


class CommitObserver(Protocol):
    """Told about each commit the harness makes after a human approval."""

    async def on_committed(self, approved: ApprovedChange) -> None:
        """React to ``approved``. Cancellation must propagate; anything else is contained."""
        ...
