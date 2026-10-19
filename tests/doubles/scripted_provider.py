"""Test double: ScriptedProvider, a finite scripted Provider (HU-01-01, T002).

Not an implementation of HU-00-03 (FakeProvider, owned by B): it exists only so the
agentic loop can be tested deterministically with a finite script. When the script is
exhausted it raises ``ScriptExhausted`` and flips ``exhausted`` so the test harness can
turn that into an explicit test failure (FR-028, condition 2 of the PO decision).
"""

from __future__ import annotations

import asyncio

from harness_agent.core.entities import Message
from harness_agent.core.interfaces.provider import (
    Provider,
    ProviderResponse,
    ToolDefinition,
)


class ScriptExhausted(Exception):
    """Raised when the loop asks the provider for more responses than scripted."""


class ScriptedProvider(Provider):
    """Provider that replays a finite script of responses (or raises scripted errors)."""

    def __init__(
        self,
        script: list[ProviderResponse | BaseException],
        *,
        allow_invalid_ids: bool = False,
        block_on_call: int | None = None,
    ) -> None:
        if not allow_invalid_ids:
            self._check_ids(script)
        self._script = list(script)
        self._block_on_call = block_on_call
        self.received: list[list[Message]] = []
        self.received_tools: list[list[ToolDefinition] | None] = []
        self.call_count = 0
        self.exhausted = False
        self.blocked = asyncio.Event()

    @staticmethod
    def _check_ids(script: list[ProviderResponse | BaseException]) -> None:
        seen: set[str] = set()
        for item in script:
            if not isinstance(item, ProviderResponse):
                continue
            for call in item.tool_calls:
                if not call.id or call.id in seen:
                    raise ValueError(
                        f"Scripted tool call id {call.id!r} must be non-empty and unique "
                        "across the whole session (use allow_invalid_ids=True for negative tests)."
                    )
                seen.add(call.id)

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        """Record a copy of the received messages and replay the next scripted item."""
        self.received.append(list(messages))
        self.received_tools.append(None if tools is None else list(tools))
        index = self.call_count
        self.call_count += 1
        if self._block_on_call is not None and index == self._block_on_call:
            self.blocked.set()
            await asyncio.Event().wait()  # waits until the task is cancelled
        if index >= len(self._script):
            self.exhausted = True
            raise ScriptExhausted(f"Script exhausted at provider call {index + 1}.")
        item = self._script[index]
        if isinstance(item, BaseException):
            raise item
        return item
