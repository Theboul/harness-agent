"""A failing MCP server never takes the session down (HU-00-05.2 / RNF-8).

Whole-session evidence: ``compose`` plus ``run_session`` over real child Python processes (the demo
server and the probe server), a scripted model and a console input. HU-08-04 proved the pieces
(client and loop); this proves the session survives, mid-session and at startup, with no orphan
processes left. No network, no keys; every wait is polled with a ceiling (no fixed sleeps).
"""

from __future__ import annotations

import dataclasses
import io
import os
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mcp")

from harness_agent.adapters.mcp import McpStdioClient  # noqa: E402
from harness_agent.bootstrap import Composition, run_session  # noqa: E402
from harness_agent.config import HarnessConfig, McpServerConfig  # noqa: E402
from harness_agent.core import (  # noqa: E402
    ApprovalAction,
    ProviderResponse,
    Role,
    ToolCall,
    ToolResult,
)
from tests.doubles import DummyApprover, FakeProvider  # noqa: E402
from tests.integration.test_mcp_stdio_connection import PROBE_SERVER, wait_until  # noqa: E402
from tests.spikes.mcp_probe import DEMO_SERVER_PATH, process_alive  # noqa: E402
from tests.unit.bootstrap_support import build, make_config  # noqa: E402

EXIT_TEXT = "Sesión terminada."
DOWN = "[mcp_server_down]"
INSTANT_S = 2.0  # far below the call timeouts configured here: a lost server must not wait for them


@dataclass(frozen=True)
class Seen:
    """One ``call_tool`` as the client saw it."""

    name: str
    outcome: ToolResult
    elapsed: float


def demo_server(name: str = "demo", *, call_timeout_s: float = 30) -> McpServerConfig:
    return McpServerConfig(
        name=name,
        command=sys.executable,
        args=(str(DEMO_SERVER_PATH),),
        startup_timeout_s=30,
        call_timeout_s=call_timeout_s,
    )


def probe_server(name: str = "probe") -> McpServerConfig:
    return McpServerConfig(
        name=name,
        command=sys.executable,
        args=(str(PROBE_SERVER),),
        env=("PROBE_PID_FILE",),
        startup_timeout_s=30,
    )


def with_servers(config: HarnessConfig, *servers: McpServerConfig) -> HarnessConfig:
    return dataclasses.replace(config, mcp_servers=servers)


