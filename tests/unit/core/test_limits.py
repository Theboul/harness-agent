"""Unit tests for the session limits (HU-01-06): validation and tracker rules."""

from __future__ import annotations

import pytest

from harness_agent.core.entities import TokenUsage
from harness_agent.core.limits import (
    InvalidLimitsError,
    LimitKind,
    LimitReached,
    LimitTracker,
    SessionLimits,
)

SENTINEL = "VALOR-DE-PRUEBA-123"


class TestSessionLimitsValidation:
    def test_valid_limits_are_kept(self) -> None:
        limits = SessionLimits(max_turns=3, max_seconds=10, max_tokens=500)
        assert (limits.max_turns, limits.max_seconds, limits.max_tokens) == (3, 10, 500)

    @pytest.mark.parametrize("field", ["max_turns", "max_seconds", "max_tokens"])
    @pytest.mark.parametrize("bad", [0, -1, True, 1.5, "3", None])
    def test_a_non_positive_or_non_integer_value_fails_closed(
        self, field: str, bad: object
    ) -> None:
        values: dict[str, object] = {"max_turns": 1, "max_seconds": 1, "max_tokens": 1}
        values[field] = bad
        with pytest.raises(InvalidLimitsError) as error:
            SessionLimits(**values)  # type: ignore[arg-type]
        assert field in str(error.value)

    def test_the_message_never_reproduces_the_received_value(self) -> None:
        with pytest.raises(InvalidLimitsError) as error:
            SessionLimits(max_turns=SENTINEL, max_seconds=1, max_tokens=1)  # type: ignore[arg-type]
        assert SENTINEL not in str(error.value)

    def test_the_error_is_a_value_error(self) -> None:
        assert issubclass(InvalidLimitsError, ValueError)

    def test_limit_kinds_are_the_event_payload_keys(self) -> None:
        assert [kind.value for kind in LimitKind] == ["turns", "time", "tokens"]


class FakeClock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def make_tracker(
    max_turns: int = 3, max_seconds: int = 10, max_tokens: int = 100
) -> tuple[LimitTracker, FakeClock]:
    clock = FakeClock()
    return LimitTracker(SessionLimits(max_turns, max_seconds, max_tokens), clock), clock


class TestTurns:
    def test_nothing_is_reached_at_the_start(self) -> None:
        tracker, _ = make_tracker()
        assert tracker.reached() is None

    def test_the_limit_is_reached_with_greater_or_equal(self) -> None:
        tracker, _ = make_tracker(max_turns=2)
        tracker.start_turn()
        assert tracker.reached() is None
        tracker.start_turn()
        assert tracker.reached() == LimitReached(LimitKind.TURNS, 2, 2)

    def test_a_reached_limit_stays_reached(self) -> None:
        tracker, _ = make_tracker(max_turns=1)
        tracker.start_turn()
        assert tracker.reached() is not None
        assert tracker.reached() is not None


class TestTokens:
    def test_usage_is_added_and_the_budget_is_reached_with_greater_or_equal(self) -> None:
        tracker, _ = make_tracker(max_tokens=100)
        tracker.add_usage(TokenUsage(input_tokens=60, output_tokens=30))
        assert tracker.reached() is None
        tracker.add_usage(TokenUsage(input_tokens=5, output_tokens=5))
        assert tracker.reached() == LimitReached(LimitKind.TOKENS, 100, 100)

    def test_one_call_may_overshoot_the_budget(self) -> None:
        tracker, _ = make_tracker(max_tokens=100)
        tracker.add_usage(TokenUsage(input_tokens=500, output_tokens=0))
        assert tracker.reached() == LimitReached(LimitKind.TOKENS, 500, 100)

    def test_missing_or_invalid_usage_counts_as_zero(self) -> None:
        tracker, _ = make_tracker(max_tokens=1)
        tracker.add_usage(None)
        tracker.add_usage(TokenUsage(input_tokens=-5, output_tokens=2))
        tracker.add_usage(TokenUsage(input_tokens="x", output_tokens=0))  # type: ignore[arg-type]
        tracker.add_usage(TokenUsage(input_tokens=1.5, output_tokens=0))  # type: ignore[arg-type]
        assert tracker.reached() is None


class TestTime:
    def test_the_running_task_counts(self) -> None:
        tracker, clock = make_tracker(max_seconds=10)
        tracker.begin_task()
        clock.now += 9.9
        assert tracker.reached() is None
        clock.now += 0.1
        assert tracker.reached() == LimitReached(LimitKind.TIME, 10, 10)

    def test_the_wait_between_tasks_is_not_counted(self) -> None:
        tracker, clock = make_tracker(max_seconds=10)
        tracker.begin_task()
        clock.now += 4
        tracker.end_task()
        clock.now += 1000
        assert tracker.reached() is None
        tracker.begin_task()
        clock.now += 5
        assert tracker.reached() is None
        clock.now += 1
        tracker.end_task()
        assert tracker.reached() is not None

    def test_end_task_is_idempotent_and_safe_without_a_task(self) -> None:
        tracker, clock = make_tracker(max_seconds=10)
        tracker.end_task()
        tracker.begin_task()
        tracker.begin_task()
        clock.now += 3
        tracker.end_task()
        tracker.end_task()
        clock.now += 50
        assert tracker.reached() is None

    def test_a_clock_that_goes_back_never_reduces_the_time(self) -> None:
        tracker, clock = make_tracker(max_seconds=10)
        tracker.begin_task()
        clock.now -= 50
        assert tracker.reached() is None
        tracker.end_task()
        assert tracker.reached() is None

    def test_the_default_clock_is_monotonic(self) -> None:
        tracker = LimitTracker(SessionLimits(1, 1000, 1))
        tracker.begin_task()
        tracker.end_task()
        assert tracker.reached() is None


class TestOrder:
    def test_turns_come_before_time_and_time_before_tokens(self) -> None:
        tracker, clock = make_tracker(max_turns=1, max_seconds=1, max_tokens=1)
        tracker.begin_task()
        clock.now += 5
        tracker.add_usage(TokenUsage(input_tokens=5, output_tokens=0))
        reached = tracker.reached()
        assert reached is not None and reached.kind is LimitKind.TIME
        tracker.start_turn()
        reached = tracker.reached()
        assert reached is not None and reached.kind is LimitKind.TURNS
