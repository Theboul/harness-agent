"""Retries with exponential backoff around any ``Provider`` (HU-07-04).

``RetryingProvider`` is a ``Provider`` that wraps another one. It retries only the failures that
pass by themselves (timeout, service unavailable, rate limit), waits longer each time, and gives
up after a bounded number of attempts by raising the last error as it came, so a later failover
(HU-07-05) sees the same error it would see without retries. It lives in the adapter layer: the
loop and the ports do not know that retries exist.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from harness_agent.adapters.providers.errors import RateLimited, valid_wait_hint
from harness_agent.core import (
    Message,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    ProviderUnavailable,
    ToolDefinition,
)

MAX_ATTEMPTS_LIMIT = 10
MAX_DELAY_LIMIT = 600.0

_BAD_ATTEMPTS = f"max_attempts debe ser un entero entre 1 y {MAX_ATTEMPTS_LIMIT}."
_BAD_BASE = "base_delay debe ser un número de segundos mayor que 0."
_BAD_MAX = f"max_delay debe ser un número de segundos entre base_delay y {MAX_DELAY_LIMIT:g}."

# What passes by itself. Anything else (a bad key, a malformed request, an exhausted credit, an
# unreadable answer) fails at once: waiting would not fix it.
TRANSIENT_ERRORS: tuple[type[ProviderError], ...] = (
    ProviderTimeout,
    ProviderUnavailable,
    RateLimited,
)


def _is_number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, int | float) and math.isfinite(value)


@dataclass(frozen=True)
class RetryPolicy:
    """How many times to try and how long to wait between tries (seconds).

    ``max_attempts`` counts the first call, so ``1`` means no retries. The wait before retry
    ``n`` is ``base_delay * 2 ** (n - 1)``, never above ``max_delay``; there is no randomness.
    """

    max_attempts: int
    base_delay: float
    max_delay: float

    def __post_init__(self) -> None:
        attempts = self.max_attempts
        if (
            isinstance(attempts, bool)
            or not isinstance(attempts, int)
            or not 1 <= attempts <= MAX_ATTEMPTS_LIMIT
        ):
            raise ValueError(_BAD_ATTEMPTS)
        if not _is_number(self.base_delay) or self.base_delay <= 0:
            raise ValueError(_BAD_BASE)
        if (
            not _is_number(self.max_delay)
            or self.max_delay < self.base_delay
            or self.max_delay > MAX_DELAY_LIMIT
        ):
            raise ValueError(_BAD_MAX)

    def backoff(self, retry: int) -> float:
        """The wait before retry number ``retry`` (1 is the first retry)."""
        exponent = min(retry - 1, 64)
        return float(min(self.base_delay * 2**exponent, self.max_delay))


@dataclass(frozen=True)
class RetryAttempt:
    """What an observer learns about one retry: never the request nor the text of the error."""

    attempt: int
    max_attempts: int
    error_type: str
    delay: float


Sleep = Callable[[float], Awaitable[None]]
Observer = Callable[[RetryAttempt], None]


class RetryingProvider(Provider):
    """A ``Provider`` that retries the transient failures of the provider it wraps.

    Args:
        inner: The provider that makes the calls.
        policy: Number of attempts and waits.
        sleep: Awaits the given seconds; tests inject one that does not wait.
        observer: Told about every retry before the wait; a failure of the observer is ignored.
    """

    def __init__(
        self,
        inner: Provider,
        policy: RetryPolicy,
        *,
        sleep: Sleep = asyncio.sleep,
        observer: Observer | None = None,
    ) -> None:
        self._inner = inner
        self._policy = policy
        self._sleep = sleep
        self._observer = observer

    @property
    def inner(self) -> Provider:
        """The wrapped provider."""
        return self._inner

    def _notify(self, attempt: RetryAttempt) -> None:
        if self._observer is None:
            return
        try:
            self._observer(attempt)
        except Exception:
            # The record is a courtesy: it must never change the outcome of the call.
            return

    def _wait_for(self, error: ProviderError, retry: int) -> float | None:
        """Seconds to wait before the next try, or ``None`` if the provider asked for too long."""
        delay = self._policy.backoff(retry)
        hint = valid_wait_hint(getattr(error, "retry_after", None))
        if hint is None:
            return delay
        if hint > self._policy.max_delay:
            return None
        return max(delay, hint)

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        """Call the wrapped provider, retrying the transient failures as the policy says."""
        attempt = 1
        while True:
            try:
                return await self._inner.complete(messages, tools)
            except TRANSIENT_ERRORS as error:
                if attempt >= self._policy.max_attempts:
                    raise
                delay = self._wait_for(error, attempt)
                if delay is None:
                    raise
                self._notify(
                    RetryAttempt(
                        attempt=attempt,
                        max_attempts=self._policy.max_attempts,
                        error_type=type(error).__name__,
                        delay=delay,
                    )
                )
                await self._sleep(delay)
                attempt += 1
