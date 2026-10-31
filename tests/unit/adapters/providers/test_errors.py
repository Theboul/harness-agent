"""Translation of LiteLLM failures to the canonical errors (HU-07-02 / FR-010 to FR-012).

The exception classes below reproduce the names and the inheritance that LiteLLM 1.106.2 really
has (checked in research.md, section 1); a test in ``tests/integration`` compares this table with
the installed library. The adapter matches by class name along the MRO, so none of these tests
needs ``litellm``.
"""

from __future__ import annotations

import asyncio

import pytest

from harness_agent.adapters.providers.errors import RateLimited
from harness_agent.adapters.providers.litellm_provider import ERROR_TABLE
from harness_agent.core import (
    Message,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    Role,
)
from tests.unit.adapters.providers.support import SENTINEL, make_provider

USER = [Message(Role.USER, "haz algo")]


class OpenAIError(Exception): ...


class APIError(OpenAIError): ...


class APIConnectionError(APIError): ...


class APITimeoutError(APIConnectionError): ...


class Timeout(APITimeoutError): ...


class APIStatusError(APIError): ...


class RateLimitError(APIStatusError): ...


class BadRequestError(APIStatusError): ...


class PaymentRequiredError(BadRequestError): ...


class ContextWindowExceededError(BadRequestError): ...


class ContentPolicyViolationError(BadRequestError): ...


class BudgetExceededError(Exception): ...


class ServiceUnavailableError(APIStatusError): ...


class BadGatewayError(APIStatusError): ...


class InternalServerError(APIStatusError): ...


class AuthenticationError(APIStatusError): ...


class PermissionDeniedError(APIStatusError): ...


class NotFoundError(APIStatusError): ...


class GatewayTimeoutLike(ServiceUnavailableError): ...


async def failure_of(error: BaseException) -> tuple[Exception, int]:
    """Run one call whose completion function raises ``error``; return the escape and the calls."""
    provider, completion = make_provider(error)
    with pytest.raises(Exception) as raised:
        await provider.complete(list(USER))
    return raised.value, len(completion.calls)


TABLE: list[tuple[type[Exception], type[ProviderError], str]] = [
    (Timeout, ProviderTimeout, "no respondió a tiempo"),
    (APITimeoutError, ProviderTimeout, "no respondió a tiempo"),
    (RateLimitError, RateLimited, "límite de tasa"),
    (PaymentRequiredError, QuotaExceeded, "cuota o el crédito"),
    (BudgetExceededError, QuotaExceeded, "cuota o el crédito"),
    (ServiceUnavailableError, ProviderUnavailable, "no está disponible"),
    (BadGatewayError, ProviderUnavailable, "no está disponible"),
    (InternalServerError, ProviderUnavailable, "no está disponible"),
    (APIConnectionError, ProviderUnavailable, "no está disponible"),
    (AuthenticationError, ProviderError, "devolvió un error"),
    (PermissionDeniedError, ProviderError, "devolvió un error"),
    (NotFoundError, ProviderError, "devolvió un error"),
    (BadRequestError, ProviderError, "devolvió un error"),
    (ContextWindowExceededError, ProviderError, "devolvió un error"),
    (ContentPolicyViolationError, ProviderError, "devolvió un error"),
    (RuntimeError, ProviderError, "devolvió un error"),
    (ValueError, ProviderError, "devolvió un error"),
    (KeyError, ProviderError, "devolvió un error"),
]


