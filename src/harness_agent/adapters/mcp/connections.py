"""Connect and close a group of MCP servers without letting one failure stop the others (HU-08-01).

A server that cannot be started is reported through ``warn`` and left without tools; the session
goes on (rule 1 of the story). Each client keeps its own connection, so the isolation of failures
between servers (HU-08-04) and several servers (HU-08-05) add to this without rebuilding it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Protocol

from harness_agent.adapters.mcp.errors import McpError


class Connectable(Protocol):
    """What this module needs from a client: ``McpStdioClient`` has both methods."""

    async def connect(self) -> None: ...

    async def close(self) -> None: ...


async def connect_all(clients: Sequence[Connectable], warn: Callable[[str], None]) -> None:
    """Connect each client in order; a failure becomes one warning and the rest are connected.

    If the caller is cancelled, every client is closed (including the ones already connected)
    and the cancellation propagates.
    """
    for client in clients:
        try:
            await client.connect()
        except McpError as error:
            warn(str(error))
        except asyncio.CancelledError:
            await close_all(clients)
            raise


async def close_all(clients: Sequence[Connectable]) -> None:
    """Close every client; one that fails to close does not stop the others."""
    for client in clients:
        try:
            await client.close()
        except Exception:
            continue
