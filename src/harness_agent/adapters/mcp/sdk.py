"""Lazy loading of the MCP SDK (HU-08-01 / FR-011).

``mcp`` is an optional dependency (the extra ``mcp``): it is imported with ``importlib`` inside a
function, so the harness never loads it when no server is configured and ``core/`` never sees it.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from harness_agent.adapters.mcp.errors import McpDependencyError


@dataclass(frozen=True)
class McpSdk:
    """The few pieces of the SDK the adapter uses; tests inject a double with the same shape."""

    client_session: Any
    server_parameters: Any
    stdio_client: Any
    text_content: Any


def load_sdk(server: str = "") -> McpSdk:
    """Import the SDK now.

    Args:
        server: Name of the server that needs it, for the text of the error.

    Raises:
        McpDependencyError: The library is not installed or does not have the expected pieces.
    """
    try:
        root = importlib.import_module("mcp")
        stdio = importlib.import_module("mcp.client.stdio")
        types = importlib.import_module("mcp.types")
        return McpSdk(
            client_session=root.ClientSession,
            server_parameters=root.StdioServerParameters,
            stdio_client=stdio.stdio_client,
            text_content=types.TextContent,
        )
    except (ImportError, AttributeError):
        raise McpDependencyError(server) from None
