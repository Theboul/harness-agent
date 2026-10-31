"""An MCP tool seen as a native ``Tool`` (HU-08-02).

The server describes each tool with a name, a description and a JSON Schema. Everything it says is
untrusted: the description is capped before it reaches the model, the schema is copied (the server
object is never shared) and the risk is never taken from the server, because MCP has no such field.
The registry validates the final definition: a name or schema that does not fit is rejected there.
"""

from __future__ import annotations

import copy
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any

from harness_agent.core import RiskLevel, Tool, ToolResult

MAX_DESCRIPTION_CHARS = 2000
_KEPT_CONTROLS = "\n\t"
_DROPPED_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co"})
_FAILED = "[mcp_error] La herramienta MCP falló al ejecutarse."

CallTool = Callable[[str, dict[str, Any]], Awaitable[ToolResult]]


class McpTool(Tool):
    """A tool that lives in an MCP server; ``run`` forwards the call to it.

    Args:
        server: Name the server has in the configuration (for the fallback description).
        remote_name: Name of the tool in the server, used for the call.
        description: Text from the server; empty or not text gives a fixed fallback.
        schema: Argument schema from the server; a copy is kept.
        call: The ``call_tool`` of the client that owns the connection.
    """

    def __init__(
        self,
        server: str,
        remote_name: str,
        description: object,
        schema: object,
        call: CallTool,
    ) -> None:
        self._remote_name = remote_name
        self._description = _description(server, remote_name, description)
        self._schema: dict[str, Any] = copy.deepcopy(schema) if isinstance(schema, dict) else {}
        self._call = call

    @property
    def name(self) -> str:
        return self._remote_name

    @property
    def description(self) -> str:
        return self._description

    @property
    def schema(self) -> dict[str, Any]:
        return self._schema

    @property
    def risk(self) -> RiskLevel:
        """Always HIGH: nothing is allowed on the word of a remote server (HU-08-03)."""
        return RiskLevel.HIGH

    async def run(self, args: dict[str, Any]) -> ToolResult:
        """Forward the call; an unexpected failure is a fixed error, never ``str(exc)``."""
        try:
            return await self._call(self._remote_name, args)
        except Exception:
            return ToolResult("", _FAILED, is_error=True)


def _description(server: str, name: str, description: object) -> str:
    if isinstance(description, str):
        cleaned = _clean(description).strip()
        if cleaned:
            return cleaned[:MAX_DESCRIPTION_CHARS]
    return f"MCP tool '{name}' from server '{server}' (no description)."


def _clean(text: str) -> str:
    """Drop control, format, surrogate and private-use characters (newline and tab stay)."""
    return "".join(
        char
        for char in text
        if char in _KEPT_CONTROLS or unicodedata.category(char) not in _DROPPED_CATEGORIES
    )


def translate_tool(server: str, sdk_tool: object, call: CallTool) -> McpTool | None:
    """Build the internal tool for one entry of the server list; ``None`` if it has no text name."""
    name = getattr(sdk_tool, "name", None)
    if not isinstance(name, str):
        return None
    return McpTool(
        server,
        name,
        getattr(sdk_tool, "description", None),
        getattr(sdk_tool, "input_schema", None),
        call,
    )
