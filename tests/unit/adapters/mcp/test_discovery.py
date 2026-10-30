"""Discovery, translation and registration of MCP tools (HU-08-02)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from harness_agent.adapters.mcp import (
    McpListError,
    McpServerSettings,
    McpStdioClient,
    register_mcp_tools,
)
from harness_agent.adapters.mcp.tool import MAX_DESCRIPTION_CHARS, McpTool, translate_tool
from harness_agent.core import InMemoryToolRegistry, RiskLevel, Tool, ToolResult
from tests.unit.adapters.mcp.fake_sdk import FakeSdk, Script, listed, result, sdk_tool

SENTINEL = "VALOR-DE-PRUEBA-123"
SETTINGS = McpServerSettings(name="demo", command="servidor", call_timeout_s=0.2, close_timeout_s=1)


async def connected(script: Script) -> tuple[McpStdioClient, FakeSdk]:
    fake = FakeSdk(script)
    client = McpStdioClient(SETTINGS, environ={}, sdk_loader=fake.loader)
    await client.connect()
    return client, fake


async def no_call(name: str, arguments: dict[str, Any]) -> ToolResult:
    return ToolResult("", f"{name}:{arguments}")


class TestTranslation:
    def test_name_description_and_schema_are_kept_and_risk_is_high(self) -> None:
        entry = sdk_tool("add", "Suma", {"type": "object", "properties": {}})

        tool = translate_tool("demo", entry, no_call)

        assert tool is not None
        assert (tool.name, tool.description) == ("add", "Suma")
        assert tool.schema == {"type": "object", "properties": {}}
        assert tool.risk is RiskLevel.HIGH

    def test_the_schema_is_a_copy(self) -> None:
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        tool = translate_tool("demo", sdk_tool("t", schema=schema), no_call)

        assert tool is not None
        schema["properties"]["x"]["type"] = "integer"  # type: ignore[index]
        assert tool.schema["properties"]["x"]["type"] == "string"

    @pytest.mark.parametrize("description", [None, "", "   ", 42])
    def test_a_missing_description_gets_a_fixed_text(self, description: object) -> None:
        tool = translate_tool("demo", sdk_tool("t", description), no_call)

        assert tool is not None
        assert tool.description == "MCP tool 't' from server 'demo' (no description)."

    def test_a_long_description_is_capped(self) -> None:
        tool = translate_tool("demo", sdk_tool("t", "x" * 10_000), no_call)

        assert tool is not None
        assert len(tool.description) == MAX_DESCRIPTION_CHARS

    def test_an_entry_without_a_text_name_is_skipped(self) -> None:
        assert translate_tool("demo", sdk_tool(None), no_call) is None
        assert translate_tool("demo", sdk_tool(7), no_call) is None

    def test_a_schema_that_is_not_a_mapping_becomes_an_empty_one(self) -> None:
        tool = McpTool("demo", "t", "d", ["no"], no_call)

        assert tool.schema == {}

    async def test_run_calls_the_server_with_the_remote_name(self) -> None:
        tool = translate_tool("demo", sdk_tool("add"), no_call)
        assert tool is not None

        outcome = await tool.run({"a": 1})

        assert outcome.content == "add:{'a': 1}"


class TestListTools:
    async def test_the_tools_of_the_server_are_returned_as_tools(self) -> None:
        page = listed(sdk_tool("add"), sdk_tool("echo"))
        client, _ = await connected(Script(pages={None: page}))

        tools = await client.list_tools()

        assert [tool.name for tool in tools] == ["add", "echo"]
        assert all(isinstance(tool, Tool) for tool in tools)
        await client.close()

    async def test_a_listed_tool_calls_through_the_client(self) -> None:
        client, fake = await connected(
            Script(pages={None: listed(sdk_tool("add"))}, call_result=result("3"))
        )
        (tool,) = await client.list_tools()

        outcome = await tool.run({"a": 1})

        assert outcome.content == "3"
        assert fake.calls[0][:2] == ("add", {"a": 1})
        await client.close()

    async def test_pages_are_followed(self) -> None:
        pages = {
            None: listed(sdk_tool("a"), next_cursor="p2"),
            "p2": listed(sdk_tool("b")),
        }
        client, fake = await connected(Script(pages=pages))

        tools = await client.list_tools()

        assert [tool.name for tool in tools] == ["a", "b"]
        assert fake.list_params[0] is None
        assert fake.list_params[1].cursor == "p2"
        await client.close()

    async def test_a_cursor_that_repeats_ends_the_listing(self) -> None:
        pages = {
            None: listed(sdk_tool("a"), next_cursor="c"),
            "c": listed(sdk_tool("b"), next_cursor="c"),
        }
        client, _ = await connected(Script(pages=pages))

        assert [tool.name for tool in await client.list_tools()] == ["a", "b"]
        await client.close()

    async def test_pages_are_bounded(self) -> None:
        pages: dict[str | None, Any] = {None: listed(sdk_tool("t0"), next_cursor="c1")}
        for index in range(1, 100):
            pages[f"c{index}"] = listed(sdk_tool(f"t{index}"), next_cursor=f"c{index + 1}")
        client, _ = await connected(Script(pages=pages))

        assert len(await client.list_tools()) == 20
        await client.close()

    async def test_entries_without_a_name_are_skipped(self) -> None:
        client, _ = await connected(Script(pages={None: listed(sdk_tool(None), sdk_tool("ok"))}))

        assert [tool.name for tool in await client.list_tools()] == ["ok"]
        await client.close()

    async def test_not_connected_gives_no_tools(self) -> None:
        client = McpStdioClient(SETTINGS, environ={}, sdk_loader=FakeSdk().loader)

        assert await client.list_tools() == []

    async def test_a_failure_is_a_fixed_text_without_what_the_server_said(self) -> None:
        client, _ = await connected(Script(list_error=RuntimeError(SENTINEL)))

        with pytest.raises(McpListError) as caught:
            await client.list_tools()

        assert SENTINEL not in str(caught.value)
        assert "'demo'" in str(caught.value)
        await client.close()

    async def test_a_server_that_does_not_answer_gives_the_same_error(self) -> None:
        client, _ = await connected(Script(list_hang=True))

        with pytest.raises(McpListError):
            await client.list_tools()
        await client.close()

    async def test_cancellation_is_not_swallowed(self) -> None:
        client, _ = await connected(Script(list_error=asyncio.CancelledError()))

        with pytest.raises(asyncio.CancelledError):
            await client.list_tools()
        await client.close()

    async def test_the_name_is_the_configured_one(self) -> None:
        client = McpStdioClient(SETTINGS, environ={}, sdk_loader=FakeSdk().loader)

        assert client.name == "demo"


class FakeSource:
    def __init__(
        self,
        name: str,
        tools: list[Tool],
        *,
        connected: bool = True,
        error: BaseException | None = None,
    ) -> None:
        self.name = name
        self.connected = connected
        self._tools = tools
        self._error = error

    async def list_tools(self) -> list[Tool]:
        if self._error is not None:
            raise self._error
        return self._tools


def make(name: str, schema: Any = None) -> Tool:
    tool = translate_tool("demo", sdk_tool(name, schema=schema), no_call)
    assert tool is not None
    return tool


class TestRegistration:
    async def test_the_tools_appear_in_the_registry_with_their_definition(self) -> None:
        registry = InMemoryToolRegistry()
        warnings: list[str] = []

        count = await register_mcp_tools(
            [FakeSource("demo", [make("add")])], registry, warnings.append
        )

        assert count == 1 and warnings == []
        tool = registry.get("add")
        assert tool is not None and tool.description == "desc"
        assert registry.validate_args("add", {"x": "a"}) == {"x": "a"}

    async def test_a_tool_with_a_schema_the_validator_rejects_is_left_out_alone(self) -> None:
        registry = InMemoryToolRegistry()
        warnings: list[str] = []
        bad = make("bad", {"type": "object", "properties": {"a": {"anyOf": [{"type": "string"}]}}})

        count = await register_mcp_tools(
            [FakeSource("demo", [bad, make("good")])], registry, warnings.append
        )

        assert count == 1
        assert registry.get("bad") is None and registry.get("good") is not None
        assert warnings == [
            "El servidor MCP 'demo' ofrece la herramienta 'bad', pero se omitió: "
            "su nombre o su esquema no son válidos para el arnés."
        ]

    async def test_a_name_that_collides_is_left_out(self) -> None:
        registry = InMemoryToolRegistry()
        registry.register(make("add"))
        warnings: list[str] = []

        count = await register_mcp_tools(
            [FakeSource("demo", [make("add")])], registry, warnings.append
        )

        assert count == 0
        assert "ya existe otra herramienta con ese nombre" in warnings[0]

    async def test_a_name_the_registry_rejects_is_never_repeated_in_the_warning(self) -> None:
        registry = InMemoryToolRegistry()
        warnings: list[str] = []
        name = f"mal.nombre {SENTINEL}"

        await register_mcp_tools([FakeSource("demo", [make(name)])], registry, warnings.append)

        assert registry.list() == []
        assert SENTINEL not in warnings[0] and "<nombre no válido>" in warnings[0]

    async def test_a_list_failure_warns_and_the_next_server_is_registered(self) -> None:
        registry = InMemoryToolRegistry()
        warnings: list[str] = []
        sources = [
            FakeSource("a", [], error=McpListError("a")),
            FakeSource("b", [make("ok")]),
        ]

        count = await register_mcp_tools(sources, registry, warnings.append)

        assert count == 1 and registry.get("ok") is not None
        assert warnings == [str(McpListError("a"))]

    async def test_a_client_that_is_not_connected_is_skipped_without_a_warning(self) -> None:
        registry = InMemoryToolRegistry()
        warnings: list[str] = []

        count = await register_mcp_tools(
            [FakeSource("a", [make("x")], connected=False)], registry, warnings.append
        )

        assert count == 0 and warnings == [] and registry.list() == []

    async def test_cancellation_propagates(self) -> None:
        with pytest.raises(asyncio.CancelledError):
            await register_mcp_tools(
                [FakeSource("a", [], error=asyncio.CancelledError())],
                InMemoryToolRegistry(),
                lambda text: None,
            )