class TestTheTable:
    @pytest.mark.parametrize(
        ("raised", "canonical", "fragment"), TABLE, ids=lambda v: getattr(v, "__name__", str(v))
    )
    async def test_each_failure_becomes_exactly_its_canonical_type(
        self, raised: type[Exception], canonical: type[ProviderError], fragment: str
    ) -> None:
        original = raised("mensaje original del proveedor")

        error, calls = await failure_of(original)

        assert type(error) is canonical
        assert fragment in str(error)
        assert error.__cause__ is original
        assert calls == 1

    async def test_the_message_is_in_spanish_and_names_the_class_but_not_the_original_text(
        self,
    ) -> None:
        error, _ = await failure_of(RateLimitError(SENTINEL))

        assert str(error).startswith("El proveedor")
        assert "RateLimitError" in str(error)
        assert SENTINEL not in str(error)

    async def test_a_rate_limit_and_an_exhausted_quota_read_differently(self) -> None:
        rate, _ = await failure_of(RateLimitError("x"))
        quota, _ = await failure_of(PaymentRequiredError("x"))

        assert type(rate) is RateLimited
        assert type(quota) is QuotaExceeded
        assert "tasa" in str(rate)
        assert "tasa" not in str(quota)
        assert str(rate) != str(quota)

    async def test_the_most_specific_class_wins_over_its_parent(self) -> None:
        # ``Timeout`` is also an ``APIConnectionError`` (unavailable) in LiteLLM.
        assert issubclass(Timeout, APIConnectionError)

        error, _ = await failure_of(Timeout("x"))

        assert type(error) is ProviderTimeout

    async def test_a_subclass_that_is_not_listed_inherits_the_mapping_of_its_parent(self) -> None:
        error, _ = await failure_of(GatewayTimeoutLike("x"))
        subclass_of_rate_limit = type("OtraTasa", (RateLimitError,), {})
        other, _ = await failure_of(subclass_of_rate_limit("x"))

        assert type(error) is ProviderUnavailable
        assert type(other) is RateLimited

    async def test_a_payment_required_error_is_not_swallowed_by_its_bad_request_parent(
        self,
    ) -> None:
        assert issubclass(PaymentRequiredError, BadRequestError)

        error, _ = await failure_of(PaymentRequiredError("x"))

        assert type(error) is QuotaExceeded

    def test_the_table_names_every_class_of_the_contract(self) -> None:
        assert set(ERROR_TABLE) == {
            "Timeout",
            "APITimeoutError",
            "RateLimitError",
            "PaymentRequiredError",
            "BudgetExceededError",
            "ServiceUnavailableError",
            "BadGatewayError",
            "InternalServerError",
            "APIConnectionError",
            "ImportError",
        }

    def test_the_table_is_read_only(self) -> None:
        with pytest.raises(TypeError):
            ERROR_TABLE["Otra"] = (ProviderError, "x")  # type: ignore[index]


class TestTheWaitHint:
    """HU-07-04: a rate limit may carry the seconds the provider asked to wait."""

    @pytest.mark.parametrize("hint", [0, 7, 2.5])
    async def test_a_valid_retry_after_of_the_original_error_is_kept(self, hint: float) -> None:
        original = RateLimitError("x")
        original.retry_after = hint  # type: ignore[attr-defined]

        error, _ = await failure_of(original)

        assert isinstance(error, RateLimited)
        assert error.retry_after == hint

    @pytest.mark.parametrize("hint", [-1, float("inf"), float("nan"), True, "5", None])
    async def test_an_unusable_retry_after_is_dropped(self, hint: object) -> None:
        original = RateLimitError("x")
        original.retry_after = hint  # type: ignore[attr-defined]

        error, _ = await failure_of(original)

        assert isinstance(error, RateLimited)
        assert error.retry_after is None

    async def test_without_the_attribute_there_is_no_hint(self) -> None:
        error, _ = await failure_of(RateLimitError("x"))

        assert isinstance(error, RateLimited)
        assert error.retry_after is None

    async def test_an_exhausted_credit_is_not_a_rate_limit_even_with_a_hint(self) -> None:
        original = PaymentRequiredError("x")
        original.retry_after = 5  # type: ignore[attr-defined]

        error, _ = await failure_of(original)

        assert type(error) is QuotaExceeded
        assert not hasattr(error, "retry_after")


class TestABrokenInstallation:
    @pytest.mark.parametrize("raised", [ImportError, ModuleNotFoundError])
    async def test_an_import_error_during_the_call_points_to_the_install_command(
        self, raised: type[ImportError]
    ) -> None:
        original = raised("No module named 'otro'")

        error, calls = await failure_of(original)

        assert type(error) is ProviderError
        assert 'pip install -e ".[litellm]"' in str(error)
        assert "ruta corta" in str(error)
        assert "otro" not in str(error)
        assert error.__cause__ is original
        assert calls == 1


class TestWhatMustNotBeTranslated:
    @pytest.mark.parametrize("raised", [asyncio.CancelledError, KeyboardInterrupt])
    async def test_cancellation_and_interrupts_pass_through(
        self, raised: type[BaseException]
    ) -> None:
        provider, completion = make_provider(raised())

        with pytest.raises(raised):
            await provider.complete(list(USER))

        assert len(completion.calls) == 1

    async def test_a_canonical_error_raised_by_the_function_passes_through_unchanged(self) -> None:
        original = QuotaExceeded("ya canónico")

        error, _ = await failure_of(original)

        assert error is original
        assert error.__cause__ is None

    async def test_there_are_no_retries(self) -> None:
        _, calls = await failure_of(RateLimitError("x"))

        assert calls == 1


def test_the_table_entries_are_canonical_types_with_a_message() -> None:
    for kind, message in ERROR_TABLE.values():
        assert issubclass(kind, ProviderError)
        assert message
        assert "{kind}" in message or kind is ProviderError
