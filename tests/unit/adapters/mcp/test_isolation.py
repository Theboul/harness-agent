"""Isolation of MCP failures (HU-08-04) and the hardening of the tool (HU-08-03).

A server that goes away, hangs or breaks affects only its own tools: calls come back as fixed
error results, the client reports itself as lost, and a failure of one client never stops the
connection, registration or closing of the others.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from harness_agent.adapters.mcp import (
    McpServerSettings,
    McpStdioClient,
    close_all,
    connect_all,
    register_mcp_tools,
)
from harness_agent.adapters.mcp.tool import McpTool
from harness_agent.core import InMemoryToolRegistry, Tool, ToolResult
from tests.unit.adapters.mcp.fake_sdk import FakeSdk, Script, result

SENTINEL = "VALOR-DE-PRUEBA-123"
SETTINGS = McpServerSettings(
    name="demo", command="servidor", call_timeout_s=0.05, close_timeout_s=1
)


async def connected(script: Script, *, grace: float = 0.05) -> tuple[McpStdioClient, FakeSdk]:
    fake = FakeSdk(script)
    client = McpStdioClient(SETTINGS, environ={}, sdk_loader=fake.loader, call_grace_s=grace)
    await client.connect()
    return client, fake


class TestClientLoss:
    async def test_a_call_that_finds_the_server_down_marks_the_client_as_lost(self) -> None:
        client, fake = await connected(Script(call_error=ConnectionError("gone")))

        first = await client.call_tool("add", {})

        assert first.content.startswith("[mcp_server_down]")
        assert client.connected is False
        await client.close()
        assert len(fake.calls) == 1

    async def test_a_lost_client_answers_at_once_without_touching_the_sdk(self) -> None:
        client, fake = await connected(Script(call_error=ConnectionError("gone")))
        await client.call_tool("add", {})

        again = await client.call_tool("add", {"a": SENTINEL})

        assert again.is_error and again.content.startswith("[mcp_server_down]")
        assert SENTINEL not in again.content
        assert len(fake.calls) == 1
        await client.close()

    async def test_closing_a_lost_client_leaves_nothing_behind(self) -> None:
        client, fake = await connected(Script(call_error=ConnectionError("gone")))
        await client.call_tool("add", {})

        await client.close()
        await client.close()

        assert fake.names("exit-stdio") == fake.names("enter-stdio")
        assert client.connected is False

    async def test_a_timeout_does_not_mark_the_client_as_lost(self) -> None:
        client, _ = await connected(Script(call_error=TimeoutError("late")))

        outcome = await client.call_tool("slow", {})

        assert outcome.content.startswith("[mcp_timeout]")
        assert client.connected is True
        await client.close()

    async def test_a_server_that_hangs_ends_the_call_by_the_hard_limit(self) -> None:
        client, _ = await connected(Script(call_hang=True))

        outcome = await asyncio.wait_for(client.call_tool("slow", {}), timeout=5)

        assert outcome.is_error and outcome.content.startswith("[mcp_timeout]")
        assert client.connected is True
        await client.close()

    async def test_a_generic_error_does_not_mark_the_client_as_lost(self) -> None:
        client, _ = await connected(Script(call_error=ValueError(SENTINEL)))

        outcome = await client.call_tool("add", {})

        assert outcome.content.startswith("[mcp_error]") and SENTINEL not in outcome.content
        assert client.connected is True
        await client.close()


class BrokenClient:
    """A client whose own code fails with something unexpected."""

    def __init__(self, name: str, *, connect: bool = False, close: bool = False) -> None:
        self.name = name
        self.connected = True
        self._fail_connect = connect
        self._fail_close = close
        self.closed = False
        self.did_connect = False

    async def connect(self) -> None:
        if self._fail_connect:
            raise RuntimeError(SENTINEL)
        self.did_connect = True

    async def close(self) -> None:
        self.closed = True
        if self._fail_close:
            raise RuntimeError(SENTINEL)

    async def list_tools(self) -> list[Tool]:
        raise RuntimeError(SENTINEL)


class TestConnectionsIsolation:
    async def test_an_unexpected_error_when_connecting_is_a_fixed_warning(self) -> None:
        broken, good = BrokenClient("roto", connect=True), BrokenClient("bueno")
        warnings: list[str] = []

        await connect_all([broken, good], warnings.append)

        assert good.did_connect
        assert len(warnings) == 1 and "roto" in warnings[0] and SENTINEL not in warnings[0]

    async def test_an_unsafe_name_is_never_repeated_in_the_warning(self) -> None:
        broken = BrokenClient(f"mal\n{SENTINEL}", connect=True)
        warnings: list[str] = []

        await connect_all([broken], warnings.append)

        assert len(warnings) == 1 and SENTINEL not in warnings[0]

    async def test_cancellation_while_connecting_closes_every_client(self) -> None:
        class Cancelling(BrokenClient):
            async def connect(self) -> None:
                raise asyncio.CancelledError

        first, second = BrokenClient("a"), Cancelling("b")

        with pytest.raises(asyncio.CancelledError):
            await connect_all([first, second], lambda text: None)

        assert first.closed and second.closed

    async def test_a_client_that_fails_to_close_does_not_stop_the_others(self) -> None:
        broken, good = BrokenClient("roto", close=True), BrokenClient("bueno")

        await close_all([broken, good])

        assert good.closed

    async def test_an_unexpected_error_when_listing_is_a_fixed_warning_and_the_next_registers(
        self,
    ) -> None:
        class Good(BrokenClient):
            async def list_tools(self) -> list[Tool]:
                async def call(name: str, arguments: dict[str, Any]) -> ToolResult:
                    return ToolResult("", "ok")

                return [McpTool("bueno", "ping", "d", {"type": "object"}, call)]

        registry = InMemoryToolRegistry()
        names: set[str] = set()
        warnings: list[str] = []

        count = await register_mcp_tools(
            [BrokenClient("roto"), Good("bueno")], registry, warnings.append, names
        )

        assert count == 1 and names == {"ping"} and registry.get("ping") is not None
        assert len(warnings) == 1 and "roto" in warnings[0] and SENTINEL not in warnings[0]


class TestMcpTool:
    async def test_an_unexpected_exception_of_the_client_is_a_fixed_error(self) -> None:
        async def call(name: str, arguments: dict[str, Any]) -> ToolResult:
            raise RuntimeError(SENTINEL)

        tool = McpTool("demo", "ping", "d", {"type": "object"}, call)

        outcome = await tool.run({})

        assert outcome.is_error and outcome.content.startswith("[mcp_error]")
        assert SENTINEL not in outcome.content

    async def test_cancellation_is_not_swallowed(self) -> None:
        async def call(name: str, arguments: dict[str, Any]) -> ToolResult:
            raise asyncio.CancelledError

        tool = McpTool("demo", "ping", "d", {"type": "object"}, call)

        with pytest.raises(asyncio.CancelledError):
            await tool.run({})

    def test_the_description_loses_control_and_format_characters(self) -> None:
        dirty = "Line one\nline\ttwo\x00\x1b[31m \u202eevil\u200b \ue000 ok"

        async def call(name: str, arguments: dict[str, Any]) -> ToolResult:
            return ToolResult("", "")

        tool = McpTool("demo", "ping", dirty, {"type": "object"}, call)

        assert tool.description == "Line one\nline\ttwo[31m evil  ok"

    def test_a_description_that_is_only_control_characters_gets_the_fallback(self) -> None:
        async def call(name: str, arguments: dict[str, Any]) -> ToolResult:
            return ToolResult("", "")

        tool = McpTool("demo", "ping", "\x00\u200b", {"type": "object"}, call)

        assert "(no description)" in tool.description

    async def test_a_good_result_passes_through_unchanged(self) -> None:
        client, _ = await connected(Script(call_result=result("hola")))
        outcome = await client.call_tool("echo", {})
        assert outcome.content == "hola"
        await client.close()
