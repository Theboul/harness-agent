"""Verification commands of a task: the tests and the lint the agent may run (HU-11-03).

A task may declare, in its ``## Comandos`` section, one command for the tests and one for the
lint, each with a time limit. They are data: what may run without asking is decided by the
permission policy that the composition root builds from them. ``commands_notice`` writes the text
that tells the model which exact commands it has.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

DEFAULT_COMMAND_TIMEOUT_SECONDS = 300
MAX_COMMAND_TIMEOUT_SECONDS = 600
# Same bound as the other fields of a task (``MAX_FIELD_CHARS``); kept here to avoid a cycle.
MAX_COMMAND_TEXT_CHARS = 2_000


class CommandKind(str, Enum):
    """What the command checks; the value is the key of its line in the task."""

    TESTS = "pruebas"
    LINT = "lint"


def _is_one_line(text: str) -> bool:
    return not any(ord(ch) < 32 or ord(ch) == 127 for ch in text)


@dataclass(frozen=True)
class TaskCommand:
    """One declared command.

    Attributes:
        kind: Tests or lint.
        command: The exact text that may run, on one line and without outer spaces.
        timeout_seconds: Time limit of a run, from 1 to ``MAX_COMMAND_TIMEOUT_SECONDS``.
    """

    kind: CommandKind
    command: str
    timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CommandKind):
            raise ValueError("El tipo del comando debe ser 'pruebas' o 'lint'.")
        text = self.command
        if (
            not isinstance(text, str)
            or not text.strip()
            or text != text.strip()
            or len(text) > MAX_COMMAND_TEXT_CHARS
            or not _is_one_line(text)
        ):
            raise ValueError(
                "El comando debe ser un texto de una línea, sin espacios en los extremos y de "
                f"hasta {MAX_COMMAND_TEXT_CHARS} caracteres."
            )
        seconds = self.timeout_seconds
        if type(seconds) is not int or not 1 <= seconds <= MAX_COMMAND_TIMEOUT_SECONDS:
            raise ValueError(
                f"El tiempo máximo del comando debe ser un entero de 1 a "
                f"{MAX_COMMAND_TIMEOUT_SECONDS} segundos."
            )


def commands_notice(commands: Sequence[TaskCommand]) -> str | None:
    """The text that tells the model which commands run without asking, or ``None`` if none."""
    if not commands:
        return None
    lines = [
        "Comandos de verificación de la tarea. Solo estos textos exactos se ejecutan con el shell "
        "sin pedir aprobación, indicando un tiempo máximo que no supere el de cada uno; cualquier "
        "variación (otro texto, comandos encadenados, más tiempo) pide aprobación:"
    ]
    lines.extend(
        f"- {command.kind.value}: `{command.command}` (tiempo máximo: {command.timeout_seconds} s)"
        for command in commands
    )
    return "\n".join(lines)
