"""Statuses and results of the automatic verification of criteria (HU-11-04.1).

Only the standard library and ``harness_agent.core`` are used here. Everything is immutable. The
three statuses of a task are decided by one pure function, ``task_state``, that the verifier and
the terminal share, so there is never a second opinion about when a task counts as verified.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from enum import Enum

from harness_agent.core.entities import ToolCall


class CriterionStatus(str, Enum):
    """What one verification round found out about one criterion."""

    MET = "cumplido"
    NOT_MET = "no_cumplido"
    REGRESSION = "regresion"
    NOT_RUN = "no_ejecutado"
    TIMED_OUT = "tiempo_agotado"
    TAMPERED = "alterado"
    PENDING_HUMAN = "pendiente_humano"


class NotRunCause(str, Enum):
    """Why a verification command did not run."""

    DENIED = "denegado"
    NO_APPROVER = "sin_aprobador"
    NOT_APPROVED = "no_aprobado"
    UNSUPPORTED_CONDITION = "condicion_no_soportada"
    ERROR = "error"


class TaskState(str, Enum):
    """The state of the task after a round; it is never "done" by the model's word."""

    VERIFIED = "verificada"
    PENDING_HUMAN = "pendiente_humano"
    NOT_FINISHED = "no_terminada"


_CORRECTABLE = frozenset(
    {CriterionStatus.NOT_MET, CriterionStatus.REGRESSION, CriterionStatus.TIMED_OUT}
)


def task_state(statuses: Iterable[object]) -> TaskState:
    """The state of the task given the status of each criterion (text or ``CriterionStatus``).

    Anything that is neither met nor waiting for a person, an unknown value, or no criteria at
    all means the task is not finished (fail closed).
    """
    values = [item.value if isinstance(item, CriterionStatus) else item for item in statuses]
    met, pending = CriterionStatus.MET.value, CriterionStatus.PENDING_HUMAN.value
    if not values or any(value not in (met, pending) for value in values):
        return TaskState.NOT_FINISHED
    return TaskState.PENDING_HUMAN if pending in values else TaskState.VERIFIED


@dataclass(frozen=True)
class CommandOutcome:
    """What running one verification command gave.

    Attributes:
        ran: Whether the command ran at all (it did not if there is no work area, the arguments
            were not valid or the shell could not start).
        exit_code: The exit code; ``None`` if it did not run or the time ran out.
        timed_out: The process was ended because it passed its time limit.
        output: Bounded output, with the credentials of URLs already hidden.
        timeout_seconds: The time limit that applied, when it is known.
    """

    ran: bool
    exit_code: int | None = None
    timed_out: bool = False
    output: str = ""
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        if not self.ran and (self.exit_code is not None or self.output or self.timed_out):
            raise ValueError("Un comando que no se ejecutó no tiene código, salida ni tiempo.")
        if self.timed_out and self.exit_code is not None:
            raise ValueError("Un comando que agotó su tiempo no tiene código de salida.")


CommandRunner = Callable[[ToolCall], Awaitable[CommandOutcome]]


@dataclass(frozen=True)
class CriterionResult:
    """The result of one criterion in one round (``index`` counts from 1).

    ``output`` is only kept for the statuses the agent can fix; ``program`` is the name of the
    program of the command (never its arguments) and is only used to show it to the person.
    """

    index: int
    description: str
    status: CriterionStatus
    exit_code: int | None = None
    program: str | None = None
    output: str = ""
    cause: NotRunCause | None = None
    timeout_seconds: float | None = None


@dataclass(frozen=True)
class VerificationReport:
    """One result per criterion of the task, in the order of the task."""

    results: tuple[CriterionResult, ...]

    @property
    def state(self) -> TaskState:
        return task_state(result.status for result in self.results)

    @property
    def correctable(self) -> tuple[CriterionResult, ...]:
        """The results the agent can fix by changing the work."""
        return tuple(result for result in self.results if result.status in _CORRECTABLE)
