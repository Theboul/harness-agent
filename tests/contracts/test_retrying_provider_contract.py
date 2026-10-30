"""RetryingProvider honours the Provider contract (HU-07-04): same consumer, same answers/errors."""

from __future__ import annotations

import pytest

from harness_agent.adapters.providers.retrying_provider import RetryingProvider, RetryPolicy
from harness_agent.core import (
    Message,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    QuotaExceeded,
    Role,
    TokenUsage,
    ToolDefinition,
)
from tests.contracts.test_provider_interchangeability import TestAgentConsumer
from tests.doubles import FakeProvider

ANSWER = ProviderResponse(content="respuesta", usage=TokenUsage(input_tokens=2, output_tokens=3))
POLICY = RetryPolicy(max_attempts=3, base_delay=1, max_delay=2)


async def _no_wait(_seconds: float) -> None:
    return None


def _wrap(inner: Provider) -> RetryingProvider:
    return RetryingProvider(inner, POLICY, sleep=_no_wait)


async def test_the_consumer_works_with_the_wrapper_as_with_the_wrapped_provider() -> None:
    direct = await TestAgentConsumer(FakeProvider([ANSWER])).execute_turn("hola")
    wrapped = await TestAgentConsumer(_wrap(FakeProvider([ANSWER]))).execute_turn("hola")

    assert isinstance(_wrap(FakeProvider([ANSWER])), Provider)
    assert direct == wrapped == ANSWER


async def test_the_wrapper_passes_the_canonical_arguments_through() -> None:
    inner = FakeProvider([ANSWER])
    definition = ToolDefinition(name="echo", description="d", parameters={})

    await TestAgentConsumer(_wrap(inner)).execute_turn("hola", [definition])

    assert inner.received == [[Message(role=Role.USER, content="hola")]]
    assert inner.received_tools == [[definition]]


@pytest.mark.parametrize(
    "error", [QuotaExceeded("cuota"), ProviderError("otro")], ids=lambda e: type(e).__name__
)
async def test_a_permanent_failure_arrives_with_the_same_type_as_without_the_wrapper(
    error: ProviderError,
) -> None:
    with pytest.raises(ProviderError) as direct:
        await TestAgentConsumer(FakeProvider([error])).execute_turn("hola")
    with pytest.raises(ProviderError) as wrapped:
        await TestAgentConsumer(_wrap(FakeProvider([error]))).execute_turn("hola")

    assert type(wrapped.value) is type(direct.value)


async def test_an_exhausted_transient_failure_arrives_as_the_same_canonical_error() -> None:
    script = [ProviderTimeout("a")] * 3
    with pytest.raises(ProviderTimeout):
        await TestAgentConsumer(_wrap(FakeProvider(script))).execute_turn("hola")
