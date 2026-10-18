"""Test double: DummyProvider implementing the Provider abstract contract."""

from __future__ import annotations

from harness_agent.core.entities import Message, TokenUsage
from harness_agent.core.interfaces.provider import (
    Provider,
    ProviderResponse,
    ToolDefinition,
)


class DummyProvider(Provider):
    """In-memory test double for the Provider interface."""

    def __init__(
        self,
        canned_response: ProviderResponse | None = None,
    ) -> None:
        self.canned_response = canned_response or ProviderResponse(
            content="Dummy response from model",
            tool_calls=[],
            usage=TokenUsage(input_tokens=10, output_tokens=5),
        )
        self.recorded_calls: list[tuple[list[Message], list[ToolDefinition] | None]] = []

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        """Record the call and return the configured canned response."""
        self.recorded_calls.append((messages, tools))
        return self.canned_response
