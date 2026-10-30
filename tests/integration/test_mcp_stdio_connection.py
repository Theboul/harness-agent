"""The MCP client against real servers over stdio, with no network and no key (HU-08-01).

Covers AC-01 (start, negotiate, connected), the clean close (no orphan process, also on
cancellation and when the close comes from another task), the isolation of the environment and of
the stderr, and the failures that must not stop the harness from starting. Waits poll with a
ceiling instead of sleeping a fixed time.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from harness_agent.adapters.mcp import (  # noqa: E402
    McpConnectError,
    McpServerSettings,
    McpStdioClient,
)
from tests.integration.mcp_env_probe_server import STARTED_MARK  # noqa: E402
from tests.spikes.mcp_probe import DEMO_SERVER_PATH, process_alive  # noqa: E402

PROBE_SERVER = Path(__file__).with_name("mcp_env_probe_server.py")
SENTINEL = "VALOR-DE-PRUEBA-123"
CEILING_S = 20.0


async def wait_until(condition: Callable[[], bool], *, ceiling: float = CEILING_S) -> bool:
    """Poll ``condition`` every 50 ms until it holds or ``ceiling`` seconds pass."""
    deadline = time.monotonic() + ceiling
    while time.monotonic() < deadline:
        if condition():
            return True
        await asyncio.sleep(0.05)
    return condition()


def demo(**options: object) -> McpServerSettings:
    return McpServerSettings(
        name="demo",
        command=sys.executable,
        args=(str(DEMO_SERVER_PATH),),
        startup_timeout_s=30,
        call_timeout_s=30,
        **options,  # type: ignore[arg-type]
    )


def probe(*, env_names: tuple[str, ...] = (), startup: float = 30) -> McpServerSettings:
    return McpServerSettings(
        name="probe",
        command=sys.executable,
        args=(str(PROBE_SERVER),),
        env_names=env_names,
        startup_timeout_s=startup,
        call_timeout_s=30,
    )


async def server_pid(client: McpStdioClient) -> int:
    outcome = await client.call_tool("pid", {})
    assert not outcome.is_error, outcome.content
    return int(outcome.content)


class TestConnection:
    """AC-01: a configured server starts, negotiates its capabilities and stays connected."""

    async def test_the_client_starts_the_server_negotiates_and_is_connected(self) -> None:
        client = McpStdioClient(demo(), environ=dict(os.environ))

        await client.connect()

        try:
            assert client.connected
            assert client.server_name == "harness-demo"
            assert client.has_tools is True
            outcome = await client.call_tool("add", {"a": 2, "b": 3})
            assert (outcome.is_error, outcome.content) == (False, "5")
        finally:
            await client.close()

    async def test_the_server_process_is_gone_after_close(self) -> None:
        client = McpStdioClient(demo(), environ=dict(os.environ))
        await client.connect()
        pid = await server_pid(client)
        assert process_alive(pid)

        await client.close()

        assert await wait_until(lambda: not process_alive(pid))

    async def test_it_can_be_closed_from_another_task_than_the_one_that_connected(self) -> None:
        client = McpStdioClient(demo(), environ=dict(os.environ))
        connecting = asyncio.create_task(client.connect(), name="conecta")
        await connecting
        pid = await server_pid(client)

        # With the real SDK, leaving its contexts from another task took 98.8 s and raised
        # (SPK-04, 5.3): the owner task is what makes this quick and clean.
        started = time.monotonic()
        await asyncio.wait_for(asyncio.create_task(client.close(), name="cierra"), timeout=15)

        assert time.monotonic() - started < 15
        assert await wait_until(lambda: not process_alive(pid))

    async def test_cancelling_the_task_that_called_connect_leaves_no_server_behind(
        self, tmp_path: Path
    ) -> None:
        pid_file = tmp_path / "server.pid"
        environ = {**os.environ, "PROBE_PID_FILE": str(pid_file), "PROBE_STARTUP_DELAY": "30"}
        client = McpStdioClient(
            probe(env_names=("PROBE_PID_FILE", "PROBE_STARTUP_DELAY")), environ=environ
        )
        connecting = asyncio.create_task(client.connect())
        assert await wait_until(lambda: pid_file.exists() and pid_file.read_text("utf-8") != "")
        pid = int(pid_file.read_text("utf-8"))

        connecting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await connecting

        assert not client.connected
        assert await wait_until(lambda: not process_alive(pid))

    async def test_cancelling_a_task_that_holds_a_connected_client_does_not_strand_the_server(
        self,
    ) -> None:
        client = McpStdioClient(demo(), environ=dict(os.environ))

        async def use() -> None:
            await client.connect()
            await asyncio.Event().wait()

        user = asyncio.create_task(use())
        assert await wait_until(lambda: client.connected)
        pid = await server_pid(client)

        user.cancel()
        with pytest.raises(asyncio.CancelledError):
            await user
        await client.close()

        assert await wait_until(lambda: not process_alive(pid))


class TestIsolation:
    """The server sees only what the configuration names and never writes to the terminal."""

    async def test_the_api_keys_of_the_parent_do_not_reach_the_server(self) -> None:
        environ = {
            **os.environ,
            "ANTHROPIC_API_KEY": SENTINEL,
            "OPENAI_API_KEY": SENTINEL,
            "PROBE_FLAG": "1",
        }
        client = McpStdioClient(probe(env_names=("PROBE_FLAG",)), environ=environ)
        await client.connect()

        try:
            outcome = await client.call_tool("env_names", {})
        finally:
            await client.close()

        names = outcome.content.split(",")
        assert "PROBE_FLAG" in names
        assert "ANTHROPIC_API_KEY" not in names
        assert "OPENAI_API_KEY" not in names

    async def test_the_stderr_of_the_server_goes_to_the_log_file_and_not_to_the_terminal(
        self, tmp_path: Path, capfd: pytest.CaptureFixture[str]
    ) -> None:
        log = tmp_path / "mcp-probe.log"
        client = McpStdioClient(probe(), environ=dict(os.environ), log_path=log)

        await client.connect()
        await client.close()

        captured = capfd.readouterr()
        assert STARTED_MARK not in captured.err
        assert STARTED_MARK not in captured.out
        assert STARTED_MARK in log.read_text("utf-8")


class TestFailures:
    """A server that cannot start is a domain error, quickly, and leaves no process."""

    async def test_a_command_that_does_not_exist(self) -> None:
        settings = McpServerSettings(
            name="roto", command="no-such-command-hu-08-01", args=(SENTINEL,)
        )
        client = McpStdioClient(settings, environ=dict(os.environ))

        with pytest.raises(McpConnectError) as raised:
            await client.connect()

        assert raised.value.code == "no_se_pudo_iniciar"
        assert SENTINEL not in str(raised.value)

    async def test_a_server_that_exits_as_soon_as_it_starts(self) -> None:
        settings = McpServerSettings(
            name="roto", command=sys.executable, args=("-c", "raise SystemExit(1)")
        )
        client = McpStdioClient(settings, environ=dict(os.environ))

        with pytest.raises(McpConnectError) as raised:
            await client.connect()

        assert raised.value.code == "cerro_al_arrancar"

    async def test_a_server_that_never_answers_the_negotiation(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "silent.pid"
        code = (
            f"import os, time; open({str(pid_file)!r}, 'w').write(str(os.getpid())); time.sleep(60)"
        )
        settings = McpServerSettings(
            name="mudo", command=sys.executable, args=("-c", code), startup_timeout_s=1
        )
        client = McpStdioClient(settings, environ=dict(os.environ))
        started = time.monotonic()

        with pytest.raises(McpConnectError) as raised:
            await client.connect()

        assert raised.value.code == "sin_respuesta"
        assert time.monotonic() - started < 20
        pid = int(pid_file.read_text("utf-8"))
        assert await wait_until(lambda: not process_alive(pid))

    async def test_a_server_that_dies_in_the_middle_of_a_call(self) -> None:
        client = McpStdioClient(demo(), environ=dict(os.environ))
        await client.connect()
        pid = await server_pid(client)

        outcome = await client.call_tool("crash", {})
        await client.close()

        assert outcome.is_error
        assert outcome.content.startswith("[mcp_")
        assert await wait_until(lambda: not process_alive(pid))

    async def test_a_tool_that_fails_and_one_that_is_called_with_bad_arguments(self) -> None:
        client = McpStdioClient(demo(), environ=dict(os.environ))
        await client.connect()
        try:
            failing = await client.call_tool("fail", {})
            invalid = await client.call_tool("add", {"a": SENTINEL, "b": 1})
            unknown = await client.call_tool("no-such-tool", {})
        finally:
            await client.close()

        for outcome in (failing, invalid, unknown):
            assert outcome.is_error
            assert outcome.content.startswith("[mcp_error]")
            assert SENTINEL not in outcome.content
