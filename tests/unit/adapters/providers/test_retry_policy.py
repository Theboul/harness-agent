"""``RetryPolicy`` and ``RetryAttempt`` (HU-07-04 / FR-004, FR-005, FR-012)."""

from __future__ import annotations

import dataclasses
import math

import pytest

from harness_agent.adapters.providers.retrying_provider import RetryAttempt, RetryPolicy

SENTINEL = "VALOR-DE-PRUEBA-123"


def test_valid_policy_keeps_its_values() -> None:
    policy = RetryPolicy(max_attempts=4, base_delay=1.5, max_delay=10)
    assert (policy.max_attempts, policy.base_delay, policy.max_delay) == (4, 1.5, 10)


def test_policy_and_attempt_are_frozen() -> None:
    policy = RetryPolicy(max_attempts=2, base_delay=1, max_delay=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.max_attempts = 3  # type: ignore[misc]
    attempt = RetryAttempt(attempt=1, max_attempts=2, error_type="ProviderTimeout", delay=1.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        attempt.delay = 2.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("max_attempts", "base_delay", "max_delay"),
    [
        (0, 1, 2),
        (11, 1, 2),
        (-1, 1, 2),
        (True, 1, 2),
        (2.0, 1, 2),
        ("3", 1, 2),
        (3, 0, 2),
        (3, -1, 2),
        (3, True, 2),
        (3, math.nan, 2),
        (3, math.inf, math.inf),
        (3, "1", 2),
        (3, 5, 4),
        (3, 1, 601),
        (3, 1, "2"),
    ],
)
def test_invalid_values_are_rejected_without_repeating_them(
    max_attempts: object, base_delay: object, max_delay: object
) -> None:
    with pytest.raises(ValueError) as caught:
        RetryPolicy(max_attempts, base_delay, max_delay)  # type: ignore[arg-type]
    assert SENTINEL not in str(caught.value)
    assert str(caught.value)


def test_error_message_never_repeats_the_value_received() -> None:
    with pytest.raises(ValueError) as caught:
        RetryPolicy(SENTINEL, 1, 2)  # type: ignore[arg-type]
    assert SENTINEL not in str(caught.value)


@pytest.mark.parametrize(
    ("retry", "expected"), [(1, 2.0), (2, 4.0), (3, 8.0), (4, 16.0), (5, 30.0), (9, 30.0)]
)
def test_backoff_doubles_and_is_capped(retry: int, expected: float) -> None:
    policy = RetryPolicy(max_attempts=10, base_delay=2, max_delay=30)
    assert policy.backoff(retry) == expected
