"""Thin MCP client probe for the SPK-04 spike (test support, not production code).

Wraps the SDK's low-level stdio client so the tests read as observations of the SDK, and
flattens its results into frozen records. The real adapter belongs to HU-08-01.
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

DEMO_SERVER_PATH = Path(__file__).with_name("mcp_demo_server.py")


@dataclass(frozen=True)
class ProbeServer:
    """How to launch a stdio server."""

    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] | None = None


@dataclass(frozen=True)
class Handshake:
    """What the initialize exchange negotiated."""

    protocol_version: str
    server_name: str
    has_tools: bool
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class ListedTool:
    """The minimum HU-08-02 needs to build a ``Tool``."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CallOutcome:
    """A flattened ``call_tool`` result."""

    text: str
    is_error: bool
    structured: dict[str, Any] | None = None


def demo_server() -> ProbeServer:
    """The local demo server, launched with the interpreter running the tests."""
    return ProbeServer(command=sys.executable, args=(str(DEMO_SERVER_PATH),))


@asynccontextmanager
async def open_session(
    server: ProbeServer,
    *,
    read_timeout_s: float | None = None,
    errlog: TextIO | None = None,
) -> AsyncIterator[ClientSession]:
    """Start the server over stdio and yield an initialized-ready client session.

    The server's stderr goes to ``errlog`` (a real file) or to the null device, so tracebacks
    from the child do not pollute the test output.
    """
    params = StdioServerParameters(
        command=server.command,
        args=list(server.args),
        env=dict(server.env) if server.env is not None else None,
    )
    if errlog is not None:
        sink: TextIO = errlog
        async with _session(params, sink, read_timeout_s) as session:
            yield session
        return
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        async with _session(params, devnull, read_timeout_s) as session:
            yield session


@asynccontextmanager
async def _session(
    params: StdioServerParameters, errlog: TextIO, read_timeout_s: float | None
) -> AsyncIterator[ClientSession]:
    async with stdio_client(params, errlog=errlog) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=read_timeout_s) as session:
            yield session


async def handshake(session: ClientSession) -> Handshake:
    """Negotiate capabilities and flatten the answer."""
    result = await session.initialize()
    capabilities = tuple(
        key for key, value in result.capabilities.model_dump().items() if value is not None
    )
    return Handshake(
        protocol_version=str(result.protocol_version),
        server_name=result.server_info.name,
        has_tools=result.capabilities.tools is not None,
        capabilities=capabilities,
    )


async def list_tools(session: ClientSession) -> list[ListedTool]:
    """List the server's tools as frozen records."""
    result = await session.list_tools()
    return [
        ListedTool(
            name=tool.name,
            description=tool.description or "",
            input_schema=dict(tool.input_schema),
        )
        for tool in result.tools
    ]


async def call(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any],
    *,
    timeout_s: float | None = None,
) -> CallOutcome:
    """Call a tool and flatten the result; the SDK reports tool errors as ``is_error``."""
    result = await session.call_tool(name, arguments, read_timeout_seconds=timeout_s)
    text = "\n".join(block.text for block in result.content if isinstance(block, TextContent))
    return CallOutcome(
        text=text,
        is_error=bool(result.is_error),
        structured=dict(result.structured_content) if result.structured_content else None,
    )


def process_alive(pid: int) -> bool:
    """Whether a process id is still running (no third-party dependency, Windows and POSIX)."""
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def leaf_exceptions(error: BaseException) -> list[BaseException]:
    """Flatten nested exception groups: the SDK wraps transport failures in task-group groups."""
    if isinstance(error, BaseExceptionGroup):
        return [leaf for inner in error.exceptions for leaf in leaf_exceptions(inner)]
    return [error]
