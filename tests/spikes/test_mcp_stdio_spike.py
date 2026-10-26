"""SPK-04 spike: can a stdio MCP client talk to a local, credential-free server?

Characterization tests against the real MCP SDK (pinned in ``requirements-dev.txt``) and a
local demo server (``mcp_demo_server.py``) launched with the test interpreter. There is no
network, no key and no third-party server. They record how the SDK behaves so HU-08-01 to
HU-08-04 can be estimated; they do NOT implement the adapter.
Findings: ``docs/decisiones/SPK-04-cliente-mcp-stdio.md``.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any

import pytest

pytest.importorskip("mcp")

from mcp import ClientSession, MCPError  # noqa: E402

from harness_agent.core.tools import check_schema, validate_arguments  # noqa: E402
from tests.spikes.mcp_probe import (  # noqa: E402
    CallOutcome,
    ProbeServer,
    call,
    demo_server,
    handshake,
    leaf_exceptions,
    list_tools,
    open_session,
    process_alive,
)


class TestHandshake:
    """AC-01: a credential-free server starts, negotiates capabilities and lists a tool."""

    async def test_negotiates_capabilities(self) -> None:
        async with open_session(demo_server()) as session:
            result = await handshake(session)

        assert result.server_name == "harness-demo"
        assert result.protocol_version
        assert result.has_tools is True
        assert "tools" in result.capabilities

    async def test_lists_at_least_one_tool_with_schema(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            tools = await list_tools(session)

        by_name = {tool.name: tool for tool in tools}
        assert len(tools) >= 1
        assert {"add", "echo", "fail", "slow", "crash", "pid", "free_form"} <= set(by_name)
        add = by_name["add"]
        assert add.description == "Add two integers."
        assert add.input_schema["type"] == "object"
        assert set(add.input_schema["required"]) == {"a", "b"}


SENTINEL = "VALOR-DE-PRUEBA-123"


class TestCallResults:
    """How results and errors reach the client (feeds HU-08-03)."""

    async def test_valid_call_returns_text_and_structured_content(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            outcome = await call(session, "add", {"a": 2, "b": 3})

        assert outcome == CallOutcome(text="5", is_error=False, structured={"result": 5})

    async def test_tool_failure_is_a_result_not_an_exception(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            outcome = await call(session, "fail", {})

        assert outcome.is_error is True
        assert "demo failure" not in outcome.text  # the SDK hides the original message

    async def test_unknown_tool_is_a_result_not_an_exception(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            outcome = await call(session, "does_not_exist", {})

        assert outcome.is_error is True
        assert "does_not_exist" in outcome.text

    async def test_invalid_arguments_are_a_result_and_echo_the_received_value(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            outcome = await call(session, "add", {"a": SENTINEL})

        assert outcome.is_error is True
        # Finding: the server error text reproduces the received value and links outside.
        # HU-08-03 must not forward it to the model as is.
        assert SENTINEL in outcome.text

    async def test_echo_round_trips_text_unchanged(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            outcome = await call(session, "echo", {"text": SENTINEL})

        assert outcome.text == SENTINEL
        assert outcome.is_error is False


async def _server_pid(session: ClientSession) -> int:
    outcome = await call(session, "pid", {})
    assert outcome.structured is not None
    return int(outcome.structured["result"])


async def _wait_dead(pid: int, limit_s: float = 5.0) -> bool:
    deadline = time.monotonic() + limit_s
    while time.monotonic() < deadline:
        if not process_alive(pid):
            return True
        await asyncio.sleep(0.1)
    return not process_alive(pid)


class TestServerFailures:
    """What the client sees when the server cannot start, dies or does not answer (HU-08-04)."""

    async def test_missing_command_raises_file_not_found_quickly(self) -> None:
        started = time.monotonic()
        with pytest.raises(FileNotFoundError):
            async with open_session(ProbeServer("no-such-command-spk04")) as session:
                await handshake(session)  # pragma: no cover - never reached
        assert time.monotonic() - started < 10

    async def test_server_exiting_at_startup_surfaces_as_connection_closed(self) -> None:
        dying = ProbeServer(sys.executable, ("-c", "import sys; sys.exit(5)"))
        with pytest.raises(BaseException) as caught:
            async with open_session(dying) as session:
                await handshake(session)

        leaves = leaf_exceptions(caught.value)
        assert [type(leaf) for leaf in leaves] == [MCPError]
        assert "Connection closed" in str(leaves[0])
        # Finding: a launch failure of an existing command is an ExceptionGroup, not a plain error.
        assert isinstance(caught.value, BaseExceptionGroup)

    async def test_server_dying_mid_call_surfaces_as_connection_closed(self) -> None:
        pid = 0
        with pytest.raises(BaseException) as caught:
            async with open_session(demo_server()) as session:
                await handshake(session)
                pid = await _server_pid(session)
                await call(session, "crash", {})

        leaves = leaf_exceptions(caught.value)
        assert [type(leaf) for leaf in leaves] == [MCPError]
        assert "Connection closed" in str(leaves[0])
        assert await _wait_dead(pid)

    async def test_per_call_timeout_raises_and_the_session_stays_usable(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            pid = await _server_pid(session)
            with pytest.raises(MCPError, match="timed out"):
                await call(session, "slow", {"seconds": 3}, timeout_s=0.5)
            after = await call(session, "add", {"a": 1, "b": 2})

        assert after.text == "3"
        assert await _wait_dead(pid)

    async def test_silent_server_times_out_during_initialize(self) -> None:
        silent = ProbeServer(sys.executable, ("-c", "import time; time.sleep(30)"))
        with pytest.raises(BaseException) as caught:
            async with open_session(silent, read_timeout_s=1.0) as session:
                await handshake(session)

        leaves = leaf_exceptions(caught.value)
        assert [type(leaf) for leaf in leaves] == [MCPError]
        assert "timed out" in str(leaves[0])

    async def test_normal_exit_leaves_no_child_process(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            pid = await _server_pid(session)
            assert process_alive(pid)

        assert await _wait_dead(pid)


class TestProcessProbe:
    """The orphan checks above are only as good as ``process_alive``."""

    def test_sees_itself_alive_and_an_unused_id_dead(self) -> None:
        assert process_alive(os.getpid()) is True
        assert process_alive(2**22 + 12345) is False


class TestCancellation:
    """Cancelling client work must not hang or leave the server running (D-01)."""

    async def test_cancelling_one_call_leaves_the_session_usable(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            pid = await _server_pid(session)
            running = asyncio.create_task(call(session, "slow", {"seconds": 20}))
            await asyncio.sleep(0.5)
            running.cancel()
            with pytest.raises(asyncio.CancelledError):
                await running
            after = await asyncio.wait_for(call(session, "add", {"a": 1, "b": 2}), 10)

        assert after.text == "3"
        assert await _wait_dead(pid)

    async def test_cancelling_the_task_that_owns_the_session_stops_the_server(self) -> None:
        holder: dict[str, int] = {}

        async def owner() -> None:
            async with open_session(demo_server()) as session:
                await handshake(session)
                holder["pid"] = await _server_pid(session)
                await call(session, "slow", {"seconds": 20})

        task = asyncio.create_task(owner())
        while "pid" not in holder:
            await asyncio.sleep(0.1)
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert time.monotonic() - started < 15
        assert await _wait_dead(holder["pid"])


class TestSchemaCompatibility:
    """Do the schemas a server announces pass the core validator (HU-01-02), HU-08-02's gate?"""

    async def test_plain_tool_schemas_are_accepted(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            tools = await list_tools(session)

        plain = [tool for tool in tools if tool.name != "greet"]
        assert plain
        for tool in plain:
            assert check_schema(tool.input_schema) == [], tool.name

    async def test_open_object_argument_declares_additional_properties(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            tools = {tool.name: tool for tool in await list_tools(session)}

        schema = tools["free_form"].input_schema
        assert schema["properties"]["payload"]["additionalProperties"] is True
        assert validate_arguments(schema, {"payload": {"k": 1}}) == []
        assert [v.path for v in validate_arguments(schema, {"payload": "x"})] == ["payload"]

    async def test_optional_argument_makes_the_sdk_emit_any_of_which_the_core_rejects(self) -> None:
        async with open_session(demo_server()) as session:
            await handshake(session)
            tools = {tool.name: tool for tool in await list_tools(session)}

        problems = check_schema(tools["greet"].input_schema)
        # Finding: a plain ``str | None`` parameter is enough to hit an unsupported keyword.
        assert any("anyOf" in problem for problem in problems)

    @pytest.mark.parametrize(
        ("label", "schema", "keyword"),
        [
            ("refs", {"type": "object", "properties": {"a": {"$ref": "#/$defs/X"}}}, "$ref"),
            (
                "defs",
                {"type": "object", "properties": {}, "$defs": {"X": {"type": "string"}}},
                "$defs",
            ),
            (
                "format",
                {"type": "object", "properties": {"u": {"type": "string", "format": "uri"}}},
                "format",
            ),
            ("no_root_type", {"properties": {"a": {"type": "string"}}}, "type"),
            ("empty", {}, "type"),
        ],
    )
    def test_common_server_schemas_the_core_rejects(
        self, label: str, schema: dict[str, Any], keyword: str
    ) -> None:
        problems = check_schema(schema)

        assert problems, label
        assert any(keyword in problem for problem in problems)

    @pytest.mark.parametrize(
        "schema",
        [
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {},
            },
            {"type": "object", "properties": {"a": {"type": ["string", "null"]}}},
            {"type": "object", "properties": {}, "additionalProperties": False},
        ],
    )
    def test_schema_features_the_core_accepts(self, schema: dict[str, Any]) -> None:
        assert check_schema(schema) == []
