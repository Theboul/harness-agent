"""Validation of the ``[mcp_servers.<name>]`` section of the configuration (HU-08-01).

Pure functions with no file or environment access: ``config.py`` reads the file and calls
``check_mcp_servers`` with the table; the problems come back as ``(field, message)`` pairs that
``config.py`` turns into its own ``ConfigProblem``. The messages are complete sentences in Spanish
and never show the value they received.

The ``env`` field lists **names** of variables of the parent environment that the server receives:
the file holds no value and therefore no secret.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

MCP_TABLE = "mcp_servers"
MCP_FIELDS = ("command", "args", "env", "startup_timeout_s", "call_timeout_s")
DEFAULT_STARTUP_TIMEOUT_S = 15.0
DEFAULT_CALL_TIMEOUT_S = 60.0
MAX_STARTUP_TIMEOUT_S = 300
MAX_CALL_TIMEOUT_S = 3600

_NAME = re.compile(r"[A-Za-z0-9_-]{1,32}")
_VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_MAX_TEXT_CHARS = 500
_NAME_SHOWN_CHARS = 32
_MISSING = "falta el campo obligatorio."
_NOT_A_TABLE = "debe ser una tabla."
_BAD_NAME = "el nombre debe tener de 1 a 32 caracteres: letras, números, _ y -."
_NOT_A_COMMAND = "debe ser un texto no vacío de una sola línea, de hasta 500 caracteres."
_NOT_ARGUMENTS = "debe ser una lista de textos de una sola línea, de hasta 500 caracteres cada uno."
_NOT_NAMES = "debe ser una lista de nombres de variables de entorno (letras, números y _)."
_NOT_A_TIMEOUT = "debe ser un número mayor que 0 y de hasta {maximum} segundos."


@dataclass(frozen=True, slots=True)
class McpServerConfig:
    """One MCP server of the configuration.

    Attributes:
        name: Name of the table (``[mcp_servers.<name>]``).
        command: Executable to start (resolved by the operating system).
        args: Arguments of the command.
        env: Names of the variables of the parent environment the server receives; it receives
            no other variable except the safe base the SDK adds.
        startup_timeout_s: Longest wait for the capability negotiation.
        call_timeout_s: Longest wait for one tool call.
    """

    name: str
    command: str
    args: tuple[str, ...] = ()
    env: tuple[str, ...] = ()
    startup_timeout_s: float = DEFAULT_STARTUP_TIMEOUT_S
    call_timeout_s: float = DEFAULT_CALL_TIMEOUT_S


def _one_line(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= _MAX_TEXT_CHARS
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
    )


def _shown(name: str) -> str:
    """The name of a server as it is shown in a problem: printable and not too long."""
    text = "".join(char if char.isprintable() else "?" for char in name)
    return text if len(text) <= _NAME_SHOWN_CHARS else text[:_NAME_SHOWN_CHARS] + "…"


def _timeout(value: object, maximum: int) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if 0 < value <= maximum else None


def check_mcp_servers(
    table: Mapping[str, Any],
) -> tuple[tuple[McpServerConfig, ...], list[tuple[str, str]]]:
    """Validate the table ``mcp_servers`` (server name -> table of fields).

    Returns:
        The servers in the order of the file, and the problems as ``(field, message)``; when
        there is a problem the servers are not to be used.
    """
    servers: list[McpServerConfig] = []
    problems: list[tuple[str, str]] = []
    for name, value in table.items():
        prefix = f"{MCP_TABLE}.{_shown(name)}"
        if not _NAME.fullmatch(name):
            problems.append((prefix, _BAD_NAME))
            continue
        if not isinstance(value, dict):
            problems.append((prefix, _NOT_A_TABLE))
            continue
        before = len(problems)
        server = _check_server(name, value, prefix, problems)
        if len(problems) == before:
            servers.append(server)
    return tuple(servers), problems


def _check_server(
    name: str, fields: Mapping[str, Any], prefix: str, problems: list[tuple[str, str]]
) -> McpServerConfig:
    command = ""
    if "command" not in fields:
        problems.append((f"{prefix}.command", _MISSING))
    elif _one_line(fields["command"]):
        command = fields["command"]
    else:
        problems.append((f"{prefix}.command", _NOT_A_COMMAND))
    args: tuple[str, ...] = ()
    if "args" in fields:
        value = fields["args"]
        if isinstance(value, list) and all(_one_line_or_empty(item) for item in value):
            args = tuple(value)
        else:
            problems.append((f"{prefix}.args", _NOT_ARGUMENTS))
    env: tuple[str, ...] = ()
    if "env" in fields:
        value = fields["env"]
        if isinstance(value, list) and all(
            isinstance(item, str) and _VARIABLE.fullmatch(item) for item in value
        ):
            env = tuple(dict.fromkeys(value))
        else:
            problems.append((f"{prefix}.env", _NOT_NAMES))
    startup = DEFAULT_STARTUP_TIMEOUT_S
    if "startup_timeout_s" in fields:
        checked = _timeout(fields["startup_timeout_s"], MAX_STARTUP_TIMEOUT_S)
        if checked is None:
            message = _NOT_A_TIMEOUT.format(maximum=MAX_STARTUP_TIMEOUT_S)
            problems.append((f"{prefix}.startup_timeout_s", message))
        else:
            startup = checked
    call = DEFAULT_CALL_TIMEOUT_S
    if "call_timeout_s" in fields:
        checked = _timeout(fields["call_timeout_s"], MAX_CALL_TIMEOUT_S)
        if checked is None:
            message = _NOT_A_TIMEOUT.format(maximum=MAX_CALL_TIMEOUT_S)
            problems.append((f"{prefix}.call_timeout_s", message))
        else:
            call = checked
    return McpServerConfig(name, command, args, env, startup, call)


def _one_line_or_empty(value: object) -> bool:
    """An argument may be an empty text (``""`` is a legitimate argument) but not multi-line."""
    return isinstance(value, str) and (value == "" or _one_line(value))
