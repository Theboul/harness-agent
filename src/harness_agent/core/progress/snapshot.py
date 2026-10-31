"""What a progress checkpoint says about a ticket (HU-11-08.1).

Plain immutable values: the recorder fills them and ``render_progress`` writes them as text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class CriterionState(str, Enum):
    """DONE: verified; PENDING: objective and not met yet; HUMAN: semantic, waits for a person."""

    DONE = "cumplido"
    PENDING = "pendiente"
    HUMAN = "pendiente de validación humana"


class CheckpointKind(str, Enum):
    """CHECKPOINT: written at the end of a turn; FINAL: written when the session ends normally."""

    CHECKPOINT = "punto de control"
    FINAL = "final de la sesión"


@dataclass(frozen=True)
class CriterionLine:
    """The state of one acceptance criterion.

    Attributes:
        position: One-based order of the criterion in the task.
        description: What must be true (never the verification command).
        state: Where the criterion stands.
    """

    position: int
    description: str
    state: CriterionState


@dataclass(frozen=True)
class ProgressSnapshot:
    """Everything one progress file says.

    Attributes:
        ticket: Name of the ticket (the title of the task, or the session when it has none).
        session_id: Session that wrote the checkpoint.
        turn: Turns finished so far (zero before the first one).
        kind: Whether it is a turn checkpoint or the final write.
        updated_at: When it was written.
        objective: The goal of the task.
        criteria: The state of every criterion, in the order of the task.
        note: Last answer of the agent; may be empty.
    """

    ticket: str
    session_id: str
    turn: int
    kind: CheckpointKind
    updated_at: datetime
    objective: str
    criteria: tuple[CriterionLine, ...]
    note: str

    def __post_init__(self) -> None:
        if isinstance(self.turn, bool) or not isinstance(self.turn, int) or self.turn < 0:
            raise ValueError("El número de turno debe ser un entero no negativo.")
        if not isinstance(self.criteria, tuple) or not all(
            isinstance(line, CriterionLine) for line in self.criteria
        ):
            raise ValueError("Los criterios deben ser una tupla de CriterionLine.")
