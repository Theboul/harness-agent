"""In-memory implementation of the ``ToolRegistry`` port (HU-01-02).

The registry is plain domain logic: it needs nothing from outside the core, so it lives in
``core/tools/`` and takes no constructor arguments. It is synchronous and has no locks: it is
meant for a single event loop, and tools are registered at start-up.

Standard library only.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any

from harness_agent.core.interfaces.tool import RiskLevel, Tool, ToolRegistry
from harness_agent.core.tools.errors import (
    MAX_NAME_LENGTH,
    DuplicateToolError,
    InvalidToolDefinitionError,
    ToolValidationError,
    UnknownToolError,
)
from harness_agent.core.tools.output_limit import TruncatingTool, check_max_output_chars
from harness_agent.core.tools.schema_validator import check_schema, validate_arguments

_NAME_PATTERN = re.compile(rf"[A-Za-z0-9_-]{{1,{MAX_NAME_LENGTH}}}")

_NAME_PROBLEM = (
    "nombre: solo se admiten letras ASCII, dígitos, guion bajo y guion "
    f"(1 a {MAX_NAME_LENGTH} caracteres)."
)
_NAME_NOT_TEXT_PROBLEM = "nombre: debe ser un texto."
_DESCRIPTION_NOT_TEXT_PROBLEM = "descripción: debe ser un texto."
_DESCRIPTION_EMPTY_PROBLEM = "descripción: no puede estar vacía."

_UNCOPYABLE_SCHEMA_PROBLEM = (
    "esquema (raíz): contiene valores que no se pueden copiar; solo se admiten datos JSON."
)

_RISK_NAMES = [level.value for level in RiskLevel]
_RISK_PROBLEM = (
    f"riesgo: debe ser un RiskLevel ({', '.join(_RISK_NAMES[:-1])} o {_RISK_NAMES[-1]})."
)


def _name_problems(name: object) -> list[str]:
    if not isinstance(name, str):
        return [_NAME_NOT_TEXT_PROBLEM]
    if _NAME_PATTERN.fullmatch(name) is None:  # fullmatch: "nombre\n" must be rejected
        return [_NAME_PROBLEM]
    return []


def _description_problems(description: object) -> list[str]:
    if not isinstance(description, str):
        return [_DESCRIPTION_NOT_TEXT_PROBLEM]
    if not description.strip():
        return [_DESCRIPTION_EMPTY_PROBLEM]
    return []


def _risk_problems(risk: object) -> list[str]:
    return [] if isinstance(risk, RiskLevel) else [_RISK_PROBLEM]


def _check_and_copy_schema(schema: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Check a schema and, once it is accepted, take the deep copy that the catalog keeps.

    The copy is made only after ``check_schema`` accepts the schema, so a circular schema never
    reaches ``copy.deepcopy``. An accepted schema can still hold values that cannot be copied
    (``default``, ``examples`` and ``enum`` take any value): that is one more problem of the
    definition. At run time ``schema`` may not even be a dict; ``check_schema`` reports that.
    """
    problems = [f"esquema {problem}" for problem in check_schema(schema)]
    if problems:
        return problems, {}
    try:
        return [], copy.deepcopy(schema)
    except Exception:  # Arbitrary objects can fail to be copied in arbitrary ways.
        return [_UNCOPYABLE_SCHEMA_PROBLEM], {}


@dataclass(frozen=True)
class _Entry:
    """A registered tool, the deep copy of its schema taken at registration and the tool that
    is served to callers (the tool itself, or the tool wrapped so its results are bounded)."""

    tool: Tool
    schema: dict[str, Any]
    served: Tool


class InMemoryToolRegistry(ToolRegistry):
    """Tool catalog that lives in memory; registration order is the order of ``list()``.

    A registration either succeeds completely or leaves the catalog untouched. The catalog only
    grows: tools cannot be removed or replaced.

    With ``max_output_chars`` every tool is served wrapped in ``TruncatingTool`` (HU-02-02): the
    content of its results never exceeds the maximum and a notice says what was left out. Without
    it the registry serves the registered instances, as it did before.
    """

    def __init__(self, *, max_output_chars: int | None = None) -> None:
        """Create an empty registry.

        Args:
            max_output_chars: Longest content of a tool result, or ``None`` for no general limit.

        Raises:
            ValueError: ``max_output_chars`` is not ``None`` and not a valid maximum.
        """
        self._max_output_chars = (
            None if max_output_chars is None else check_max_output_chars(max_output_chars)
        )
        self._entries: dict[str, _Entry] = {}

    def register(self, tool: Tool) -> None:
        """Register ``tool``.

        Raises:
            InvalidToolDefinitionError: Its name, description, risk or schema is invalid; every
                problem found is reported together, in that order.
            DuplicateToolError: Another tool already has the same name (case-sensitive). This
                is checked only once the definition itself is valid.
        """
        # Each attribute is read once; everything below works on these values.
        name = tool.name
        description = tool.description
        risk = tool.risk
        schema = tool.schema

        schema_problems, schema_copy = _check_and_copy_schema(schema)
        problems = [
            *_name_problems(name),
            *_description_problems(description),
            *_risk_problems(risk),
            *schema_problems,
        ]
        if problems:
            raise InvalidToolDefinitionError(str(name), problems)
        if name in self._entries:
            raise DuplicateToolError(name)

        # Only now is the catalog modified.
        served = (
            tool if self._max_output_chars is None else TruncatingTool(tool, self._max_output_chars)
        )
        self._entries[name] = _Entry(tool, schema_copy, served)

    def _find_entry(self, name: object) -> _Entry | None:
        """The entry registered under exactly ``name``; ``None`` if there is none.

        The type is checked first: a name that is not text comes from the JSON of the model, a
        list or a mapping is not hashable and must not reach the lookup, and it must never match
        the text of a registered name either.
        """
        return self._entries.get(name) if isinstance(name, str) else None

    def get(self, name: str) -> Tool | None:
        """Return the tool registered under exactly ``name``, or ``None``.

        With a maximum, the tool returned is the registered one wrapped so its results are bounded.

        A ``name`` that is not text is an unknown tool, not an error.
        """
        entry = self._find_entry(name)
        return entry.served if entry is not None else None

    def validate_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Validate ``args`` against the schema that was stored when ``name`` was registered.

        Returns a shallow copy of ``args``, otherwise unchanged. The tool is never run.

        Raises:
            UnknownToolError: No tool is registered under ``name``. A ``name`` that is not text
                (it comes from the JSON of the model) is an unknown tool as well.
            ToolValidationError: ``args`` do not satisfy the schema; it carries every violation.
        """
        entry = self._find_entry(name)
        if entry is None:
            raise UnknownToolError(str(name))
        violations = validate_arguments(entry.schema, args)
        if violations:
            raise ToolValidationError(name, tuple(violations))
        return dict(args)

    # `list` must stay the last method: after it, `list[...]` in an annotation of this class
    # body would refer to this method instead of the builtin type (mypy).
    def list(self) -> list[Tool]:
        """Return a new list with the registered tools, in registration order."""
        return [entry.served for entry in self._entries.values()]
