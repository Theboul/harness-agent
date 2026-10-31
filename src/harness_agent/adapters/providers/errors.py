"""Errors of the provider adapters that the core port does not define (HU-07-04).

``QuotaExceeded`` (the port of the core) covers both a rate limit, which passes by itself, and an
exhausted credit, which does not. The port is a contract of the three areas, so the distinction
lives here as a subtype: whoever catches ``QuotaExceeded`` keeps catching both.
"""

from __future__ import annotations

import math

from harness_agent.core import QuotaExceeded


def valid_wait_hint(value: object) -> float | None:
    """The hint as seconds if it is a finite number of at least zero (a boolean is not one)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


class RateLimited(QuotaExceeded):
    """The provider refused the call because of its rate limit; waiting is expected to fix it.

    Args:
        message: The text of the error, written by the adapter (never the provider's own text).
        retry_after: The seconds the provider asked to wait, if it said so; anything that is not a
            finite number of at least zero is dropped.
    """

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = valid_wait_hint(retry_after)
