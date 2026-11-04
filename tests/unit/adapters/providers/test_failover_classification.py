"""Which LiteLLM failures the failover switches on (HU-07-05 / T004).

The classification is the one of the adapter (``ERROR_TABLE``) plus the rule of the core
(``is_failover_eligible``): this test fixes the contract between them with the class names LiteLLM
raises, through an injected completion function. No network, no key.
"""

from __future__ import annotations

import pytest

from harness_agent.core import ProviderError, is_failover_eligible
from tests.unit.adapters.providers.support import SENTINEL, make_provider
from tests.unit.adapters.providers.test_failover_provider import USER


def failure(name: str) -> Exception:
    """An exception whose class has the given name, as the ones of LiteLLM do."""
    kind: type[Exception] = type(name, (Exception,), {})
    return kind(SENTINEL)


ELIGIBLE = [
    "RateLimitError",
    "PaymentRequiredError",
    "BudgetExceededError",
    "Timeout",
    "APITimeoutError",
    "ServiceUnavailableError",
    "BadGatewayError",
    "InternalServerError",
    "APIConnectionError",
]
NOT_ELIGIBLE = [
    "AuthenticationError",
    "BadRequestError",
    "ContentPolicyViolationError",
    "NotFoundError",
    "ContextWindowExceededError",
    "PermissionDeniedError",
    "SomethingNobodyListed",
    "ImportError",
]


@pytest.mark.parametrize("name", ELIGIBLE)
async def test_the_transient_failures_of_litellm_are_eligible(name: str) -> None:
    provider, _ = make_provider(failure(name))

    with pytest.raises(ProviderError) as raised:
        await provider.complete(USER)

    assert is_failover_eligible(raised.value) is True


@pytest.mark.parametrize("name", NOT_ELIGIBLE)
async def test_the_failures_that_depend_on_the_request_or_are_unknown_are_not_eligible(
    name: str,
) -> None:
    provider, _ = make_provider(failure(name))

    with pytest.raises(ProviderError) as raised:
        await provider.complete(USER)

    assert is_failover_eligible(raised.value) is False


async def test_a_subclass_of_a_listed_failure_is_classified_by_its_ancestor() -> None:
    base = type("RateLimitError", (Exception,), {})
    child = type("SomeProviderRateLimit", (base,), {})(SENTINEL)
    provider, _ = make_provider(child)

    with pytest.raises(ProviderError) as raised:
        await provider.complete(USER)

    assert is_failover_eligible(raised.value) is True
