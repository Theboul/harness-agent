"""A real MCP server that crashes or hangs costs only its own tools (HU-08-04 / AC-01).

The demo server has ``crash`` (it terminates its process), ``slow``, ``pid`` and ``echo``. The
timeouts are short and every wait is polled with a ceiling: no fixed sleeps.
"""

from __future__ import annotations

import asyncio
import dataclasses
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mcp")

from harness_agent.adapters.mcp import (  # noqa: E402
    McpServerSettings,
    McpStdioClient,
    close_all,
    connect_all,
    register_mcp_tools,
)
from harness_agent.bootstrap import Composition  # noqa: E402
from harness_agent.config import McpServerConfig  # noqa: E402
from harness_agent.core import (  # noqa: E402
    ApprovalAction,
    ProviderResponse,
    Role,
    ToolCall,
)
from tests.doubles import DummyApprover, FakeProvider  # noqa: E402
from tests.integration.test_mcp_stdio_connection import wait_until  # noqa: E402
from tests.spikes.mcp_probe import DEMO_SERVER_PATH, process_alive  # noqa: E402
from tests.unit.bootstrap_support import build, make_config  # noqa: E402


def demo(name: str, **options: Any) -> McpServerSettings:
    return McpServerSettings(
        name=name,
        command=sys.executable,
        args=(str(DEMO_SERVER_PATH),),
        startup_timeout_s=30,
        close_timeout_s=10,
        **options,
    )


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


async def server_pid(client: McpStdioClient) -> int:
    outcome = await client.call_tool("pid", {})
    return int(outcome.content)


class TestTwoServers:
    async def test_the_crash_of_one_server_leaves_the_other_working(self) -> None:
        first, second = McpStdioClient(demo("a"), environ={}), McpStdioClient(demo("b"), environ={})
        warnings: list[str] = []
        await connect_all([first, second], warnings.append)
        try:
            first_pid, second_pid = await server_pid(first), await server_pid(second)

            crashed = await first.call_tool("crash", {})
            again = await first.call_tool("echo", {"text": "x"})
            other = await second.call_tool("echo", {"text": "still here"})

            assert crashed.is_error and crashed.content.startswith("[mcp_server_down]")
            assert again.is_error and again.content.startswith("[mcp_server_down]")
            assert first.connected is False and second.connected is True
            assert other.content == "still here" and not other.is_error
            assert await wait_until(lambda: not process_alive(first_pid))
            assert process_alive(second_pid)
        finally:
            await close_all([first, second])
        assert await wait_until(lambda: not process_alive(second_pid))
        assert warnings == []

    async def test_a_lost_server_closes_cleanly_and_leaves_no_process(self) -> None:
        client = McpStdioClient(demo("a"), environ={})
        await client.connect()
        pid = await server_pid(client)
        await client.call_tool("crash", {})

        await client.close()
        await client.close()

        assert await wait_until(lambda: not process_alive(pid))

    async def test_a_server_that_hangs_is_cut_off_and_stays_usable(self) -> None:
        client = McpStdioClient(demo("a", call_timeout_s=1), environ={}, call_grace_s=1)
        await client.connect()
        try:
            slow = await asyncio.wait_for(client.call_tool("slow", {"seconds": 4}), timeout=20)

            assert slow.is_error and slow.content.startswith("[mcp_timeout]")
            assert client.connected is True
        finally:
            await client.close()


class TestInTheSession:
    async def test_the_model_gets_an_error_and_the_native_tools_keep_working(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        workspace = tmp_path / "work"
        workspace.mkdir()
        (workspace / "nota.txt").write_text("hola", encoding="utf-8")
        server = McpServerConfig(
            name="demo",
            command=sys.executable,
            args=(str(DEMO_SERVER_PATH),),
            startup_timeout_s=30,
            call_timeout_s=10,
        )
        config = dataclasses.replace(
            make_config(tmp_path, workspace=workspace), mcp_servers=(server,)
        )
        calls = [
            ToolCall("c1", "crash", {}),
            ToolCall("c2", "echo", {"text": "hi"}),
            ToolCall("c3", "leer_archivo", {"path": "nota.txt"}),
        ]
        provider = FakeProvider(
            [ProviderResponse(tool_calls=calls), ProviderResponse(content="finished")]
        )
        composition = build(
            opened, config, provider, approver=DummyApprover(ApprovalAction.APPROVE_ONCE)
        )
        warnings: list[str] = []
        await connect_all(composition.mcp_clients, warnings.append)
        try:
            await register_mcp_tools(
                composition.mcp_clients,
                composition.registry,
                warnings.append,
                composition.mcp_tool_names,
            )

            result = await composition.loop.run_turn(
                session_id=composition.session_id,
                task="go",
                history=list(composition.history_prefix),
            )

            tools = [message for message in result.history if message.role is Role.TOOL]
            assert result.final_response == "finished"
            assert tools[0].content.startswith("[mcp_")
            assert tools[1].content.startswith("[mcp_server_down]")
            assert "hola" in tools[2].content and tools[2].tool_result is not None
            assert tools[2].tool_result.is_error is False
            assert all(message.is_external for message in tools)
            # Only the known omission of ``greet`` (its schema uses ``anyOf``), nothing else.
            assert len(warnings) == 1 and "'greet'" in warnings[0]
        finally:
            await close_all(composition.mcp_clients)
