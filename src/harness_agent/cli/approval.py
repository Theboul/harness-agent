"""Approval prompt of the terminal: shows what is asked and reads the user's choice (HU-05-03).

``ConsoleApprover`` implements the ``Approver`` port for the CLI. It shows the tool, its arguments
and the expected effect, then reads ``1`` (approve once), ``2`` (approve for the session) or ``3``
(reject). It fails closed on its own: the end of the input, or an invalid option repeated
``max_attempts`` times, is a rejection; the invalid text is never echoed. The values of arguments
whose name looks like a secret are hidden. A broken stream raises; the approval gate of the core
turns that into a denial.

The input is read with the same blocking ``readline`` that ``run_cli`` uses, from the same stream.
"""

from __future__ import annotations

import sys
from typing import Any, TextIO

from harness_agent.core import ApprovalAction, ApprovalResult, Approver, ToolCall

from .app import put_line
from .render import bounded, sanitize

MAX_VALUE_CHARS = 200
MAX_EFFECT_CHARS = 200
MAX_NAME_CHARS = 64
MAX_ARGUMENTS_SHOWN = 20
DEFAULT_ATTEMPTS = 3
HIDDEN_VALUE = "***"
NO_EFFECT = "(sin descripción)"
SECRET_WORDS = ("key", "secret", "token", "password", "passwd", "credential", "auth")
RISK_NAMES = {"low": "bajo", "medium": "medio", "high": "alto"}
UNKNOWN_RISK = "desconocido"
OPTIONS_LINE = "  [1] aprobar una vez  [2] aprobar para la sesión  [3] rechazar"
PROMPT = "opción> "
INVALID_OPTION = "Opción no válida: escribe 1, 2 o 3."
CHOICES = {
    "1": ApprovalAction.APPROVE_ONCE,
    "2": ApprovalAction.APPROVE_SESSION,
    "3": ApprovalAction.REJECT,
}


def _one_line(value: object, limit: int) -> str:
    text = value if isinstance(value, str) else repr(value)
    return bounded(" ".join(sanitize(text).split()), limit)


def _argument_lines(arguments: object) -> list[str]:
    if not isinstance(arguments, dict):
        return []
    lines: list[str] = []
    for position, (name, value) in enumerate(arguments.items()):
        if position == MAX_ARGUMENTS_SHOWN:
            lines.append(f"  ... (y {len(arguments) - MAX_ARGUMENTS_SHOWN} más)")
            break
        shown_name = _one_line(name, MAX_NAME_CHARS)
        hidden = any(word in str(name).lower() for word in SECRET_WORDS)
        shown_value = HIDDEN_VALUE if hidden else _one_line(value, MAX_VALUE_CHARS)
        lines.append(f"  {shown_name}: {shown_value}")
    return lines


def _effect_line(details: dict[str, Any]) -> str:
    effect = details.get("effect")
    text = _one_line(effect, MAX_EFFECT_CHARS) if isinstance(effect, str) and effect else ""
    risk = details.get("risk")
    risk_name = RISK_NAMES.get(risk, UNKNOWN_RISK) if isinstance(risk, str) else UNKNOWN_RISK
    return f"  efecto: {text or NO_EFFECT} (riesgo: {risk_name})"


class ConsoleApprover(Approver):
    """Asks the user in the terminal; ``input_stream``/``output`` default to the standard ones.

    Args:
        input_stream: Where the choice is read from (``sys.stdin`` when ``None``).
        output: Where the question is written (``sys.stdout`` when ``None``).
        max_attempts: Invalid answers tolerated before the request is rejected (at least 1).
    """

    def __init__(
        self,
        input_stream: TextIO | None = None,
        output: TextIO | None = None,
        *,
        max_attempts: int = DEFAULT_ATTEMPTS,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("Debe haber al menos un intento.")
        self._input = input_stream
        self._output = output
        self._max_attempts = max_attempts

    async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
        """Show the detail and read the choice; reject on the end of the input."""
        source = sys.stdin if self._input is None else self._input
        stream = sys.stdout if self._output is None else self._output
        tool = details.get("tool") if isinstance(details.get("tool"), str) else call.name
        put_line(stream, f"[!] El agente quiere ejecutar: {_one_line(tool, MAX_NAME_CHARS)}")
        for line in _argument_lines(details.get("arguments")):
            put_line(stream, line)
        put_line(stream, _effect_line(details))
        put_line(stream, OPTIONS_LINE)
        for _ in range(self._max_attempts):
            put_line(stream, PROMPT, end="")
            answer = source.readline()
            if answer == "":  # end of the input
                put_line(stream, "")
                return ApprovalResult(ApprovalAction.REJECT)
            action = CHOICES.get(answer.strip())
            if action is not None:
                return ApprovalResult(action)
            put_line(stream, INVALID_OPTION)
        return ApprovalResult(ApprovalAction.REJECT)
