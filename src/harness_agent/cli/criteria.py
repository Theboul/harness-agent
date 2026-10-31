"""The state of each criterion of the task in the terminal (HU-11-04.1 / AC-04).

The harness publishes ``criterion_verified`` once per criterion after each verification (see
``specs/029-automatic-criteria-verification/contracts/criterion_verified_event.md``). This module
turns those events into the lines of the contract: a marker, the number, the description and, in
parentheses, what happened. The text comes only from the payload and is cleaned and bounded; the
command is never in the payload, and a program name that is not a plain name is not shown, so the
arguments of a command can never reach the screen.

``CriteriaBoard`` keeps the last state of each criterion in memory (it reads no store and runs
nothing) so the person can ask for it at any time.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping
from typing import Any, TextIO

from harness_agent.core import Event, EventBus, EventType, TaskState, one_line, task_state

from .app import put_line

MAX_DESCRIPTION_CHARS = 80
MAX_CRITERIA_SHOWN = 100_000
NOT_YET = "Todavía no se ha verificado ningún criterio."
NOT_RUN = "no ejecutado"
_PROGRAM = re.compile(r"[A-Za-z0-9._+-]{1,40}")
_MARKS = {"cumplido": "[x]", "confirmado_humano": "[x]", "pendiente_humano": "[?]"}
_STATE_TEXT = {
    TaskState.VERIFIED: "verificada",
    TaskState.PENDING_HUMAN: "pendiente de validación humana",
    TaskState.NOT_FINISHED: "no terminada",
}
_KNOWN = (
    "cumplido",
    "no_cumplido",
    "regresion",
    "no_ejecutado",
    "tiempo_agotado",
    "alterado",
    "pendiente_humano",
    "confirmado_humano",
)


def _number(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _status(payload: Mapping[str, Any]) -> str:
    status = payload.get("status")
    return status if isinstance(status, str) and status in _KNOWN else "no_ejecutado"


def _detail(payload: Mapping[str, Any], status: str) -> str:
    code = _number(payload.get("exit_code"))
    program = payload.get("program")
    named = program if isinstance(program, str) and _PROGRAM.fullmatch(program) else None
    prefix = f"{named}: " if named else ""
    if status in ("cumplido", "no_cumplido") and code is not None:
        return f"{prefix}salida {code}"
    if status == "regresion" and code is not None:
        return f"regresión; {prefix}salida {code}"
    if status == "tiempo_agotado":
        return f"{prefix}tiempo agotado"
    if status == "alterado":
        return "criterio alterado: no se ejecutó"
    if status == "pendiente_humano":
        return "pendiente de validación humana"
    if status == "confirmado_humano":
        return "confirmado por la persona"
    return NOT_RUN


def _resolve(payload: Mapping[str, Any]) -> tuple[str, str]:
    """The status and the detail to show; "met" without a valid exit code is not shown as met."""
    status = _status(payload)
    detail = _detail(payload, status)
    return ("no_ejecutado" if detail == NOT_RUN else status), detail


def criterion_line(payload: Mapping[str, Any]) -> str:
    """The line of one criterion for the payload of a ``criterion_verified`` event.

    A payload with missing or odd fields gives a neutral line; it never raises.
    """
    status, detail = _resolve(payload)
    mark = _MARKS.get(status, "[ ]")
    number = _number(payload.get("criterion"))
    description = payload.get("description")
    text = one_line(description, MAX_DESCRIPTION_CHARS) if isinstance(description, str) else ""
    parts = [mark, "?" if number is None else str(number)]
    if text:
        parts.append(text)
    return " ".join(parts) + f" ({detail})"


class CriteriaBoard:
    """The last state of each criterion, as the events reported it."""

    def __init__(self) -> None:
        self._rows: dict[int, tuple[str, str]] = {}

    def update(self, payload: Mapping[str, Any]) -> None:
        """Remember the state of one criterion; a payload without a usable number is ignored."""
        number = _number(payload.get("criterion"))
        if number is None or not 1 <= number <= MAX_CRITERIA_SHOWN:
            return
        self._rows[number] = (criterion_line(payload), _resolve(payload)[0])

    def lines(self) -> list[str]:
        """One line per criterion, in order."""
        return [self._rows[number][0] for number in sorted(self._rows)]

    def summary_line(self) -> str:
        """The state of the task and how many objective criteria are met."""
        statuses = [status for _, status in self._rows.values()]
        objective = [
            status for status in statuses if status not in ("pendiente_humano", "confirmado_humano")
        ]
        met = sum(1 for status in objective if status == "cumplido")
        state = _STATE_TEXT[task_state(statuses)]
        return f"Tarea: {state} ({met} de {len(objective)} criterios objetivos cumplidos)"

    def report(self) -> str:
        """What ``/criterios`` writes: every line and the summary, or that nothing was verified."""
        if not self._rows:
            return NOT_YET
        return "\n".join([*self.lines(), self.summary_line()])


def attach_criteria_status(bus: EventBus, output: TextIO | None = None) -> CriteriaBoard:
    """Write the line of each criterion as its event arrives, and the summary after the last.

    It subscribes only to ``criterion_verified`` (the renderer of the other events is not
    touched) and returns the board that ``/criterios`` reads. ``output`` is ``sys.stdout`` at the
    moment of the call when it is not given.
    """
    stream = sys.stdout if output is None else output
    board = CriteriaBoard()

    def show(event: Event) -> None:
        payload = event.payload
        board.update(payload)
        put_line(stream, criterion_line(payload))
        number, total = _number(payload.get("criterion")), _number(payload.get("total"))
        if number is not None and number == total:
            put_line(stream, board.summary_line())

    bus.subscribe(EventType.CRITERION_VERIFIED, show)
    return board
