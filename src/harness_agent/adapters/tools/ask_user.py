"""AskUserTool: asks the person a question with options (HU-06-02, ``preguntar_usuario``).

The model uses it when the task is ambiguous. The tool asks nothing itself: it receives by
constructor an ``ask`` function (``AskFn``) that shows the question and returns the answer; the
composition root connects the one of the console. Types and function belong to this adapter, not
to the core: there is no port for it. The tool executes nothing, so its risk is low.

It fails closed: no answer, an answer that makes no sense, a free text where only the options are
allowed or a failure of ``ask`` is a tagged error (``[sin_respuesta]``), never an option chosen by
default. The free text is cleaned like a rejection reason; nothing of it goes to an event.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from harness_agent.adapters.tools._limits import (
    MAX_OPTION_CHARS,
    MAX_OPTIONS,
    MAX_QUESTION_CHARS,
    MIN_OPTIONS,
)
from harness_agent.adapters.tools._paths import error_result
from harness_agent.core import RiskLevel, Tool, ToolResult, clean_reason


@dataclass(frozen=True)
class Question:
    """What is shown to the person: a text, the options in order and whether free text is fine."""

    text: str
    options: tuple[str, ...]
    allow_free_text: bool = True


@dataclass(frozen=True)
class Answer:
    """What the person answered: the number of an option (1-based) or a free text."""

    number: int | None = None
    text: str = ""


AskFn = Callable[[Question], Awaitable[Answer | None]]
"""Shows the question and returns the answer; ``None`` when there is none (end of input...)."""

_NO_ANSWER = (
    "La persona no respondió a la pregunta. No elijas una opción por tu cuenta: "
    "explica qué falta o vuelve a preguntar."
)
_DROPPED = frozenset({"Cc", "Cf", "Cs", "Co", "Cn"})


def _one_line(value: object, limit: int) -> str:
    """``value`` as one line of printable text, bounded; empty when nothing usable is left."""
    if not isinstance(value, str):
        return ""
    kept = "".join(
        " " if char.isspace() else char
        for char in value
        if char.isspace() or unicodedata.category(char) not in _DROPPED
    )
    text = " ".join(kept.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


class AskUserTool(Tool):
    """Ask a question with numbered options; the answer comes back as the tool result."""

    def __init__(self, ask: AskFn) -> None:
        self._ask = ask

    @property
    def name(self) -> str:
        return "preguntar_usuario"

    @property
    def description(self) -> str:
        return (
            "Hace una pregunta a la persona con opciones numeradas cuando la tarea es ambigua y "
            "no debes adivinar. Devuelve la opción elegida o, si se permite, un texto libre. "
            f"Usa entre {MIN_OPTIONS} y {MAX_OPTIONS} opciones cortas."
        )

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pregunta": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_QUESTION_CHARS,
                    "description": "La pregunta para la persona.",
                },
                "opciones": {
                    "type": "array",
                    "minItems": MIN_OPTIONS,
                    "maxItems": MAX_OPTIONS,
                    "items": {"type": "string", "minLength": 1, "maxLength": MAX_OPTION_CHARS},
                    "description": "Opciones predefinidas, en el orden en que se muestran.",
                },
                "permitir_texto_libre": {
                    "type": "boolean",
                    "description": "Si la persona puede escribir otra respuesta (por defecto sí).",
                },
            },
            "required": ["pregunta", "opciones"],
            "additionalProperties": False,
        }

    @property
    def risk(self) -> RiskLevel:
        return RiskLevel.LOW

    async def run(self, args: dict[str, Any]) -> ToolResult:
        text = _one_line(args.get("pregunta"), MAX_QUESTION_CHARS)
        if not text:
            return error_result("pregunta_invalida", "La pregunta queda vacía tras limpiarla.")
        raw_options = args.get("opciones")
        options = tuple(
            _one_line(option, MAX_OPTION_CHARS)
            for option in (raw_options if isinstance(raw_options, list) else [])
        )
        if (
            not MIN_OPTIONS <= len(options) <= MAX_OPTIONS
            or not all(options)
            or len({option.casefold() for option in options}) != len(options)
        ):
            return error_result(
                "opciones_invalidas",
                f"Indica de {MIN_OPTIONS} a {MAX_OPTIONS} opciones distintas y con texto.",
            )
        allow_free_text = args.get("permitir_texto_libre", True) is not False
        question = Question(text, options, allow_free_text)
        try:
            answer = await self._ask(question)
        except Exception:
            return error_result("sin_respuesta", _NO_ANSWER)
        return self._result(answer, question)

    @staticmethod
    def _result(answer: object, question: Question) -> ToolResult:
        if not isinstance(answer, Answer):
            return error_result("sin_respuesta", _NO_ANSWER)
        number = answer.number
        if number is not None:
            if isinstance(number, bool) or not 1 <= number <= len(question.options):
                return error_result("sin_respuesta", _NO_ANSWER)
            chosen = question.options[number - 1]
            return ToolResult(
                call_id="", content=f"Respuesta de la persona: opción {number}: {chosen}"
            )
        free = clean_reason(answer.text) if question.allow_free_text else None
        if free is None:
            return error_result("sin_respuesta", _NO_ANSWER)
        return ToolResult(call_id="", content=f"Respuesta de la persona (texto libre): {free}")
