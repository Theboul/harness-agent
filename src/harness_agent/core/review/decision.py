"""What a person can decide in the review, and the port that asks for it.

``ChangeReviewer`` is implemented by the terminal (``cli/review.py``); the core only needs the
decision. Only the standard library and ``harness_agent.core`` are used here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from harness_agent.core.review.view import ReviewView


class Choice(str, Enum):
    """The decisions of the menu. ``NONE`` is no decision (end of input, ``/salir``)."""

    APPROVE = "aprobar"
    REJECT = "rechazar"
    CONFIRM = "confirmar_criterio"
    REJECT_CRITERION = "rechazar_criterio"
    NONE = "sin_decision"


@dataclass(frozen=True)
class ReviewDecision:
    """A decision: the choice, the criterion it is about (from 1) and an optional reason."""

    choice: Choice
    criterion: int | None = None
    reason: str | None = None


class ChangeReviewer(Protocol):
    """Shows the review and returns the decision of the person."""

    async def choose(self, view: ReviewView) -> ReviewDecision:
        """Show ``view`` and wait for a decision."""
        ...

    def inform(self, text: str) -> None:
        """Tell the person the result of a step (a commit, a refusal)."""
        ...
