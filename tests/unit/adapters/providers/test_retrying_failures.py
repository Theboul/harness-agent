"""``RetryingProvider``: what is not retried and when it gives up (HU-07-04 / US2)."""

from __future__ import annotations

import asyncio

import pytest

from harness_agent.adapters.providers.errors import RateLimited
from harness_agent.core import ProviderError, ProviderTimeout, ProviderUnavailable, QuotaExceeded
from harness_agent.core.interfaces.provider import Provider, ProviderResponse
from tests.doubles.fake_provider import FakeProvider
from tests.unit.adapters.providers.retry_support import (
    OK,
    SENTINEL,
    USER,
    RecordingObserver,
    RecordingSleep,
    policy,
    wrap,
)


@pytest.mark.parametrize(
    "error", [QuotaExceeded("crédito"), ProviderError("genérico")], ids=["quota", "generic"]
)
async def test_a_non_transient_error_fails_at_once(error: ProviderError) -> None:
    inner = FakeProvider([error, OK])
    sleep = RecordingSleep()
    observer = RecordingObserver()
    with pytest.raises(ProviderError) as caught:
        await wrap(inner, sleep, observer=observer).complete(USER)
    assert type(caught.value) is type(error)
    assert inner.call_count == 1
    assert sleep.waits == []
    assert observer.attempts == []


async def test_a_foreign_exception_is_not_caught() -> None:
    class Boom(Provider):
        calls = 0

        async def complete(self, messages: list, tools: list | None = None) -> ProviderResponse:  # type: ignore[type-arg]
            Boom.calls += 1
            raise KeyError(SENTINEL)

    with pytest.raises(KeyError):
        await wrap(Boom(), RecordingSleep()).complete(USER)
    assert Boom.calls == 1


@pytest.mark.parametrize("attempts", [1, 2, 4])
async def test_when_attempts_run_out_the_last_error_goes_up_unchanged(attempts: int) -> None:
    errors = [ProviderUnavailable(f"fallo {n}") for n in range(attempts)]
    calls: list[ProviderUnavailable] = []

    class Always(Provider):
        async def complete(self, messages: list, tools: list | None = None) -> ProviderResponse:  # type: ignore[type-arg]
            error = errors[len(calls)]
            calls.append(error)
            raise error

    sleep = RecordingSleep()
    with pytest.raises(ProviderUnavailable) as caught:
        await wrap(Always(), sleep, policy(attempts=attempts)).complete(USER)
    assert caught.value is errors[-1]
    assert len(calls) == attempts
    assert len(sleep.waits) == attempts - 1


async def test_one_attempt_means_no_retries() -> None:
    inner = FakeProvider([ProviderTimeout("t"), OK])
    sleep = RecordingSleep()
    with pytest.raises(ProviderTimeout):
        await wrap(inner, sleep, policy(attempts=1)).complete(USER)
    assert inner.call_count == 1
    assert sleep.waits == []


async def test_a_longer_hint_replaces_the_backoff() -> None:
    inner = FakeProvider([RateLimited("r", retry_after=12), OK])
    sleep = RecordingSleep()
    await wrap(inner, sleep).complete(USER)
    assert sleep.waits == [12]


async def test_a_shorter_hint_does_not_shorten_the_backoff() -> None:
    inner = FakeProvider([RateLimited("r", retry_after=0.5), OK])
    sleep = RecordingSleep()
    await wrap(inner, sleep).complete(USER)
    assert sleep.waits == [2.0]


async def test_a_hint_above_the_cap_is_not_waited_for() -> None:
    inner = FakeProvider([RateLimited("r", retry_after=31), OK])
    sleep = RecordingSleep()
    observer = RecordingObserver()
    with pytest.raises(RateLimited):
        await wrap(inner, sleep, observer=observer).complete(USER)
    assert inner.call_count == 1
    assert sleep.waits == []
    assert observer.attempts == []


async def test_a_hint_equal_to_the_cap_is_waited_for() -> None:
    inner = FakeProvider([RateLimited("r", retry_after=30), OK])
    sleep = RecordingSleep()
    await wrap(inner, sleep).complete(USER)
    assert sleep.waits == [30]


async def test_an_unreadable_hint_is_ignored() -> None:
    error = ProviderUnavailable("u")
    error.retry_after = "soon"  # type: ignore[attr-defined]
    inner = FakeProvider([error, OK])
    sleep = RecordingSleep()
    await wrap(inner, sleep).complete(USER)
    assert sleep.waits == [2.0]


async def test_a_failing_observer_changes_nothing() -> None:
    def broken(_attempt: object) -> None:
        raise RuntimeError(SENTINEL)

    inner = FakeProvider([ProviderTimeout("t"), OK])
    sleep = RecordingSleep()
    provider = wrap(inner, sleep)
    provider._observer = broken
    assert await provider.complete(USER) == OK
    assert sleep.waits == [2.0]


async def test_the_observer_record_never_carries_the_error_text() -> None:
    inner = FakeProvider([ProviderTimeout(f"texto {SENTINEL}"), OK])
    observer = RecordingObserver()
    await wrap(inner, RecordingSleep(), observer=observer).complete(USER)
    assert SENTINEL not in repr(observer.attempts)


async def test_cancellation_from_the_provider_is_not_retried() -> None:
    class Cancelled(Provider):
        calls = 0

        async def complete(self, messages: list, tools: list | None = None) -> ProviderResponse:  # type: ignore[type-arg]
            Cancelled.calls += 1
            raise asyncio.CancelledError

    sleep = RecordingSleep()
    with pytest.raises(asyncio.CancelledError):
        await wrap(Cancelled(), sleep).complete(USER)
    assert Cancelled.calls == 1
    assert sleep.waits == []


async def test_cancellation_during_the_wait_goes_up_and_stops_retrying() -> None:
    inner = FakeProvider([ProviderTimeout("t"), OK])

    async def cancelled_sleep(_seconds: float) -> None:
        raise asyncio.CancelledError

    provider = wrap(inner, RecordingSleep())
    provider._sleep = cancelled_sleep
    with pytest.raises(asyncio.CancelledError):
        await provider.complete(USER)
    assert inner.call_count == 1


def test_the_default_sleep_is_the_one_of_asyncio() -> None:
    from harness_agent.adapters.providers.retrying_provider import RetryingProvider

    assert RetryingProvider(FakeProvider([OK]), policy())._sleep is asyncio.sleep
