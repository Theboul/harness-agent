"""Domain errors of the tool registry and the model-facing text of their messages.

Every error derives from ``ValueError`` because the ``ToolRegistry`` port already declares
``ValueError`` for name collisions and invalid arguments, so the port stays unchanged.

``str(error)`` is the final text handed back to the language model (contract, section 3):
Spanish, one ``- <path>: <reason>`` line per violation, and never the values that were received.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

MAX_NAME_LENGTH = 64
MAX_RENDERED_VIOLATIONS = 20
MAX_PATH_DISPLAY = 80

_ELLIPSIS = "…"
_ROOT_PATH_LABEL = "(argumentos)"


def clip(text: str, limit: int) -> str:
    """Return ``text`` as is, or cut it so that, ellipsis included, it has ``limit`` characters.

    Shared by the error texts and the validator; internal to ``core.tools``, not public API.
    """
    if len(text) <= limit:
        return text
    return text[: limit - 1] + _ELLIPSIS


@dataclass(frozen=True)
class Violation:
    """One concrete way in which the arguments of a call break the schema of a tool.

    Attributes:
        path: Field path from the root of the arguments; ``""`` means the arguments as a whole.
            Nested fields are separated by dots (``opciones.tiempo_maximo``) and list items
            carry an index (``archivos[2].ruta``).
        message: Reason in Spanish, written as a complete sentence that ends with a period and
            never contains received values. The validator guarantees the final period: the error
            text prints the message verbatim after ``<path>: `` and adds no punctuation.
    """

    path: str
    message: str


class ToolRegistryError(ValueError):
    """Base class of every error raised by the tool registry."""


class InvalidToolDefinitionError(ToolRegistryError):
    """A tool was rejected at registration because its definition is invalid.

    Attributes:
        tool_name: Name the tool declared (it may itself be the invalid part).
        problems: Every problem found, each one already written for display.
    """

    def __init__(self, tool_name: str, problems: Sequence[str]) -> None:
        self.tool_name = tool_name
        self.problems = tuple(problems)
        super().__init__(tool_name, self.problems)

    def __str__(self) -> str:
        name = clip(self.tool_name, MAX_NAME_LENGTH)
        header = f"Definición inválida de la herramienta '{name}':"
        return "\n".join([header, *(f"- {problem}" for problem in self.problems)])


class DuplicateToolError(ToolRegistryError):
    """A tool was rejected at registration because its name is already taken.

    Attributes:
        tool_name: The repeated name.
    """

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(tool_name)

    def __str__(self) -> str:
        name = clip(self.tool_name, MAX_NAME_LENGTH)
        return f"Ya existe una herramienta registrada con el nombre '{name}'."


class UnknownToolError(ToolRegistryError):
    """A call named a tool that is not registered.

    Attributes:
        tool_name: The name that was requested.
    """

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(tool_name)

    def __str__(self) -> str:
        return f"Herramienta desconocida: '{clip(self.tool_name, MAX_NAME_LENGTH)}'."


class ToolValidationError(ToolRegistryError):
    """The arguments of a call do not satisfy the schema of the tool.

    The text shows at most ``MAX_RENDERED_VIOLATIONS`` violations and summarises the rest;
    ``violations`` always keeps all of them.

    Attributes:
        tool_name: Name of the tool that was called.
        violations: Every violation found, in the order the validator reported them.
    """

    def __init__(self, tool_name: str, violations: Sequence[Violation]) -> None:
        self.tool_name = tool_name
        self.violations = tuple(violations)
        super().__init__(tool_name, self.violations)

    def __str__(self) -> str:
        name = clip(self.tool_name, MAX_NAME_LENGTH)
        lines = [f"Argumentos inválidos para la herramienta '{name}':"]
        for violation in self.violations[:MAX_RENDERED_VIOLATIONS]:
            path = clip(violation.path, MAX_PATH_DISPLAY) if violation.path else _ROOT_PATH_LABEL
            lines.append(f"- {path}: {violation.message}")
        omitted = len(self.violations) - MAX_RENDERED_VIOLATIONS
        if omitted > 0:
            noun = "violación" if omitted == 1 else "violaciones"
            lines.append(f"- … y {omitted} {noun} más.")
        return "\n".join(lines)
