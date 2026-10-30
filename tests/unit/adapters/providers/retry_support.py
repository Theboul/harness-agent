"""Shared builders for the retry tests (HU-07-04): a recording sleep and a recording observer."""

from __future__ import annotations

from harness_agent.adapters.providers.retrying_provider import (
    RetryAttempt,
    RetryingProvider,
    RetryPolicy,
)
from harness_agent.core import Message, Provider, ProviderResponse, Role
from tests.doubles.fake_provider import Step

SENTINEL = "VALOR-DE-PRUEBA-123"
USER = [Message(Role.USER, "haz algo")]
OK = ProviderResponse(content="listo")


class RecordingSleep:
    """An injectable ``sleep`` that records the requested waits and never waits."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


class RecordingObserver:
    """An observer that keeps every ``RetryAttempt`` it is told about."""

    def __init__(self) -> None:
        self.attempts: list[RetryAttempt] = []

    def __call__(self, attempt: RetryAttempt) -> None:
        self.attempts.append(attempt)


def policy(attempts: int = 5, base: float = 2, cap: float = 30) -> RetryPolicy:
    return RetryPolicy(max_attempts=attempts, base_delay=base, max_delay=cap)


def wrap(
    inner: Provider,
    sleep: RecordingSleep,
    retry_policy: RetryPolicy | None = None,
    observer: RecordingObserver | None = None,
) -> RetryingProvider:
    return RetryingProvider(inner, retry_policy or policy(), sleep=sleep, observer=observer)


__all__ = [
    "OK",
    "SENTINEL",
    "USER",
    "RecordingObserver",
    "RecordingSleep",
    "Step",
    "policy",
    "wrap",
]
