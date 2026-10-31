"""``connect_all`` and ``close_all``: a server that fails never stops the others (FR-005)."""

from __future__ import annotations

import asyncio

import pytest

from harness_agent.adapters.mcp import (
    McpConnectError,
    McpDependencyError,
    close_all,
    connect_all,
)
from harness_agent.core import McpClient, Tool, ToolResult


class StubClient(McpClient):
    """A client that records what it is asked and can fail on demand."""

    def __init__(
        self, name: str, *, fail: BaseException | None = None, close_fails: bool = False
    ) -> None:
        self.name = name
        self.fail = fail
        self.close_fails = close_fails
        self.events: list[str] = []

    async def connect(self) -> None:
        self.events.append("connect")
        if self.fail is not None:
            raise self.fail

    async def close(self) -> None:
        self.events.append("close")
        if self.close_fails:
            raise RuntimeError("fallo al cerrar")

    async def list_tools(self) -> list[Tool]:
        return []

    async def call_tool(self, name: str, arguments: dict[str, object]) -> ToolResult:
        return ToolResult("", "")


class TestConnectAll:
    async def test_every_server_is_connected_in_order(self) -> None:
        clients = [StubClient("a"), StubClient("b")]
        warnings: list[str] = []

        await connect_all(clients, warnings.append)

        assert [c.events for c in clients] == [["connect"], ["connect"]]
        assert warnings == []

    async def test_a_server_that_fails_is_reported_and_the_next_one_is_still_connected(
        self,
    ) -> None:
        broken = StubClient("a", fail=McpConnectError("a", "cerro_al_arrancar"))
        healthy = StubClient("b")
        warnings: list[str] = []

        await connect_all([broken, healthy], warnings.append)

        assert healthy.events == ["connect"]
        assert warnings == [str(McpConnectError("a", "cerro_al_arrancar"))]

    async def test_a_missing_library_is_a_warning_too(self) -> None:
        client = StubClient("a", fail=McpDependencyError("a"))
        warnings: list[str] = []

        await connect_all([client], warnings.append)

        assert warnings == [str(McpDependencyError("a"))]

    async def test_cancellation_closes_what_was_opened_and_propagates(self) -> None:
        opened = StubClient("a")
        cancelled = StubClient("b", fail=asyncio.CancelledError())

        with pytest.raises(asyncio.CancelledError):
            await connect_all([opened, cancelled], lambda _: None)

        assert opened.events == ["connect", "close"]
        assert cancelled.events == ["connect", "close"]

    async def test_an_unexpected_error_is_a_fixed_warning_and_the_session_goes_on(self) -> None:
        client = StubClient("a", fail=RuntimeError("inesperado"))
        warnings: list[str] = []

        await connect_all([client], warnings.append)

        assert len(warnings) == 1 and "inesperado" not in warnings[0]


class TestCloseAll:
    async def test_every_client_is_closed_even_if_one_fails(self) -> None:
        first = StubClient("a", close_fails=True)
        second = StubClient("b")

        await close_all([first, second])

        assert first.events == ["close"]
        assert second.events == ["close"]

    async def test_nothing_to_close_is_fine(self) -> None:
        await close_all([])
