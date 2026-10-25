"""General limit for the output of tools (HU-02-02).

``truncate_output`` is the pure rule: a text that does not fit is cut in the middle, keeping its
beginning and its end, and a visible notice says how many characters were left out.
``TruncatingTool`` applies that rule to the result of any tool, so the registry can serve every
registered tool bounded without the tool knowing about it.

The notice has the same text as the one the shell adapter writes (HU-01-04): the model sees a
single form of warning. Standard library only.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from harness_agent.core.entities import ToolResult
from harness_agent.core.interfaces.tool import RiskLevel, Tool

DEFAULT_MAX_OUTPUT_CHARS = 24_000
"""Default maximum. The tools bound their own body to 20 000 characters and add a short header:
this leaves room so that an output already bounded by its tool is not cut a second time."""

MIN_MAX_OUTPUT_CHARS = 256
"""Smallest maximum accepted: it leaves room for the notice and for useful text around it."""

_MAX_REJECTED = (
    f"El máximo de salida de una herramienta debe ser un entero de al menos "
    f"{MIN_MAX_OUTPUT_CHARS} caracteres."
)


def omission_notice(omitted: int) -> str:
    """The visible notice that goes between the kept beginning and the kept end."""
    return f"\n[salida recortada: se omitieron {omitted} caracteres]\n"


def check_max_output_chars(value: object) -> int:
    """Return ``value`` if it is a usable maximum.

    Raises:
        ValueError: ``value`` is not an integer (a boolean is not one) of at least
            ``MIN_MAX_OUTPUT_CHARS``. The message never repeats the value.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < MIN_MAX_OUTPUT_CHARS:
        raise ValueError(_MAX_REJECTED)
    return value


def truncate_output(text: str, max_chars: int) -> str:
    """Return ``text`` if it fits in ``max_chars``; otherwise its beginning, a notice and its end.

    The result is never longer than ``max_chars`` and the notice states exactly how many
    characters were omitted. Characters are counted as Python counts them.

    Raises:
        ValueError: ``max_chars`` is not a valid maximum (see ``check_max_output_chars``).
    """
    check_max_output_chars(max_chars)
    total = len(text)
    if total <= max_chars:
        return text
    # The number of omitted characters cannot have more digits than the length of the text, so
    # the notice written for the length is an upper bound of the real one.
    kept = max_chars - len(omission_notice(total))
    head = kept // 2
    tail = kept - head
    return text[:head] + omission_notice(total - kept) + text[total - tail :]


class TruncatingTool(Tool):
    """A tool that delegates everything to another one and bounds the content of its results.

    ``call_id`` and ``is_error`` are never changed, exceptions and cancellation propagate and the
    arguments are handed over as they came.
    """

    def __init__(self, inner: Tool, max_chars: int) -> None:
        """Wrap ``inner``.

        Raises:
            ValueError: ``max_chars`` is not a valid maximum.
        """
        self._inner = inner
        self._max_chars = check_max_output_chars(max_chars)

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def description(self) -> str:
        return self._inner.description

    @property
    def schema(self) -> dict[str, Any]:
        return self._inner.schema

    @property
    def risk(self) -> RiskLevel:
        return self._inner.risk

    async def run(self, args: dict[str, Any]) -> ToolResult:
        """Run the tool and cut the content of its result when it exceeds the maximum."""
        result = await self._inner.run(args)
        # Anything that is not a well-formed result goes back untouched: the loop rejects it.
        if not isinstance(result, ToolResult) or not isinstance(result.content, str):
            return result
        if len(result.content) <= self._max_chars:
            return result
        return dataclasses.replace(result, content=truncate_output(result.content, self._max_chars))
