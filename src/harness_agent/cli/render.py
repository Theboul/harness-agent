"""Text of the CLI: sanitizing, bounding and the tables of causes and suggested actions.

Everything the CLI shows that comes from the model, from a tool or from the user is data to be
shown, never something to interpret: control characters are removed (``sanitize``) and free text
is bounded (``bounded``). The tables hold, for every error category that the agent loop publishes
today, the cause and the suggested action in complete sentences in Spanish (contract section 3 of
``specs/009-basic-cli-events``). An unknown category uses a generic entry and is never reproduced.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from harness_agent.core import Event, EventType

MAX_NAME_CHARS = 64
MAX_PROVIDER_MESSAGE_CHARS = 200
MAX_COMMAND_CHARS = 40
ELLIPSIS = "..."
UNKNOWN_NAME = "(sin nombre)"
GENERIC_SUGGESTION = "Revisa el registro de eventos."
AGENT_PREFIX = "agente> "
CONTINUATION = " " * len(AGENT_PREFIX)

# Controls of text direction (U+202A-U+202E, U+2066-U+2069): they can fake what is on the screen.
_BIDIRECTIONAL_CONTROLS = frozenset(
    chr(code) for code in (*range(0x202A, 0x202F), *range(0x2066, 0x206A))
)
_KEPT_CONTROLS = "\n\t"


def sanitize(text: str) -> str:
    """Remove every control character (except line break and tab) and the bidirectional ones."""
    return "".join(
        char
        for char in text
        if char in _KEPT_CONTROLS
        or (unicodedata.category(char) != "Cc" and char not in _BIDIRECTIONAL_CONTROLS)
    )


def bounded(text: str, limit: int) -> str:
    """Cut ``text`` to ``limit`` characters, ending with ``...`` when something was removed."""
    if len(text) <= limit:
        return text
    return text[: max(limit - len(ELLIPSIS), 0)] + ELLIPSIS


@dataclass(frozen=True)
class ErrorGuide:
    """Cause and suggested action of one error category, with ``{name}``-style placeholders."""

    cause: str
    suggestion: str


TOOL_ERROR_GUIDE: Mapping[str, ErrorGuide] = MappingProxyType(
    {
        "unknown_tool": ErrorGuide(
            "La herramienta '{name}' no está registrada.",
            "Revisa el nombre de la herramienta o regístrala antes de volver a intentarlo.",
        ),
        "invalid_arguments": ErrorGuide(
            "Los argumentos de la herramienta '{name}' no son válidos.",
            "Corrige los argumentos según el esquema de la herramienta y vuelve a intentarlo.",
        ),
        "tool_exception": ErrorGuide(
            "La herramienta '{name}' falló al ejecutarse.",
            "Vuelve a intentarlo y, si se repite, revisa el registro de eventos.",
        ),
        "invalid_tool_result": ErrorGuide(
            "La herramienta '{name}' devolvió un resultado no válido.",
            "Revisa la implementación de la herramienta y el registro de eventos.",
        ),
        "tool_error": ErrorGuide(
            "La herramienta '{name}' terminó con un error.",
            "Revisa los datos de la llamada y vuelve a intentarlo; el detalle está en el "
            "historial de la sesión.",
        ),
    }
)
UNKNOWN_TOOL_ERROR_GUIDE = ErrorGuide(
    "Ocurrió un error de categoría desconocida en la herramienta '{name}'.",
    GENERIC_SUGGESTION,
)

PERMISSION_GUIDE: Mapping[str, ErrorGuide] = MappingProxyType(
    {
        "deny": ErrorGuide(
            "La herramienta '{name}' fue denegada por la política de permisos.",
            "Si debe permitirse, ajusta la política de permisos; mientras esté denegada el "
            "agente no la ejecutará.",
        ),
        "policy_error": ErrorGuide(
            "No se pudo evaluar la política de permisos para '{name}'; se denegó por seguridad.",
            "Revisa la política de permisos configurada.",
        ),
        "ask": ErrorGuide(
            "La herramienta '{name}' requiere aprobación, que no está disponible en esta "
            "sesión; se resolvió como denegada.",
            "Pide una acción que no requiera aprobación o espera a que esté disponible la "
            "aprobación interactiva.",
        ),
    }
)
UNKNOWN_PERMISSION_GUIDE = ErrorGuide(
    "Se recibió una decisión de permiso desconocida para '{name}'.",
    GENERIC_SUGGESTION,
)

PROVIDER_GUIDE: Mapping[str, ErrorGuide] = MappingProxyType(
    {
        "provider_exception": ErrorGuide(
            "El proveedor del modelo falló ({error_type}): {message}",
            "Comprueba la conexión y la clave del proveedor y vuelve a intentarlo.",
        ),
        "invalid_response": ErrorGuide(
            "El proveedor del modelo devolvió una respuesta no válida ({error_type}).",
            "Vuelve a intentarlo y, si se repite, revisa el registro de eventos.",
        ),
    }
)
UNKNOWN_PROVIDER_GUIDE = ErrorGuide(
    "El proveedor del modelo falló ({error_type}).",
    GENERIC_SUGGESTION,
)

LIMIT_GUIDE = ErrorGuide(
    "Se alcanzó un límite de la sesión.",
    "Revisa los límites en la configuración y empieza una tarea nueva.",
)
# One guide per limit of the session (HU-01-06); the maximum is the only value read from the event.
LIMIT_SUGGESTION = "Ajusta [limits] en la configuración y empieza una sesión nueva."
LIMIT_KIND_GUIDE: Mapping[str, ErrorGuide] = MappingProxyType(
    {
        "turns": ErrorGuide(
            "Se alcanzó el máximo de {maximum} turnos de la sesión.", LIMIT_SUGGESTION
        ),
        "time": ErrorGuide(
            "Se alcanzó el tiempo máximo de {maximum} segundos de la sesión.", LIMIT_SUGGESTION
        ),
        "tokens": ErrorGuide(
            "Se alcanzó el presupuesto de {maximum} tokens de la sesión.", LIMIT_SUGGESTION
        ),
    }
)


# ---------------------------------------------------------------------- events

SHOWN_TYPES: tuple[EventType, ...] = (
    EventType.TOOL_REQUESTED,
    EventType.TOOL_FINISHED,
    EventType.ASSISTANT_MESSAGE,
    EventType.PERMISSION_DECIDED,
    EventType.APPROVAL_RESOLVED,
    EventType.CONTEXT_COMPACTED,
    EventType.PROVIDER_ERROR,
    EventType.LIMIT_REACHED,
)
# Categories whose error was already reported by the permission decision: only the final state.
_FINAL_STATE_ONLY = frozenset(
    {
        "permission_denied",
        "approval_required_unavailable",
        "approval_rejected",
        "approval_failed",
    }
)
_SENTENCE_ENDINGS = (".", "!", "?")


def _text(value: object, limit: int, default: str) -> str:
    """A payload value as safe text: sanitized and bounded, or ``default`` if it is not text."""
    if not isinstance(value, str):
        return default
    clean = sanitize(value)
    return bounded(clean, limit) if clean.strip() else default


def _name(payload: Mapping[str, Any]) -> str:
    """The tool name of the payload: sanitized and bounded, or ``UNKNOWN_NAME``."""
    return _text(payload.get("name"), MAX_NAME_CHARS, UNKNOWN_NAME)


def _error_line(label: str, guide: ErrorGuide, **values: str) -> str:
    """``[x] <label>: <cause> Sugerencia: <suggestion>`` with the values in the placeholders."""
    cause = guide.cause.format(**values)
    return f"[x] {label}: {cause} Sugerencia: {guide.suggestion}"


def _assistant_lines(payload: Mapping[str, Any]) -> str | None:
    content = payload.get("content")
    if not isinstance(content, str):
        return None
    text = sanitize(content).strip("\n")
    if not text.strip():
        return None
    first, *rest = text.split("\n")
    return "\n".join([f"{AGENT_PREFIX}{first}", *(f"{CONTINUATION}{line}" for line in rest)])


def _tool_finished(payload: Mapping[str, Any], duration: str | None = None) -> str:
    name = _name(payload)
    is_error = payload.get("is_error")
    if is_error is False:
        return f"  [ok] {name}: correcto" + (f" ({duration})" if duration else "")
    category = payload.get("category")
    if is_error is True and isinstance(category, str):
        if category in _FINAL_STATE_ONLY:
            return f"  [x] {name}: no se ejecutó."
        guide = TOOL_ERROR_GUIDE.get(category)
        if guide is not None:
            return "  " + _error_line("Error", guide, name=name)
    return "  " + _error_line("Error", UNKNOWN_TOOL_ERROR_GUIDE, name=name)


def _permission_decided(payload: Mapping[str, Any]) -> str | None:
    decision = payload.get("decision")
    if decision == "allow":
        return None
    name = _name(payload)
    if decision == "deny":
        case = "policy_error" if payload.get("reason") == "policy_error" else "deny"
        return "  " + _error_line("Permiso", PERMISSION_GUIDE[case], name=name)
    if decision == "ask":
        if payload.get("resolved_as") == "ask":
            return None  # waiting for the user: the approver shows the question (HU-05-03)
        return "  " + _error_line("Permiso", PERMISSION_GUIDE["ask"], name=name)
    return "  " + _error_line("Permiso", UNKNOWN_PERMISSION_GUIDE, name=name)


def _provider_message(value: object) -> str | None:
    """The provider message on one line, bounded, ending in a sentence mark; ``None`` if empty."""
    if not isinstance(value, str):
        return None
    one_line = " ".join(sanitize(value).split())
    if not one_line:
        return None
    message = bounded(one_line, MAX_PROVIDER_MESSAGE_CHARS)
    return message if message.endswith(_SENTENCE_ENDINGS) else message + "."


def _provider_error(payload: Mapping[str, Any]) -> str:
    error_type = _text(payload.get("error_type"), MAX_NAME_CHARS, "Error")
    reason = payload.get("reason")
    if reason == "provider_exception":
        message = _provider_message(payload.get("message"))
        if message is not None:
            guide = PROVIDER_GUIDE["provider_exception"]
            return _error_line("Error", guide, error_type=error_type, message=message)
        guide = ErrorGuide(
            UNKNOWN_PROVIDER_GUIDE.cause, PROVIDER_GUIDE["provider_exception"].suggestion
        )
        return _error_line("Error", guide, error_type=error_type)
    if reason == "invalid_response":
        return _error_line("Error", PROVIDER_GUIDE["invalid_response"], error_type=error_type)
    return _error_line("Error", UNKNOWN_PROVIDER_GUIDE, error_type=error_type)


def _limit_reached(payload: Mapping[str, Any]) -> str:
    """Name the limit and its maximum; anything unexpected keeps the generic line."""
    limit = payload.get("limit")
    maximum = payload.get("maximum")
    guide = LIMIT_KIND_GUIDE.get(limit) if isinstance(limit, str) else None
    if guide is None or isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        return _error_line("Límite", LIMIT_GUIDE)
    return _error_line("Límite", guide, maximum=str(maximum))


APPROVAL_WORDS: Mapping[str, str] = MappingProxyType(
    {
        "approve_once": "aprobado una vez",
        "approve_session": "aprobado para la sesión",
        "reject": "rechazado",
    }
)


def _approval_resolved(payload: Mapping[str, Any]) -> str:
    """What the person decided; anything unexpected (an approver failure) reads as a rejection."""
    action = payload.get("action")
    key = action if isinstance(action, str) and action in APPROVAL_WORDS else "reject"
    return f"  [?] {_name(payload)}: {APPROVAL_WORDS[key]}"


def _context_compacted(payload: Mapping[str, Any]) -> str:
    count = payload.get("eventos")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return "  [~] Contexto compactado."
    return f"  [~] Contexto compactado: {count} eventos resumidos."


def render_event(event: Event, duration: str | None = None) -> str | None:
    """The text to show for ``event``, or ``None`` when the type is not shown or has nothing.

    ``duration`` is the already formatted time of a finished tool, when the caller could derive it.

    Only the fields that the agent loop publishes are read; a missing or unexpected field never
    raises: a neutral value is used instead. The text never contains a stack trace, an internal
    object, the raw payload or an unknown category.
    """
    payload = event.payload
    if event.type is EventType.TOOL_REQUESTED:
        return f"  [..] {_name(payload)}: ejecutando"
    if event.type is EventType.TOOL_FINISHED:
        return _tool_finished(payload, duration)
    if event.type is EventType.ASSISTANT_MESSAGE:
        return _assistant_lines(payload)
    if event.type is EventType.PERMISSION_DECIDED:
        return _permission_decided(payload)
    if event.type is EventType.APPROVAL_RESOLVED:
        return _approval_resolved(payload)
    if event.type is EventType.CONTEXT_COMPACTED:
        return _context_compacted(payload)
    if event.type is EventType.PROVIDER_ERROR:
        return _provider_error(payload)
    if event.type is EventType.LIMIT_REACHED:
        return _limit_reached(payload)
    return None


def turn_failure_line(error_type: str) -> str:
    """The one line shown when the turn function fails (D9): the type only, never the message."""
    shown = _text(error_type, MAX_NAME_CHARS, "Error")
    return (
        f"[x] Error: el turno terminó con un fallo interno ({shown}). "
        "Sugerencia: revisa el registro de eventos."
    )
