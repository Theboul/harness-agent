"""``RetryingProvider``: a passing failure does not sink the call (HU-07-04 / US1)."""

from __future__ import annotations

import pytest

from harness_agent.adapters.providers.errors import RateLimited
from harness_agent.core import ProviderTimeout, ProviderUnavailable, ToolDefinition
from tests.doubles.fake_provider import FakeProvider
from tests.unit.adapters.providers.retry_support import (
    OK,
    USER,
    RecordingObserver,
    RecordingSleep,
    policy,
    wrap,
)


async def test_a_good_first_answer_is_returned_without_waiting() -> None:
    inner = FakeProvider([OK])
    sleep = RecordingSleep()
    assert await wrap(inner, sleep).complete(USER) == OK
    assert inner.call_count == 1
    assert sleep.waits == []


async def test_two_rate_limits_then_an_answer_waits_two_and_four() -> None:
    inner = FakeProvider([RateLimited("a"), RateLimited("b"), OK])
    sleep = RecordingSleep()
    assert await wrap(inner, sleep).complete(USER) == OK
    assert inner.call_count == 3
    assert sleep.waits == [2.0, 4.0]


@pytest.mark.parametrize(
    "error", [ProviderTimeout("t"), ProviderUnavailable("u"), RateLimited("r")]
)
async def test_each_transient_error_is_retried(error: Exception) -> None:
    inner = FakeProvider([error, OK])  # type: ignore[list-item]
    sleep = RecordingSleep()
    assert await wrap(inner, sleep).complete(USER) == OK
    assert sleep.waits == [2.0]


async def test_the_wait_never_goes_above_the_cap() -> None:
    errors = [ProviderUnavailable("u")] * 5
    inner = FakeProvider([*errors, OK])
    sleep = RecordingSleep()
    await wrap(inner, sleep, policy(attempts=6, base=2, cap=5)).complete(USER)
    assert sleep.waits == [2.0, 4.0, 5.0, 5.0, 5.0]


async def test_messages_and_tools_reach_every_attempt_unchanged() -> None:
    tools = [ToolDefinition(name="t", description="d")]
    inner = FakeProvider([ProviderTimeout("t"), OK])
    await wrap(inner, RecordingSleep()).complete(USER, tools)
    assert inner.received == [USER, USER]
    assert inner.received_tools == [tools, tools]


async def test_the_observer_hears_about_every_retry_with_no_request_data() -> None:
    inner = FakeProvider([RateLimited("a"), ProviderTimeout("b"), OK])
    observer = RecordingObserver()
    await wrap(inner, RecordingSleep(), observer=observer).complete(USER)
    assert [(a.attempt, a.max_attempts, a.error_type, a.delay) for a in observer.attempts] == [
        (1, 5, "RateLimited", 2.0),
        (2, 5, "ProviderTimeout", 4.0),
    ]
