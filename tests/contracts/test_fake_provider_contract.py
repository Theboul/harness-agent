"""FakeProvider honours the Provider contract and is interchangeable with the other doubles.

Mirrors ``test_provider_interchangeability`` for the simulated provider of HU-00-03 without
editing that module: the same minimal consumer runs against every double.
"""

from __future__ import annotations

import pytest

from harness_agent.core import (
    Message,
    Provider,
    ProviderResponse,
    Role,
    TokenUsage,
    ToolDefinition,
)
from tests.contracts.test_provider_interchangeability import TestAgentConsumer
from tests.doubles import DummyProvider, FakeProvider, ScriptedProvider

ANSWER = ProviderResponse(content="respuesta", usage=TokenUsage(input_tokens=2, output_tokens=3))


def _doubles() -> list[Provider]:
    return [DummyProvider(ANSWER), ScriptedProvider([ANSWER]), FakeProvider([ANSWER])]


@pytest.mark.parametrize("provider", _doubles(), ids=lambda p: type(p).__name__)
async def test_the_consumer_works_with_every_double(provider: Provider) -> None:
    response = await TestAgentConsumer(provider).execute_turn("hola")

    assert isinstance(provider, Provider)
    assert isinstance(response, ProviderResponse)
    assert response.content == "respuesta"
    assert response.usage is not None
    assert response.usage.total_tokens == 5


async def test_swapping_the_provider_needs_no_change_in_the_consumer() -> None:
    consumer = TestAgentConsumer(DummyProvider(ANSWER))
    first = await consumer.execute_turn("hola")

    consumer.provider = FakeProvider([ANSWER])
    second = await consumer.execute_turn("hola")

    assert first == second == ANSWER


async def test_fake_provider_receives_the_canonical_arguments() -> None:
    provider = FakeProvider([ANSWER])
    definition = ToolDefinition(name="echo", description="d", parameters={})

    await TestAgentConsumer(provider).execute_turn("hola", [definition])

    assert provider.received == [[Message(role=Role.USER, content="hola")]]
    assert provider.received_tools == [[definition]]
