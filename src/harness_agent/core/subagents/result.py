"""The structured result of a subagent (HU-09-03): schema, parsing, shortening and fixed codes.

The orchestrator never receives the transcript of a subagent, only an object with four fields
(``resultado``, ``hallazgos_clave``, ``fuentes``, ``error``) plus ``parcial``. The subagent ends its
work with a JSON object; ``parse_result`` checks it against a schema with the validator of the core
and returns ``None`` for anything else, never saying what was received. ``shorten_output`` keeps the
result brief. Every failure is a fixed code: what the subagent or the provider said about it is
never copied.

Standard library and ``core.tools.schema_validator`` only; nothing is read, printed or published.
"""

from __future__ import annotations

import json
import re
from typing import Any

from harness_agent.core.tools.schema_validator import check_schema, validate_arguments

MAX_RESULT_CHARS = 4_000
MAX_ITEM_CHARS = 500
MAX_ITEMS = 10
MAX_ERROR_CHARS = 500
MAX_RAW_CHARS = 100_000

INVALID_RESULT = "resultado_no_valido"
PROVIDER_FAILED = "fallo_del_proveedor"
INVALID_PROVIDER_RESPONSE = "respuesta_invalida_del_proveedor"
SUBAGENT_FAILED = "fallo_del_subagente"
NO_CHILD_SESSION = "sin_sesion_hija"
LIMIT_REACHED = "limite_alcanzado"

_ELLIPSIS = "…"
_KNOWN_LIMITS = ("turns", "time", "tokens")
_LIMIT_NAME = re.compile(r"'(" + "|".join(_KNOWN_LIMITS) + r")'")
_FENCE = re.compile(r"\A```[A-Za-z]*[ \t]*\n(.*?)\n?```\Z", re.DOTALL)

RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "resultado": {"type": "string", "description": "Lo que se encontró o se hizo, breve."},
        "hallazgos_clave": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Los datos más importantes, uno por elemento.",
        },
        "fuentes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Archivos o referencias consultados.",
        },
        "error": {
            "type": ["string", "null"],
            "description": "Solo si no se pudo cumplir el objetivo: por qué.",
        },
    },
    "required": ["resultado", "hallazgos_clave", "fuentes"],
    "additionalProperties": False,
}
"""The output schema of every delegation; callers pass a copy, never this object."""


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + _ELLIPSIS


def _texts(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clip(item, MAX_ITEM_CHARS) for item in value[:MAX_ITEMS] if isinstance(item, str)]


def parse_result(text: str, schema: dict[str, Any]) -> dict[str, Any] | None:
    """The JSON object in ``text`` if it complies with ``schema``, else ``None``.

    The object may come inside a code block. Text that is not JSON, a JSON that is not an object,
    an object that breaks the schema, a text that is too long, or a schema the validator does not
    accept all give ``None`` (fail closed); nothing of ``text`` is reproduced.
    """
    if not isinstance(text, str) or len(text) > MAX_RAW_CHARS or check_schema(schema):
        return None
    body = text.strip()
    fenced = _FENCE.match(body)
    if fenced is not None:
        body = fenced.group(1).strip()
    try:
        data = json.loads(body)
    except (ValueError, RecursionError):
        return None
    if not isinstance(data, dict) or validate_arguments(schema, data):
        return None
    return data


def shorten_output(data: dict[str, Any]) -> dict[str, Any]:
    """The brief output of a finished subagent: the five keys, texts and lists cut, not partial."""
    result = data.get("resultado")
    error = data.get("error")
    return {
        "resultado": _clip(result, MAX_RESULT_CHARS) if isinstance(result, str) else "",
        "hallazgos_clave": _texts(data.get("hallazgos_clave")),
        "fuentes": _texts(data.get("fuentes")),
        "error": _clip(error, MAX_ERROR_CHARS)
        if isinstance(error, str) and error.strip()
        else None,
        "parcial": False,
    }


def failure_output(code: str) -> dict[str, Any]:
    """The output of a subagent that produced nothing usable: only its fixed ``code``."""
    return {"resultado": "", "hallazgos_clave": [], "fuentes": [], "error": code, "parcial": False}


def partial_output(last_text: str | None, code: str) -> dict[str, Any]:
    """The output of a subagent stopped by a limit: what it had said last, cut, and the limit."""
    output = failure_output(code)
    output["resultado"] = _clip(last_text or "", MAX_RESULT_CHARS)
    output["parcial"] = True
    return output


def limit_code(turn_error: str | None) -> str:
    """``limite_alcanzado:<limit>`` if the turn names a known limit, else the bare code."""
    found = _LIMIT_NAME.search(turn_error) if isinstance(turn_error, str) else None
    return LIMIT_REACHED if found is None else f"{LIMIT_REACHED}:{found.group(1)}"
