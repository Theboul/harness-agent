"""Child process of the abrupt-kill tests (HU-00-05.1, test support, not production code).

It runs the real system (``compose`` + ``run_session`` over a SQLite file) with a local model, and
tells its parent, on one line of standard output, which events are already confirmed on the disk.
The parent kills it from outside (``Popen.kill``: SIGKILL on Linux, ``TerminateProcess`` on
Windows) and a second child of mode ``resume`` reopens the file and resumes the session.

Usage: ``core_kill_child.py <mode> <database> <workspace> [<session-to-resume>]``

Modes:
    block-provider  On the 3rd request the model call never returns (a request in flight).
    block-tool      On the 3rd request the tool never returns (a call without a result).
    busy            After the 6th request it announces the checkpoint and keeps on writing.
    resume          Runs ``/reanudar <session>`` and one more request; prints the outcome.

The console of ``run_session`` goes to an in-memory buffer: standard output carries only the
``CHECKPOINT`` and ``RESULT`` lines.
"""

from __future__ import annotations

import asyncio
import io
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from harness_agent.bootstrap import Composition, compose, run_session
from harness_agent.config import HarnessConfig, Limits, Paths
from harness_agent.core import (
    Message,
    Provider,
    ProviderResponse,
    RiskLevel,
    Role,
    Tool,
    ToolCall,
    ToolDefinition,
    ToolResult,
)

CHECKPOINT = "CHECKPOINT "
RESULT = "RESULT "
BLOCKED_REQUEST = 3
BUSY_REQUEST = 6
LINES = 5_000


def announce(database: Path, session_id: str) -> None:
    """Print the events the file already holds for the session (a fresh connection sees COMMITs)."""
    connection = sqlite3.connect(str(database))
    try:
        rows = connection.execute(
            "SELECT id, type FROM events WHERE session_id = ? ORDER BY seq", (session_id,)
        ).fetchall()
    finally:
        connection.close()
    payload = {"session": session_id, "events": [[event_id, kind] for event_id, kind in rows]}
    print(CHECKPOINT + json.dumps(payload), flush=True)


class Hub:
    """What the provider and the tool share: the mode, the database and the session."""

    def __init__(self, mode: str, database: Path) -> None:
        self.mode = mode
        self.database = database
        self.session_id = ""
        self.requests = 0
        self.announced = False

    def checkpoint(self) -> None:
        if not self.announced:
            self.announced = True
            announce(self.database, self.session_id)


class LocalModel(Provider):
    """Asks for the tool on every request and answers in text once it has the result."""

    def __init__(self, hub: Hub) -> None:
        self._hub = hub

    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        hub = self._hub
        if messages[-1].role is Role.TOOL:
            return ProviderResponse(content=f"hecho {hub.requests}")
        hub.requests += 1
        if hub.mode == "block-provider" and hub.requests == BLOCKED_REQUEST:
            hub.checkpoint()
            await asyncio.Event().wait()
        if hub.mode == "busy" and hub.requests == BUSY_REQUEST:
            hub.checkpoint()
        call = ToolCall(f"c{hub.requests}", "eco", {"path": "."})
        return ProviderResponse(content="", tool_calls=[call])


class Echo(Tool):
    """An instant tool inside the work area (low risk, so the policy lets it through)."""

    def __init__(self, hub: Hub) -> None:
        self._hub = hub

    @property
    def name(self) -> str:
        return "eco"

    @property
    def description(self) -> str:
        return "Answers ok."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        }

    @property
    def risk(self) -> RiskLevel:
        return RiskLevel.LOW

    async def run(self, args: dict[str, Any]) -> ToolResult:
        hub = self._hub
        if hub.mode == "block-tool" and hub.requests == BLOCKED_REQUEST:
            hub.checkpoint()
            await asyncio.Event().wait()
        return ToolResult("", "ok", False)


def build(mode: str, database: Path, workspace: Path) -> tuple[Composition, Hub]:
    config = HarnessConfig(
        model="openai/modelo-de-prueba",
        limits=Limits(max_turns=100_000, max_output_tokens=777),
        paths=Paths(workspace_root=workspace, sessions_db=database),
        source=database.parent / "config.toml",
    )
    hub = Hub(mode, database)
    model = LocalModel(hub)
    composition = compose(config, provider_factory=lambda _config: model, system_name="Linux")
    composition.registry.register(Echo(hub))
    hub.session_id = composition.session_id
    return composition, hub


async def main(argv: list[str]) -> int:
    mode, database, workspace = argv[0], Path(argv[1]), Path(argv[2])
    composition, hub = build(mode, database, workspace)
    try:
        if mode == "resume":
            lines = [f"/reanudar {argv[3]}", "seguimos", "/salir"]
        elif mode == "busy":
            lines = [f"tarea {n}" for n in range(1, LINES + 1)]
        else:
            lines = ["tarea 1", "tarea 2", "tarea 3", "/salir"]
        console = io.StringIO()
        code = await run_session(
            composition,
            input_stream=io.StringIO("".join(f"{line}\n" for line in lines)),
            output=console,
        )
        print(RESULT + json.dumps({"code": code, "output": console.getvalue()}), flush=True)
        return code
    finally:
        composition.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
