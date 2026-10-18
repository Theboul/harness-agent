"""Verification of Provider interchangeability and LSP compliance (AC-02 / Sp1-41).

Demonstrates that a consumer component interacting strictly with the abstract Provider port
can swap provider implementations via dependency injection with zero code changes in the consumer,
without implementing the production agentic loop of HU-01-01.
"""

from __future__ import annotations

import pytest

from harness_agent.core.entities import (
    Message,
    Role,
    TokenUsage,
    ToolCall,
)
from harness_agent.core.interfaces.provider import (
    Provider,
    ProviderResponse,
    ToolDefinition,
)

# ============================================================================
# Minimal Decoupled Test Consumer (represents agent loop boundary)
# ============================================================================


class TestAgentConsumer:
    """Minimal consumer interacting solely with the abstract Provider contract."""

    __test__ = False

    def __init__(self, provider: Provider) -> None:
        self._provider = provider

    @property
    def provider(self) -> Provider:
        return self._provider

    @provider.setter
    def provider(self, new_provider: Provider) -> None:
        self._provider = new_provider

    async def execute_turn(
        self,
        prompt: str,
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        """Execute a single agentic conversational turn without vendor assumptions."""
        user_message = Message(role=Role.USER, content=prompt)
        response = await self._provider.complete(messages=[user_message], tools=tools)
        return response

    async def execute_conversation(
        self,
        history: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        """Execute a multi-turn step using only canonical entities."""
        return await self._provider.complete(messages=history, tools=tools)


# ============================================================================
# Two Distinct Test Double Implementations of Provider
# ============================================================================


class ScriptedProvider(Provider):
    """First implementation: Deterministic scripted responses."""

    def __init__(self, scripted_responses: list[ProviderResponse]) -> None:
        self._responses = list(scripted_responses)
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        self._call_count += 1
        if self._responses:
            return self._responses.pop(0)
        return ProviderResponse(
            content="Scripted default response",
            usage=TokenUsage(input_tokens=10, output_tokens=5),
        )


class DynamicEchoProvider(Provider):
    """Second implementation: Generates dynamic tool calls or text based on inputs."""

    def __init__(self, model_id: str = "mock-dynamic-v1") -> None:
        self.model_id = model_id
        self.calls_received: list[list[Message]] = []

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        self.calls_received.append(messages)
        last_msg = messages[-1].content if messages else ""

        # If tools are declared, dynamically simulate requesting the first available tool
        if tools:
            first_tool = tools[0]
            simulated_call = ToolCall(
                id=f"dyn_{len(self.calls_received)}",
                name=first_tool.name,
                arguments={"query": last_msg},
            )
            return ProviderResponse(
                content=f"Invoking {first_tool.name} on {self.model_id}",
                tool_calls=[simulated_call],
                usage=TokenUsage(input_tokens=25, output_tokens=15),
            )

        return ProviderResponse(
            content=f"Echo from {self.model_id}: {last_msg}",
            usage=TokenUsage(input_tokens=12, output_tokens=8),
        )


# ============================================================================
# AC-02 Verification Tests
# ============================================================================


@pytest.mark.asyncio
async def test_ac02_consumer_executes_identically_with_swapped_providers() -> None:
    """Verify that TestAgentConsumer executes seamlessly with two different providers.

    AC-02: Dado el bucle, cuando se cambia de proveedor, entonces no se modifica
    ninguna línea del bucle.
    """
    scripted_resp = ProviderResponse(
        content="Fixed response from Provider A",
        tool_calls=[ToolCall(id="c_fixed_1", name="read_file", arguments={"path": "a.txt"})],
        usage=TokenUsage(input_tokens=50, output_tokens=20),
    )
    provider_a = ScriptedProvider(scripted_responses=[scripted_resp])
    provider_b = DynamicEchoProvider(model_id="echo-provider-b")

    tools = [
        ToolDefinition(name="read_file", description="Reads file", parameters={"type": "object"})
    ]

    # 1. Run consumer with Provider A
    consumer = TestAgentConsumer(provider=provider_a)
    resp_a = await consumer.execute_turn("Read file a.txt", tools=tools)

    assert isinstance(resp_a, ProviderResponse)
    assert resp_a.content == "Fixed response from Provider A"
    assert len(resp_a.tool_calls) == 1
    assert resp_a.tool_calls[0].name == "read_file"
    assert resp_a.usage is not None
    assert resp_a.usage.total_tokens == 70
    assert provider_a.call_count == 1

    # 2. Swap to Provider B via dependency injection WITHOUT changing any consumer logic
    consumer.provider = provider_b
    resp_b = await consumer.execute_turn("Read file a.txt", tools=tools)

    assert isinstance(resp_b, ProviderResponse)
    assert "echo-provider-b" in resp_b.content
    assert len(resp_b.tool_calls) == 1
    assert resp_b.tool_calls[0].name == "read_file"
    assert resp_b.usage is not None
    assert resp_b.usage.total_tokens == 40
    assert len(provider_b.calls_received) == 1


@pytest.mark.asyncio
async def test_ac02_liskov_substitution_principle_guarantee() -> None:
    """Verify that multiple polymorphic providers satisfy the Provider interface.

    Demonstrates that consumer code depends strictly on abstractions, fulfilling RNF-12.
    """
    providers: list[Provider] = [
        ScriptedProvider(
            [
                ProviderResponse(
                    content="Option 1", usage=TokenUsage(input_tokens=10, output_tokens=5)
                )
            ]
        ),
        DynamicEchoProvider(model_id="v2"),
    ]

    for p in providers:
        consumer = TestAgentConsumer(provider=p)
        res = await consumer.execute_turn("Hello test")
        assert isinstance(res, ProviderResponse)
        assert res.content != ""
        assert res.usage is not None
        assert res.usage.total_tokens > 0
