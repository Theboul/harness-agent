"""``call_tool`` and ``list_tools`` of ``McpStdioClient`` (HU-08-01 / FR-010)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from harness_agent.adapters.mcp import McpServerSettings
from harness_agent.adapters.mcp.client import McpStdioClient
from tests.unit.adapters.mcp.fake_sdk import FakeImage, FakeSdk, FakeText, Script, result

SENTINEL = "VALOR-DE-PRUEBA-123"
SETTINGS = McpServerSettings(name="demo", command="servidor", call_timeout_s=7, close_timeout_s=1)


class FakeMcpError(Exception):
    """Stands for ``mcp.MCPError``."""


async def connected(script: Script) -> tuple[McpStdioClient, FakeSdk]:
    fake = FakeSdk(script)
    client = McpStdioClient(SETTINGS, environ={}, sdk_loader=fake.loader)
    await client.connect()
    return client, fake


class TestSuccess:
    async def test_the_text_blocks_are_joined_and_the_others_ignored(self) -> None:
        script = Script(call_result=result("uno", "dos"))
        script.call_result.content.insert(1, FakeImage())
        client, _ = await connected(script)

        outcome = await client.call_tool("echo", {"text": "hola"})

        assert outcome.content == "uno\ndos"
        assert outcome.is_error is False
        await client.close()

    async def test_the_arguments_and_the_call_timeout_reach_the_sdk(self) -> None:
        client, fake = await connected(Script(call_result=result("ok")))
        arguments = {"a": 1}

        await client.call_tool("add", arguments)

        assert fake.calls == [("add", {"a": 1}, 7)]
        assert fake.calls[0][1] is not arguments
        await client.close()

    async def test_a_server_without_tools_lists_none(self) -> None:
        client, _ = await connected(
            Script(pages={None: SimpleNamespace(tools=[], next_cursor=None)})
        )

        assert await client.list_tools() == []
        await client.close()


class TestErrors:
    async def test_a_result_marked_as_error_never_shows_what_the_server_said(self) -> None:
        text = f"1 validation error input_value={SENTINEL}"
        client, _ = await connected(Script(call_result=result(text, is_error=True)))

        outcome = await client.call_tool("add", {"a": SENTINEL})

        assert outcome.is_error is True
        assert outcome.content.startswith("[mcp_error]")
        assert SENTINEL not in outcome.content
        await client.close()

    async def test_a_result_without_content_is_an_error(self) -> None:
        client, _ = await connected(Script(call_result=SimpleNamespace()))

        outcome = await client.call_tool("add", {})

        assert outcome.is_error is True
        assert outcome.content.startswith("[mcp_error]")
        await client.close()

    @pytest.mark.parametrize(
        ("error", "mark"),
        [
            (FakeMcpError("Request 'tools/call' timed out"), "[mcp_timeout]"),
            (TimeoutError("late"), "[mcp_timeout]"),
            (FakeMcpError("Connection closed"), "[mcp_server_down]"),
            (ExceptionGroup("g", [ConnectionError("x")]), "[mcp_server_down]"),
            (ValueError(SENTINEL), "[mcp_error]"),
        ],
    )
    async def test_an_exception_is_a_fixed_error_result(self, error: Exception, mark: str) -> None:
        client, _ = await connected(Script(call_error=error))

        outcome = await client.call_tool("add", {"a": SENTINEL})

        assert outcome.is_error is True
        assert outcome.content.startswith(mark)
        assert SENTINEL not in outcome.content
        await client.close()

    async def test_a_call_before_connecting_or_after_closing_is_an_error_result(self) -> None:
        fake = FakeSdk(Script(call_result=result("ok")))
        client = McpStdioClient(SETTINGS, environ={}, sdk_loader=fake.loader)

        before = await client.call_tool("add", {})
        await client.connect()
        await client.close()
        after = await client.call_tool("add", {})

        assert before.is_error and before.content.startswith("[mcp_not_connected]")
        assert after.is_error and after.content.startswith("[mcp_not_connected]")
        assert fake.calls == []

    async def test_cancelling_a_call_propagates_the_cancellation(self) -> None:
        client, fake = await connected(Script(call_hang=True))
        calling = asyncio.create_task(client.call_tool("slow", {}))
        for _ in range(50):
            if fake.calls:
                break
            await asyncio.sleep(0.01)

        calling.cancel()
        with pytest.raises(asyncio.CancelledError):
            await calling

        assert client.connected
        await client.close()

    def test_the_double_text_class_is_the_one_the_client_checks(self) -> None:
        assert FakeText("x").text == "x"
