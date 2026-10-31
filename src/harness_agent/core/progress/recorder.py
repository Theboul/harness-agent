"""Collects the state of a ticket and hands the progress text to a destination (HU-11-08.1).

The core does no I/O: the destination is a ``ProgressSink`` (the adapter writes the file
atomically). A failure is a fixed warning, never an exception: the file is a copy and SQLite keeps
the truth, so a turn must not fail because of it. Cancellation and interrupts are never caught.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Protocol

from harness_agent.core.entities import Message, Role
from harness_agent.core.interfaces.system import TaskCriteria, TaskCriteriaItem
from harness_agent.core.progress.render import progress_file_name, render_progress
from harness_agent.core.progress.snapshot import (
    CheckpointKind,
    CriterionLine,
    CriterionState,
    ProgressSnapshot,
)

WRITE_WARNING = (
    "No se pudo escribir el archivo de progreso; se conserva el último punto de control."
)


class ProgressSink(Protocol):
    """Where the progress text goes; ``write`` replaces a file whole or leaves it as it was."""

    def write(self, name: str, text: str) -> None: ...

    def read(self, name: str) -> str | None: ...


def _line(position: int, item: TaskCriteriaItem) -> CriterionLine:
    if item.passes:
        state = CriterionState.DONE
    elif item.command is None:
        state = CriterionState.HUMAN
    else:
        state = CriterionState.PENDING
    return CriterionLine(position, item.description, state)


def _last_answer(history: Sequence[Message]) -> str:
    for message in reversed(history):
        if message.role is Role.ASSISTANT and not message.is_external and message.content.strip():
            return message.content
    return ""


class ProgressRecorder:
    """Writes the progress of one ticket at the end of each turn and when the session ends."""

    def __init__(
        self,
        sink: ProgressSink,
        criteria: TaskCriteria,
        *,
        ticket: str | None,
        objective: str,
        session_id: str,
        clock: Callable[[], datetime],
        warn: Callable[[str], None],
    ) -> None:
        self._sink = sink
        self._criteria = criteria
        self._ticket = ticket
        self._objective = objective
        self._session_id = session_id
        self._clock = clock
        self._warn = warn
        self._turns = 0

    @property
    def file_name(self) -> str:
        """Name of the file this recorder writes."""
        return progress_file_name(self._ticket, self._session_id)

    def checkpoint(self, history: Sequence[Message]) -> None:
        """A turn ended: count it and write a complete checkpoint."""
        self._turns += 1
        self._write(CheckpointKind.CHECKPOINT, history)

    def finish(self, history: Sequence[Message]) -> None:
        """The session ends normally: write the final state (creating the file if needed)."""
        self._write(CheckpointKind.FINAL, history)

    def _write(self, kind: CheckpointKind, history: Sequence[Message]) -> None:
        try:
            items = self._criteria.load_criteria(self._session_id)
            snapshot = ProgressSnapshot(
                ticket=self._ticket or self._session_id,
                session_id=self._session_id,
                turn=self._turns,
                kind=kind,
                updated_at=self._clock(),
                objective=self._objective,
                criteria=tuple(_line(number, item) for number, item in enumerate(items, start=1)),
                note=_last_answer(history),
            )
            self._sink.write(self.file_name, render_progress(snapshot))
        except Exception:  # noqa: BLE001 - a copy must never fail the turn; the cause is not shown
            self._warn(WRITE_WARNING)
