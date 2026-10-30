"""The harness starts with real MCP servers, broken or not, and closes them (HU-08-01 / T011).

AC-01 end to end (``compose`` + ``run_session`` over the demo server), rule 1 (a server that does
not start only costs a warning in Spanish) and the clean close when the session ends.
"""

from __future__ import annotations

import dataclasses
import io
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from harness_agent.adapters.mcp import McpConnectError  # noqa: E402
from harness_agent.bootstrap import Composition, run_session  # noqa: E402
from harness_agent.config import HarnessConfig, McpServerConfig  # noqa: E402
from tests.integration.test_mcp_stdio_connection import PROBE_SERVER, wait_until  # noqa: E402
from tests.spikes.mcp_probe import DEMO_SERVER_PATH, process_alive  # noqa: E402
from tests.unit.bootstrap_support import SENTINEL, build, make_config  # noqa: E402

EXIT_TEXT = "Sesión terminada."


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def with_servers(tmp_path: Path, *servers: McpServerConfig) -> HarnessConfig:
    return dataclasses.replace(make_config(tmp_path), mcp_servers=servers)


async def session(composition: Composition) -> tuple[int, str]:
    output = io.StringIO()
    code = await run_session(composition, input_stream=io.StringIO("/salir\n"), output=output)
    return code, output.getvalue()


class TestHealthyServer:
    async def test_the_session_connects_the_server_and_closes_it_when_it_ends(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        pid_file = tmp_path / "server.pid"
        server = McpServerConfig(
            name="probe",
            command=sys.executable,
            args=(str(PROBE_SERVER),),
            env=("PROBE_PID_FILE",),
            startup_timeout_s=30,
        )
        composition = build(
            opened,
            with_servers(tmp_path, server),
            environ={**os.environ, "PROBE_PID_FILE": str(pid_file)},
        )
        (client,) = composition.mcp_clients

        code, text = await session(composition)

        assert code == 0
        assert text.count(EXIT_TEXT) == 1
        assert "MCP" not in text  # no warning: the server connected
        assert not client.connected  # closed when the session ended
        pid = int(pid_file.read_text("utf-8"))
        assert await wait_until(lambda: not process_alive(pid))

    async def test_the_demo_server_negotiates_through_the_composition(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        server = McpServerConfig(
            name="demo", command=sys.executable, args=(str(DEMO_SERVER_PATH),), startup_timeout_s=30
        )
        composition = build(opened, with_servers(tmp_path, server))
        (client,) = composition.mcp_clients
        states: list[tuple[bool, str | None]] = []
        original = client.close

        async def spying_close() -> None:
            states.append((client.connected, client.server_name))
            await original()

        client.close = spying_close  # type: ignore[method-assign]

        code, _ = await session(composition)

        assert code == 0
        assert states == [(True, "harness-demo")]


class TestBrokenServers:
    @pytest.mark.parametrize(
        ("command", "args", "code"),
        [
            ("no-such-command-hu-08-01", (SENTINEL,), "no_se_pudo_iniciar"),
            (sys.executable, ("-c", "raise SystemExit(1)"), "cerro_al_arrancar"),
        ],
    )
    async def test_the_harness_starts_and_shows_one_warning_in_spanish(
        self,
        tmp_path: Path,
        opened: list[Composition],
        command: str,
        args: tuple[str, ...],
        code: str,
    ) -> None:
        server = McpServerConfig(name="roto", command=command, args=args, startup_timeout_s=30)
        composition = build(opened, with_servers(tmp_path, server))
        started = time.monotonic()

        exit_code, text = await session(composition)

        assert exit_code == 0
        assert text.count(str(McpConnectError("roto", code))) == 1
        assert "Se continúa sin sus herramientas." in text
        assert EXIT_TEXT in text
        assert SENTINEL not in text
        assert time.monotonic() - started < 30

    async def test_a_broken_server_does_not_stop_a_healthy_one(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        broken = McpServerConfig(name="roto", command="no-such-command-hu-08-01")
        healthy = McpServerConfig(
            name="demo", command=sys.executable, args=(str(DEMO_SERVER_PATH),), startup_timeout_s=30
        )
        composition = build(opened, with_servers(tmp_path, broken, healthy))
        _, healthy_client = composition.mcp_clients
        states: list[bool] = []
        original = healthy_client.close

        async def spying_close() -> None:
            states.append(healthy_client.connected)
            await original()

        healthy_client.close = spying_close  # type: ignore[method-assign]

        code, text = await session(composition)

        assert code == 0
        assert states == [True]
        assert text.count("no está disponible") == 1
