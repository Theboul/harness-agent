"""Register the tools of the connected MCP servers in the tool registry (HU-08-02).

A tool the registry rejects (invalid name or schema, or a name already taken) is left out with one
warning that does not repeat anything the server said; the rest of its tools, and the other
servers, are registered. Names are registered as the server gives them: prefixes against
collisions belong to HU-08-05.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, MutableSet, Sequence
from typing import Protocol

from harness_agent.adapters.mcp.errors import McpError
from harness_agent.core import DuplicateToolError, Tool, ToolRegistry, ToolRegistryError

_SAFE_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
_UNSAFE_NAME = "<nombre no válido>"
_OMITTED = "El servidor MCP '{server}' ofrece la herramienta '{tool}', pero se omitió: {reason}."
_INVALID = "su nombre o su esquema no son válidos para el arnés"
_DUPLICATE = "ya existe otra herramienta con ese nombre"
_UNEXPECTED = (
    "No se pudieron leer las herramientas del servidor MCP{name}: falló de forma inesperada."
)


class ToolSource(Protocol):
    """What this module needs from a client: ``McpStdioClient`` has all of it."""

    @property
    def name(self) -> str: ...

    @property
    def connected(self) -> bool: ...

    async def list_tools(self) -> list[Tool]: ...


async def register_mcp_tools(
    clients: Sequence[ToolSource],
    registry: ToolRegistry,
    warn: Callable[[str], None],
    names: MutableSet[str] | None = None,
) -> int:
    """Discover the tools of every connected client and register them; return how many were.

    A client that is not connected is skipped (its connection failure was already reported). One
    whose list cannot be read, for a known or an unexpected reason, gives one warning and no
    tools (HU-08-04). Cancellation propagates. When ``names`` is given, the name of every
    registered tool is added to it (the composition uses it for the ceiling of HU-08-03).
    """
    registered = 0
    for client in clients:
        if not client.connected:
            continue
        try:
            tools = await client.list_tools()
        except McpError as error:
            warn(str(error))
            continue
        except asyncio.CancelledError:
            raise
        except Exception:
            label = f" '{client.name}'" if _SAFE_NAME.fullmatch(client.name) else ""
            warn(_UNEXPECTED.format(name=label))
            continue
        for tool in tools:
            try:
                registry.register(tool)
            except ToolRegistryError as error:
                reason = _DUPLICATE if isinstance(error, DuplicateToolError) else _INVALID
                warn(_OMITTED.format(server=client.name, tool=_safe_name(tool.name), reason=reason))
            else:
                registered += 1
                if names is not None:
                    names.add(tool.name)
    return registered


def _safe_name(name: object) -> str:
    return name if isinstance(name, str) and _SAFE_NAME.fullmatch(name) else _UNSAFE_NAME
