"""The rule of the failover between models (HU-07-05): which errors switch and what a turn tried.

Pure domain logic with no I/O: it says *whether* a failure may be answered by trying another model
and *which* models a turn has already tried. The adapter that makes the calls (``FailoverProvider``)
and the composition root that connects it live outside the core.

A failure is eligible only if it is one the person cannot fix by changing the request: an
exhausted quota or rate limit, a timeout or an unavailable service (the adapters translate the
connection errors to the last one). A bad key, a malformed request, a refusal by content policy
and anything unknown are *not* eligible: failing closed means the person sees the error instead
of the harness sending the same request to other providers.
"""

from __future__ import annotations

from collections.abc import Iterable

from harness_agent.core.interfaces.provider import (
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
)

ELIGIBLE_ERRORS: tuple[type[Exception], ...] = (
    QuotaExceeded,
    ProviderTimeout,
    ProviderUnavailable,
)


def is_failover_eligible(error: object) -> bool:
    """Whether ``error`` may be answered by switching to another model.

    Only an instance of an eligible kind is; the generic provider error, any other exception,
    a cancellation and anything that is not an exception are not.
    """
    return isinstance(error, ELIGIBLE_ERRORS)


class FailoverTurn:
    """The models one turn has tried, over an ordered list of keys.

    A key is a name (an alias of the configuration or the word of the default model); the turn
    only compares them. ``begin`` forgets everything, so each request of the person starts clean;
    ``next_untried`` always answers with the first key *of the list* that was not marked, so the
    order of the list is the order of the failover, whatever order the marks came in.

    Args:
        chain: The keys in the order they are tried.
    """

    def __init__(self, chain: Iterable[str]) -> None:
        self._chain = tuple(chain)
        self._tried: set[str] = set()

    @property
    def chain(self) -> tuple[str, ...]:
        """The keys, in order."""
        return self._chain

    @property
    def tried(self) -> frozenset[str]:
        """The keys marked in this turn."""
        return frozenset(self._tried)

    def begin(self) -> None:
        """Start a new turn: nothing has been tried."""
        self._tried.clear()

    def mark(self, key: str) -> None:
        """Record that ``key`` was tried; marking it again changes nothing."""
        self._tried.add(key)

    def has_tried(self, key: str) -> bool:
        """Whether ``key`` was tried in this turn."""
        return key in self._tried

    def next_untried(self) -> str | None:
        """The first key of the list that was not tried, or ``None`` if there is none."""
        for key in self._chain:
            if key not in self._tried:
                return key
        return None
