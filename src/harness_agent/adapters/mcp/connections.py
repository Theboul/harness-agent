"""Connect and close a group of MCP servers without letting one failure stop the others (HU-08-01).

A server that cannot be started is reported through ``warn`` and left without tools; the session
goes on (rule 1 of the story). Each client keeps its own connection, so the isolation of failures
between servers (HU-08-04) and several servers (HU-08-05) add to this without rebuilding it.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Sequence
from typing import Protocol

from harness_agent.adapters.mcp.errors import McpError

_SAFE_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
_UNEXPECTED = "El servidor MCP{name} falló de forma inesperada al conectar y se omitió."


def _label(client: object) -> str:
    name = getattr(client, "name", None)
    return f" '{name}'" if isinstance(name, str) and _SAFE_NAME.fullmatch(name) else ""


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
        except Exception:
            warn(_UNEXPECTED.format(name=_label(client)))  # nothing the server said is repeated


async def close_all(clients: Sequence[Connectable]) -> None:
    """Close every client; one that fails to close does not stop the others."""
    for client in clients:
        try:
            await client.close()
        except Exception:
            continue
