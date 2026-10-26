"""Session limits for the agentic loop (HU-01-06): turns, time and token budget.

The rules live here, apart from the loop (Area A, protected file): ``SessionLimits`` are the
maximums, ``LimitTracker`` counts what a session has used and ``LimitReached`` says which limit
stopped it. The module depends only on the standard library and on ``core.entities``; the clock is
injected, nothing is read, printed or published from here (the loop publishes ``LIMIT_REACHED``).

Vocabulary (decided in the spec, pending the Product Owner): a *turn* is one call to the model,
the session is the life of one ``AgentLoop``, and the time counts only what the tasks of the
session take (the wait of the user between tasks is not counted). ``max_tokens`` is the budget of
the whole run; it is not the cap of one call (that is ``limits.max_output_tokens``).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from harness_agent.core.entities import TokenUsage


class LimitKind(str, Enum):
    """Which limit was reached; the value is the key carried by the ``LIMIT_REACHED`` event."""

    TURNS = "turns"
    TIME = "time"
    TOKENS = "tokens"


class InvalidLimitsError(ValueError):
    """A limit is not a positive integer; the message never reproduces the received value."""


def _check_positive(field: str, value: object) -> None:
    # bool is an int subclass: ``True`` is not a valid limit.
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvalidLimitsError(f"El límite '{field}' debe ser un entero mayor que cero.")


@dataclass(frozen=True)
class SessionLimits:
    """Maximums of one session.

    Attributes:
        max_turns: Calls to the model allowed in the session.
        max_seconds: Seconds the tasks of the session may take in total.
        max_tokens: Tokens (input plus output) the whole session may consume.
    """

    max_turns: int
    max_seconds: int
    max_tokens: int

    def __post_init__(self) -> None:
        _check_positive("max_turns", self.max_turns)
        _check_positive("max_seconds", self.max_seconds)
        _check_positive("max_tokens", self.max_tokens)


@dataclass(frozen=True)
class LimitReached:
    """The limit that stopped the session, with what was used and the maximum."""

    kind: LimitKind
    used: int
    maximum: int


class LimitTracker:
    """Counts turns, tokens and time of one session and says which limit is reached.

    Counters only grow, so a limit that is reached stays reached (fail closed). Several limits
    reached at once are reported in a fixed order: turns, time, tokens.
    """

    def __init__(self, limits: SessionLimits, clock: Callable[[], float] | None = None) -> None:
        self._limits = limits
        self._clock = time.monotonic if clock is None else clock
        self._turns = 0
        self._tokens = 0
        self._elapsed = 0.0
        self._task_started: float | None = None

    def begin_task(self) -> None:
        """Start counting time for a task (the user's wait between tasks is not counted)."""
        if self._task_started is None:
            self._task_started = self._clock()

    def end_task(self) -> None:
        """Stop counting time for the running task; harmless when none is running."""
        if self._task_started is not None:
            self._elapsed += max(0.0, self._clock() - self._task_started)
            self._task_started = None

    def start_turn(self) -> None:
        """Count one call to the model; call it right before the call is made."""
        self._turns += 1

    def add_usage(self, usage: TokenUsage | None) -> None:
        """Add the tokens reported by the provider; missing or invalid data counts as zero."""
        if usage is None:
            return
        try:
            total = usage.total_tokens
        except TypeError:
            return
        if isinstance(total, int) and not isinstance(total, bool) and total > 0:
            self._tokens += total

    def _seconds(self) -> float:
        running = 0.0
        if self._task_started is not None:
            running = max(0.0, self._clock() - self._task_started)
        return self._elapsed + running

    def reached(self) -> LimitReached | None:
        """Return the first limit reached (turns, time, tokens) or ``None``."""
        limits = self._limits
        if self._turns >= limits.max_turns:
            return LimitReached(LimitKind.TURNS, self._turns, limits.max_turns)
        seconds = self._seconds()
        if seconds >= limits.max_seconds:
            return LimitReached(LimitKind.TIME, int(seconds), limits.max_seconds)
        if self._tokens >= limits.max_tokens:
            return LimitReached(LimitKind.TOKENS, self._tokens, limits.max_tokens)
        return None
