"""Local MCP demo server for the SPK-04 spike: stdio, deterministic, no credentials, no network.

Run as ``python mcp_demo_server.py``. Each tool exists to exercise one behavior of the client:
the happy path, a failing tool, a slow tool, a crash and an open-ended object argument.
"""

from __future__ import annotations

import os
import time
from typing import Any

from mcp.server.mcpserver import MCPServer

SERVER_NAME = "harness-demo"

server = MCPServer(SERVER_NAME)


@server.tool()
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@server.tool()
def echo(text: str) -> str:
    """Return the given text."""
    return text


@server.tool()
def greet(name: str, title: str | None = None) -> str:
    """Greet someone; the optional title makes the SDK emit an ``anyOf`` schema."""
    return f"Hello, {title + ' ' if title else ''}{name}"


@server.tool()
def fail() -> str:
    """Always raise inside the tool."""
    raise ValueError("demo failure")


@server.tool()
def slow(seconds: float) -> str:
    """Sleep for the given seconds and then answer."""
    time.sleep(seconds)
    return "done"


@server.tool()
def crash() -> str:
    """Terminate the server process without answering."""
    os._exit(3)


@server.tool()
def pid() -> int:
    """Return the process id of the server."""
    return os.getpid()


@server.tool()
def free_form(payload: dict[str, Any]) -> int:
    """Accept an open-ended object and return how many keys it has."""
    return len(payload)


if __name__ == "__main__":
    server.run("stdio")
