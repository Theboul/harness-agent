"""A scripted double of the MCP SDK for the unit tests of the client (no process, no network).

It has the shape of ``McpSdk`` and records in which asyncio task each context was entered and
left, because the real SDK requires both to happen in the same task (SPK-04, section 5.3).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from harness_agent.adapters.mcp.sdk import McpSdk


class FakeText:
    """Stands for ``mcp.types.TextContent``."""

    def __init__(self, text: str) -> None:
        self.text = text


class FakeImage:
    """A content block that is not text."""


@dataclass
class Script:
    """What the fake server does; every field is a failure to provoke."""

    spawn_error: BaseException | None = None
    initialize_error: BaseException | None = None
    initialize_hang: bool = False
    exit_error: BaseException | None = None
    exit_hang: bool = False
    call_result: Any = None
    call_error: BaseException | None = None
    call_hang: bool = False


@dataclass
class FakeSdk:
    """Builds an ``McpSdk`` whose pieces follow ``script`` and write to ``events``."""

    script: Script = field(default_factory=Script)
    events: list[tuple[str, str]] = field(default_factory=list)
    calls: list[tuple[str, dict[str, Any] | None, float | None]] = field(default_factory=list)
    launched: list[Any] = field(default_factory=list)
    errlogs: list[Any] = field(default_factory=list)

    def _note(self, event: str) -> None:
        task = asyncio.current_task()
        self.events.append((event, "" if task is None else task.get_name()))

    def names(self, event: str) -> list[str]:
        return [task for name, task in self.events if name == event]

    def loader(self, server: str = "") -> McpSdk:
        """An ``sdk_loader`` for the client under test."""
        return self.build()

    def build(self) -> McpSdk:
        sdk = self

        @asynccontextmanager
        async def stdio_client(params: Any, errlog: Any = None) -> AsyncIterator[tuple[Any, Any]]:
            sdk._note("enter-stdio")
            sdk.launched.append(params)
            sdk.errlogs.append(errlog)
            if sdk.script.spawn_error is not None:
                raise sdk.script.spawn_error
            try:
                yield object(), object()
            finally:
                sdk._note("exit-stdio")

        class FakeSession:
            def __init__(self, read: Any, write: Any, read_timeout_seconds: float | None = None):
                self.read_timeout_seconds = read_timeout_seconds

            async def __aenter__(self) -> FakeSession:
                sdk._note("enter-session")
                return self

            async def __aexit__(self, *exc: object) -> None:
                sdk._note("exit-session")
                if sdk.script.exit_hang:
                    await asyncio.Event().wait()
                if sdk.script.exit_error is not None:
                    raise sdk.script.exit_error

            async def initialize(self) -> Any:
                sdk._note("initialize")
                if sdk.script.initialize_hang:
                    await asyncio.Event().wait()
                if sdk.script.initialize_error is not None:
                    raise sdk.script.initialize_error
                return SimpleNamespace(
                    server_info=SimpleNamespace(name="fake-server"),
                    capabilities=SimpleNamespace(tools=object()),
                )

            async def call_tool(
                self,
                name: str,
                arguments: dict[str, Any] | None = None,
                read_timeout_seconds: float | None = None,
            ) -> Any:
                sdk.calls.append((name, arguments, read_timeout_seconds))
                if sdk.script.call_hang:
                    await asyncio.Event().wait()
                if sdk.script.call_error is not None:
                    raise sdk.script.call_error
                return sdk.script.call_result

        return McpSdk(
            client_session=FakeSession,
            server_parameters=lambda **kwargs: SimpleNamespace(**kwargs),
            stdio_client=stdio_client,
            text_content=FakeText,
        )


def result(*texts: str, is_error: bool = False) -> Any:
    """A ``CallToolResult``-like object with text blocks."""
    return SimpleNamespace(content=[FakeText(text) for text in texts], is_error=is_error)
