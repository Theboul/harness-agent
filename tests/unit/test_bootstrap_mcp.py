"""The composition root builds the MCP clients and connects them in the session (HU-08-01 / T011).

``compose`` only builds the clients (it is synchronous and runs outside the event loop);
``run_session`` connects them before the first prompt, warns about the ones that fail and always
closes them. Here the SDK is blocked, so nothing starts a process; the real servers are in
``tests/integration/test_bootstrap_mcp.py``.
"""

from __future__ import annotations

import dataclasses
import io
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.mcp import McpDependencyError
from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import HarnessConfig, McpServerConfig
from tests.unit.bootstrap_support import SENTINEL, build, make_config

EXIT_TEXT = "Sesión terminada."


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def with_servers(tmp_path: Path, *servers: McpServerConfig) -> HarnessConfig:
    return dataclasses.replace(make_config(tmp_path), mcp_servers=servers)


DEMO = McpServerConfig(name="demo", command="servidor", args=(SENTINEL,), env=("EXTRA",))


class TestCompose:
    def test_without_servers_there_are_no_clients(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path))

        assert composition.mcp_clients == ()

    def test_each_server_gets_a_client_that_is_not_connected_yet(
        self, tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "mcp", None)  # building must not need the SDK

        composition = build(opened, with_servers(tmp_path, DEMO))

        (client,) = composition.mcp_clients
        assert not client.connected
        assert client.server_name is None

    def test_the_stderr_log_of_a_server_is_next_to_the_sessions_database(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, with_servers(tmp_path, DEMO))

        (client,) = composition.mcp_clients
        assert client.log_path == tmp_path / "datos" / "mcp-demo.log"

    def test_the_environment_given_to_compose_is_what_the_servers_can_name(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(
            opened, with_servers(tmp_path, DEMO), environ={"EXTRA": "uno", "OTRA": "dos"}
        )

        (client,) = composition.mcp_clients
        assert client.environment_for_server() == {"EXTRA": "uno"}


class TestRunSession:
    async def test_a_missing_library_is_one_warning_and_the_session_goes_on(
        self, tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "mcp", None)
        composition = build(opened, with_servers(tmp_path, DEMO))
        output = io.StringIO()

        code = await run_session(composition, input_stream=io.StringIO("/salir\n"), output=output)

        text = output.getvalue()
        assert code == 0
        assert text.count(str(McpDependencyError("demo"))) == 1
        assert EXIT_TEXT in text
        assert SENTINEL not in text

    async def test_the_clients_are_closed_even_if_the_session_fails(
        self, tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        composition = build(opened, with_servers(tmp_path, DEMO))
        closed: list[str] = []

        async def failing_cli(*args: object, **kwargs: object) -> int:
            raise RuntimeError("falla la sesión")

        async def record_close(clients: object) -> None:
            closed.append("cerrados")

        monkeypatch.setattr(bootstrap, "run_cli", failing_cli)
        monkeypatch.setattr(bootstrap, "close_all", record_close)

        with pytest.raises(RuntimeError):
            await run_session(composition, input_stream=io.StringIO(""), output=io.StringIO())

        assert closed == ["cerrados"]

    async def test_without_servers_the_session_never_touches_the_sdk(
        self, tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "mcp", None)
        composition = build(opened, make_config(tmp_path))
        output = io.StringIO()

        code = await run_session(composition, input_stream=io.StringIO("/salir\n"), output=output)

        assert code == 0
        assert "MCP" not in output.getvalue()
