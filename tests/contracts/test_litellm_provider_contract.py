"""LiteLLMProvider honours the Provider contract and is interchangeable with the doubles.

Mirrors ``test_fake_provider_contract`` (HU-00-03) for the real adapter of HU-07-02: the same
minimal consumer runs against every provider, so changing provider needs no change in the
consumer. The adapter is fed by an injected completion function: no network, no key, no library.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from harness_agent.adapters.providers.errors import RateLimited
from harness_agent.adapters.providers.litellm_provider import LiteLLMProvider
from harness_agent.core import (
    Message,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    ProviderUnavailable,
    Role,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from tests.contracts.test_provider_interchangeability import TestAgentConsumer
from tests.doubles import DummyProvider, FakeProvider, ScriptedProvider
from tests.unit.adapters.providers.support import RecordingCompletion, reply, wire_call

ANSWER = ProviderResponse(content="respuesta", usage=TokenUsage(input_tokens=2, output_tokens=3))
WIRE_ANSWER = reply("respuesta", usage={"prompt_tokens": 2, "completion_tokens": 3})
READ_FILE = ToolDefinition("read_file", "Read a text file", {"type": "object", "properties": {}})


def adapter(*outcomes: Any) -> tuple[LiteLLMProvider, RecordingCompletion]:
    completion = RecordingCompletion(*outcomes)
    return LiteLLMProvider("proveedor/modelo", max_output_tokens=64, completion=completion), (
        completion
    )


def providers() -> list[Provider]:
    return [
        DummyProvider(ANSWER),
        ScriptedProvider([ANSWER]),
        FakeProvider([ANSWER]),
        adapter(WIRE_ANSWER)[0],
    ]


@pytest.mark.parametrize("provider", providers(), ids=lambda p: type(p).__name__)
async def test_the_consumer_works_with_every_provider(provider: Provider) -> None:
    response = await TestAgentConsumer(provider).execute_turn("hola")

    assert isinstance(provider, Provider)
    assert isinstance(response, ProviderResponse)
    assert response.content == "respuesta"
    assert response.usage is not None
    assert response.usage.total_tokens == 5


async def test_swapping_the_provider_needs_no_change_in_the_consumer() -> None:
    consumer = TestAgentConsumer(FakeProvider([ANSWER]))
    first = await consumer.execute_turn("hola")

    consumer.provider = adapter(WIRE_ANSWER)[0]
    second = await consumer.execute_turn("hola")

    assert first == second == ANSWER


async def test_the_tool_calls_are_the_same_as_the_ones_a_script_would_give() -> None:
    expected = ProviderResponse(
        content="voy",
        tool_calls=[ToolCall("toolu_01A", "read_file", {"path": "README.md"})],
    )
    wire = reply("voy", [wire_call("toolu_01A", "read_file", {"path": "README.md"})])

    scripted = await TestAgentConsumer(FakeProvider([expected])).execute_turn("lee", [READ_FILE])
    real = await TestAgentConsumer(adapter(wire)[0]).execute_turn("lee", [READ_FILE])

    assert scripted == real == expected


async def test_the_adapter_receives_the_canonical_arguments_and_changes_neither() -> None:
    provider, completion = adapter(WIRE_ANSWER)
    messages = [Message(Role.USER, "hola")]
    before = (copy.deepcopy(messages), copy.deepcopy([READ_FILE]))

    await provider.complete(messages, [READ_FILE])

    assert (messages, [READ_FILE]) == before
    assert completion.calls[0]["messages"] == [{"role": "user", "content": "hola"}]
    assert [tool["function"]["name"] for tool in completion.calls[0]["tools"]] == ["read_file"]


class RateLimitError(Exception): ...


class Timeout(Exception): ...


class ServiceUnavailableError(Exception): ...


class AuthenticationError(Exception): ...


@pytest.mark.parametrize(
    ("simulated", "real"),
    [
        (RateLimited("cuota"), RateLimitError("tasa")),
        (ProviderTimeout("tiempo"), Timeout("tiempo")),
        (ProviderUnavailable("caído"), ServiceUnavailableError("caído")),
        (ProviderError("otro"), AuthenticationError("clave")),
    ],
    ids=lambda error: type(error).__name__,
)
async def test_a_failure_arrives_with_the_same_type_as_the_simulated_one(
    simulated: ProviderError, real: Exception
) -> None:
    fake_provider = FakeProvider([simulated])
    real_provider, _ = adapter(real)

    with pytest.raises(ProviderError) as from_the_double:
        await TestAgentConsumer(fake_provider).execute_turn("hola")
    with pytest.raises(ProviderError) as from_the_adapter:
        await TestAgentConsumer(real_provider).execute_turn("hola")

    assert type(from_the_adapter.value) is type(from_the_double.value)
