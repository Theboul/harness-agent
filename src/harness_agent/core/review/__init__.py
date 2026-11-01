"""Summary of the changes and human approval of the diff before the commit (HU-11-05).

Only the standard library and ``harness_agent.core`` are used here. Git and the terminal are
reached through the ``Protocol`` ports ``ChangeSource`` and ``ChangeReviewer``.
"""

from harness_agent.core.review.approved import ApprovedChange, CommitObserver
from harness_agent.core.review.changes import (
    ChangeSet,
    ChangeSource,
    ChangeSourceError,
    ChangeStatus,
    FileChange,
)
from harness_agent.core.review.decision import ChangeReviewer, Choice, ReviewDecision
from harness_agent.core.review.messages import (
    commit_message,
    criterion_rejection_notice,
    rejection_notice,
)
from harness_agent.core.review.runner import (
    CriterionConfirmer,
    ReviewCriteria,
    ReviewingRunner,
    TaskRunner,
)
from harness_agent.core.review.view import (
    Blocker,
    CriterionView,
    ReviewCriterionState,
    ReviewView,
    build_view,
)

__all__ = [
    "ApprovedChange",
    "CommitObserver",
    "Blocker",
    "ChangeReviewer",
    "ChangeSet",
    "ChangeSource",
    "ChangeSourceError",
    "ChangeStatus",
    "Choice",
    "ReviewCriteria",
    "CriterionConfirmer",
    "ReviewCriterionState",
    "CriterionView",
    "FileChange",
    "ReviewDecision",
    "ReviewView",
    "ReviewingRunner",
    "TaskRunner",
    "build_view",
    "commit_message",
    "criterion_rejection_notice",
    "rejection_notice",
]
