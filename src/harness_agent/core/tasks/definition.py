"""A validated task: objective, context, rules and acceptance criteria (HU-11-01).

A criterion with a verification command is *objective*; one without is *semantic* and needs a
human to validate it (business rule 5). Both types are immutable.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from harness_agent.core.tasks.commands import TaskCommand

MAX_TASK_CHARS = 65_536
MAX_CRITERIA = 100
MAX_FIELD_CHARS = 2_000
MAX_SECTION_CHARS = 20_000


class CriterionKind(str, Enum):
    """OBJECTIVE: verified by a command; SEMANTIC: needs human validation."""

    OBJECTIVE = "objetivo"
    SEMANTIC = "semantico"


@dataclass(frozen=True)
class CriterionDefinition:
    """One acceptance criterion as written in the task.

    Attributes:
        description: What must be true.
        command: Verification command, or ``None`` for a semantic criterion.
        expectation: Condition the command must meet; present exactly when ``command`` is.
    """

    description: str
    command: str | None = None
    expectation: str | None = None

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("La descripción del criterio no puede estar vacía.")
        message = "El comando y la condición esperada van juntos y con texto."
        if (self.command is None) != (self.expectation is None):
            raise ValueError(message)
        if self.command is not None and self.expectation is not None:
            if not self.command.strip() or not self.expectation.strip():
                raise ValueError(message)

    @property
    def kind(self) -> CriterionKind:
        return CriterionKind.SEMANTIC if self.command is None else CriterionKind.OBJECTIVE


@dataclass(frozen=True)
class TaskDefinition:
    """A task ready to start: it has an objective and at least one criterion.

    Attributes:
        title: Optional short name (for example ``TAREA-14: Validar el correo``).
        objective: What the agent must achieve; becomes the goal of the session.
        context: Free text with background; may be empty.
        rules: Free text with constraints; may be empty.
        criteria: Ordered acceptance criteria (at least one).
        commands: Verification commands (tests, lint) in the order of the task, at most one of
            each kind; empty when the task declares none (HU-11-03).
    """

    title: str | None
    objective: str
    context: str
    rules: str
    criteria: tuple[CriterionDefinition, ...]
    commands: tuple[TaskCommand, ...] = ()

    def __post_init__(self) -> None:
        if not self.objective.strip():
            raise ValueError("El objetivo de la tarea no puede estar vacío.")
        if not self.criteria:
            raise ValueError("La tarea necesita al menos un criterio.")
        if not isinstance(self.commands, tuple) or not all(
            isinstance(command, TaskCommand) for command in self.commands
        ):
            raise ValueError("Los comandos de la tarea deben ser una tupla de TaskCommand.")
        kinds = [command.kind for command in self.commands]
        if len(kinds) != len(set(kinds)):
            raise ValueError("La tarea declara dos comandos del mismo tipo.")

    def with_title(self, title: str) -> TaskDefinition:
        """The same task, titled ``title`` if it had none (this task if it already had one)."""
        if self.title is not None or not title.strip():
            return self
        return replace(self, title=title.strip())