def spy(client: McpStdioClient) -> list[Seen]:
    """Record every ``call_tool`` of ``client`` (the tool looks the method up on each call)."""
    seen: list[Seen] = []
    original = client.call_tool

    async def recording(name: str, arguments: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        outcome = await original(name, arguments)
        seen.append(Seen(name, outcome, time.monotonic() - started))
        return outcome

    client.call_tool = recording  # type: ignore[method-assign]
    return seen


def turn(*calls: ToolCall, answer: str) -> list[ProviderResponse]:
    return [ProviderResponse(tool_calls=list(calls)), ProviderResponse(content=answer)]


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    folder = tmp_path / "work"
    folder.mkdir()
    (folder / "nota.txt").write_text("contenido-nativo", encoding="utf-8")
    return folder


async def run(composition: Composition, lines: str) -> tuple[int, str]:
    output = io.StringIO()
    code = await run_session(composition, input_stream=io.StringIO(lines), output=output)
    return code, output.getvalue()


def tool_texts(provider: FakeProvider) -> list[str]:
    """The tool results the model saw in its last request (the whole session history)."""
    return [message.content for message in provider.received[-1] if message.role is Role.TOOL]


class TestAc01ServerMissingAtStartup:
    async def test_ac01_a_missing_server_only_costs_its_own_tools(
        self, tmp_path: Path, workspace: Path, opened: list[Composition]
    ) -> None:
        pid_file = tmp_path / "probe.pid"
        broken = McpServerConfig(name="roto", command="no-such-command-hu-00-05-2")
        provider = FakeProvider(
            turn(
                ToolCall("c1", "env_names", {}),
                ToolCall("c2", "echo", {"text": "from-demo"}),
                ToolCall("c3", "leer_archivo", {"path": "nota.txt"}),
                answer="listo",
            )
        )
        config = with_servers(
            make_config(tmp_path, workspace=workspace), broken, probe_server(), demo_server()
        )
        composition = build(
            opened,
            config,
            provider,
            approver=DummyApprover(ApprovalAction.APPROVE_ONCE),
            environ={**os.environ, "PROBE_PID_FILE": str(pid_file)},
        )
        started = time.monotonic()

        code, text = await run(composition, "hola\n/salir\n")

        results = tool_texts(provider)
        assert code == 0 and EXIT_TEXT in text
        assert text.count("no está disponible") == 1  # one fixed warning for the broken server
        assert "no-such-command" not in text
        assert not results[0].startswith("[") and "PROBE_PID_FILE" in results[0]
        assert results[1] == "from-demo"
        assert "contenido-nativo" in results[2]
        assert time.monotonic() - started < 60
        assert await wait_until(lambda: not process_alive(int(pid_file.read_text("utf-8"))))


class TestAc02ServerLostMidSession:
    async def test_ac02_the_lost_server_answers_at_once_and_the_rest_keeps_working(
        self, tmp_path: Path, workspace: Path, opened: list[Composition]
    ) -> None:
        pid_file = tmp_path / "probe.pid"
        provider = FakeProvider(
            [
                *turn(
                    ToolCall("a1", "pid", {}),
                    ToolCall("a2", "env_names", {}),
                    ToolCall("a3", "crash", {}),
                    answer="r1",
                ),
                *turn(
                    ToolCall("b1", "echo", {"text": "x"}),
                    ToolCall("b2", "env_names", {}),
                    ToolCall("b3", "leer_archivo", {"path": "nota.txt"}),
                    answer="r2",
                ),
            ]
        )
        config = with_servers(
            make_config(tmp_path, workspace=workspace), demo_server(), probe_server()
        )
        composition = build(
            opened,
            config,
            provider,
            approver=DummyApprover(ApprovalAction.APPROVE_ONCE),
            environ={**os.environ, "PROBE_PID_FILE": str(pid_file)},
        )
        demo_client, probe_client = composition.mcp_clients
        demo_calls, probe_calls = spy(demo_client), spy(probe_client)

        code, text = await run(composition, "uno\ndos\n/salir\n")

        assert code == 0 and EXIT_TEXT in text
        assert provider.exhausted is False and provider.call_count == 4  # both requests finished
        by_name = {call.name: call for call in demo_calls}
        assert [call.name for call in demo_calls] == ["pid", "crash", "echo"]
        assert by_name["crash"].outcome.content.startswith(DOWN)
        # The second request reaches the lost server: it answers on the spot, with a fixed text.
        assert by_name["echo"].outcome.is_error and by_name["echo"].outcome.content.startswith(DOWN)
        assert by_name["echo"].elapsed < INSTANT_S
        # The other server and the native tool answer after the loss.
        assert [call.outcome.is_error for call in probe_calls] == [False, False]
        results = tool_texts(provider)
        assert "contenido-nativo" in results[-1]
        # No process outlives the session: the crashed one, nor the healthy one.
        demo_pid = int(by_name["pid"].outcome.content)
        probe_pid = int(pid_file.read_text("utf-8"))
        assert await wait_until(lambda: not process_alive(demo_pid))
        assert await wait_until(lambda: not process_alive(probe_pid))
        assert demo_client.connected is False and probe_client.connected is False


class TestHungServer:
    async def test_a_hung_server_is_cut_by_time_without_blocking_the_others(
        self, tmp_path: Path, workspace: Path, opened: list[Composition]
    ) -> None:
        pid_file = tmp_path / "probe.pid"
        provider = FakeProvider(
            turn(
                ToolCall("h1", "pid", {}),
                ToolCall("h2", "slow", {"seconds": 40}),
                ToolCall("h3", "env_names", {}),
                ToolCall("h4", "leer_archivo", {"path": "nota.txt"}),
                answer="listo",
            )
        )
        config = with_servers(
            make_config(tmp_path, workspace=workspace),
            demo_server(call_timeout_s=1),
            probe_server(),
        )
        composition = build(
            opened,
            config,
            provider,
            approver=DummyApprover(ApprovalAction.APPROVE_ONCE),
            environ={**os.environ, "PROBE_PID_FILE": str(pid_file)},
        )
        demo_client, probe_client = composition.mcp_clients
        demo_calls, probe_calls = spy(demo_client), spy(probe_client)
        started = time.monotonic()

        code, text = await run(composition, "hola\n/salir\n")

        slow = next(call for call in demo_calls if call.name == "slow")
        assert code == 0 and EXIT_TEXT in text
        assert slow.outcome.is_error and slow.outcome.content.startswith("[mcp_timeout]")
        assert slow.elapsed < 20  # the call timeout plus the grace, never the 40 s of the server
        assert time.monotonic() - started < 45
        assert [call.outcome.is_error for call in probe_calls] == [False]
        assert "contenido-nativo" in tool_texts(provider)[-1]
        demo_pid = int(demo_calls[0].outcome.content)
        probe_pid = int(pid_file.read_text("utf-8"))
        assert await wait_until(lambda: not process_alive(demo_pid))
        assert await wait_until(lambda: not process_alive(probe_pid))
