"""The block that asks the user to approve a tool call: pure text, no input or output (HU-06-05).

The block answers, from top to bottom, what the agent wants to do, with what, how risky it is and
what the options are. The command or path is highlighted on its own line. Everything that comes
from the model (names, values, effect) is data to show: control characters are removed, line breaks
are written as ``\\n`` so a value never breaks the layout, and every value is bounded. The values of
arguments whose name looks like a secret are hidden. The decoration is ASCII on purpose.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .render import bounded, sanitize
from .style import PLAIN, Style

RULE_WIDTH = 60
MAX_PRIMARY_CHARS = 400
MAX_VALUE_CHARS = 200
MAX_EFFECT_CHARS = 200
MAX_NAME_CHARS = 64
MAX_ARGUMENTS_SHOWN = 20
HIDDEN_VALUE = "***"
NO_EFFECT = "(sin descripción)"
EMPTY_VALUE = "(vacío)"
SECRET_WORDS = ("key", "secret", "token", "password", "passwd", "credential", "auth")
RISK_NAMES = {"low": "BAJO", "medium": "MEDIO", "high": "ALTO"}
RISK_COLORS = {"BAJO": "green", "MEDIO": "yellow", "ALTO": "red"}
UNKNOWN_RISK = "DESCONOCIDO"
TITLE = " APROBACIÓN REQUERIDA"
OPTIONS_LINE = " [1] aprobar una vez   [2] aprobar para la sesión   [3] rechazar"
# The arguments that say what the call does, in order of preference, and the sentence of each.
PRIMARY_ARGUMENTS = ("command", "path")
_INDENT = "     "


def _escaped(value: object, limit: int) -> str:
    """``value`` on one line: controls out, line breaks as ``\\n``, tabs as spaces, bounded."""
    text = value if isinstance(value, str) else repr(value)
    one_line = (
        sanitize(text)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace("\t", " ")
    )
    return bounded(one_line, limit)


def _is_secret(name: object) -> bool:
    lowered = str(name).lower()
    return any(word in lowered for word in SECRET_WORDS)


def _shown(name: object, value: object, limit: int) -> str:
    if _is_secret(name):
        return HIDDEN_VALUE
    shown = _escaped(value, limit)
    return shown if shown.strip() else EMPTY_VALUE


def _primary_key(arguments: Mapping[str, Any]) -> str | None:
    for key in PRIMARY_ARGUMENTS:
        if key in arguments:
            return key
    return None


def _sentence(primary: str | None, tool: str) -> str:
    if primary == "command":
        return " El agente quiere ejecutar un comando:"
    if primary == "path":
        return f" El agente quiere usar la ruta indicada con '{tool}':"
    return f" El agente quiere usar la herramienta '{tool}'."


def _risk(details: Mapping[str, Any], style: Style) -> str:
    risk = details.get("risk")
    word = RISK_NAMES.get(risk, UNKNOWN_RISK) if isinstance(risk, str) else UNKNOWN_RISK
    return style.paint(word, "bold", RISK_COLORS.get(word, "yellow"))


def _effect(details: Mapping[str, Any]) -> str:
    effect = details.get("effect")
    text = _escaped(effect, MAX_EFFECT_CHARS) if isinstance(effect, str) else ""
    return text if text.strip() else NO_EFFECT


def _argument_lines(arguments: Mapping[str, Any], primary: str | None) -> list[str]:
    rest = [(name, value) for name, value in arguments.items() if name != primary]
    if not rest:
        return []
    lines = [" Argumentos:"]
    for position, (name, value) in enumerate(rest):
        if position == MAX_ARGUMENTS_SHOWN:
            lines.append(f"   ... (y {len(rest) - MAX_ARGUMENTS_SHOWN} más)")
            break
        shown_name = _escaped(name, MAX_NAME_CHARS)
        lines.append(f"   {shown_name}: {_shown(name, value, MAX_VALUE_CHARS)}")
    return lines


def approval_block(tool_name: str, details: Mapping[str, Any], style: Style = PLAIN) -> list[str]:
    """The lines of the approval question for ``details`` (what the ``Approver`` port receives).

    Args:
        tool_name: Name of the tool of the call, used when ``details`` does not carry a valid one.
        details: The detail of the request: ``tool``, ``arguments``, ``effect`` and ``risk``.
        style: Paints the title, the highlighted value and the risk; the text is the same without.
    """
    raw_tool = details.get("tool")
    tool = _escaped(raw_tool if isinstance(raw_tool, str) else tool_name, MAX_NAME_CHARS)
    raw_arguments = details.get("arguments")
    arguments: Mapping[str, Any] = raw_arguments if isinstance(raw_arguments, dict) else {}
    primary = _primary_key(arguments)
    rule, thin = "=" * RULE_WIDTH, "-" * RULE_WIDTH
    lines = [rule, style.paint(TITLE, "bold"), thin, _sentence(primary, tool)]
    if primary is not None:
        highlighted = _shown(primary, arguments[primary], MAX_PRIMARY_CHARS)
        lines.append(_INDENT + style.paint(highlighted, "bold", "cyan"))
    lines.append(f" Herramienta: {tool}")
    lines.extend(_argument_lines(arguments, primary))
    lines.append(f" Riesgo:      {_risk(details, style)}")
    lines.append(f" Efecto:      {_effect(details)}")
    lines.extend([thin, OPTIONS_LINE])
    return lines
