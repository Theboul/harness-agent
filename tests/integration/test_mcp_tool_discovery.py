"""MCP tools of a real server reach the registry and run through it (HU-08-02 / AC-01).

The demo server has a tool (``greet``) whose schema uses ``anyOf``: the validator of the core
rejects it, so it is the real case of a tool that is left out with a warning.
"""

from __future__ import annotations

import dataclasses
import io
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from harness_agent.adapters.mcp import (  # noqa: E402
    McpServerSettings,
    McpStdioClient,
    register_mcp_tools,
)
from harness_agent.bootstrap import Composition, run_session  # noqa: E402
from harness_agent.config import McpServerConfig  # noqa: E402
from harness_agent.core import InMemoryToolRegistry  # noqa: E402
from tests.spikes.mcp_probe import DEMO_SERVER_PATH  # noqa: E402
from tests.unit.bootstrap_support import build, make_config  # noqa: E402

NATIVE = {"leer_archivo", "escribir_archivo", "listar_archivos", "buscar_texto", "shell"}
REMOTE = {"add", "echo", "fail", "slow", "crash", "pid", "free_form"}


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


async def test_the_tools_of_a_connected_server_run_through_the_registry() -> None:
    settings = McpServerSettings(
        name="demo", command=sys.executable, args=(str(DEMO_SERVER_PATH),), startup_timeout_s=30
    )
    client = McpStdioClient(settings, environ={})
    registry = InMemoryToolRegistry()
    warnings: list[str] = []
    await client.connect()
    try:
        count = await register_mcp_tools([client], registry, warnings.append)

        names = {tool.name for tool in registry.list()}
        assert names == REMOTE and count == len(REMOTE)
        assert len(warnings) == 1 and "'greet'" in warnings[0]
        add = registry.get("add")
        assert add is not None and "Add two integers" in add.description
        arguments = registry.validate_args("add", {"a": 2, "b": 3})
        assert (await add.run(arguments)).content == "5"
    finally:
        await client.close()


async def test_the_session_registers_the_tools_before_the_first_prompt(
    tmp_path: Path, opened: list[Composition]
) -> None:
    server = McpServerConfig(
        name="demo", command=sys.executable, args=(str(DEMO_SERVER_PATH),), startup_timeout_s=30
    )
    config = dataclasses.replace(make_config(tmp_path), mcp_servers=(server,))
    composition = build(opened, config)
    assert {tool.name for tool in composition.registry.list()} == NATIVE
    output = io.StringIO()

    code = await run_session(composition, input_stream=io.StringIO("/salir\n"), output=output)

    assert code == 0
    assert {tool.name for tool in composition.registry.list()} == NATIVE | REMOTE
    assert "'greet'" in output.getvalue()
    assert output.getvalue().count("se omitió") == 1
