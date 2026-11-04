"""The pure rule of the failover: which errors switch and what a turn has already tried (HU-07-05).

Nothing here touches a provider, a bus or a clock: the rule is a table and a small set.
"""

from __future__ import annotations

import asyncio

import pytest

from harness_agent.core import (
    ELIGIBLE_ERRORS,
    FailoverTurn,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    is_failover_eligible,
)

SENTINEL = "VALOR-DE-PRUEBA-123"


class _LimitedByRate(QuotaExceeded):
    """A subtype of the quota error, as the adapters define them."""


class _Exhausted(ProviderError):
    """A stand-in for the error of an exhausted list: a subtype of ``ProviderError`` only."""


@pytest.mark.parametrize(
    "error",
    [
        QuotaExceeded(SENTINEL),
        _LimitedByRate(SENTINEL),
        ProviderTimeout(SENTINEL),
        ProviderUnavailable(SENTINEL),
    ],
)
def test_the_four_transient_kinds_are_eligible(error: BaseException) -> None:
    assert is_failover_eligible(error) is True


@pytest.mark.parametrize(
    "error",
    [
        ProviderError(SENTINEL),
        _Exhausted(SENTINEL),
        ValueError(SENTINEL),
        RuntimeError(SENTINEL),
        asyncio.CancelledError(),
        KeyboardInterrupt(),
    ],
)
def test_everything_else_is_not_eligible(error: BaseException) -> None:
    assert is_failover_eligible(error) is False


def test_an_object_that_is_not_an_exception_is_not_eligible() -> None:
    assert is_failover_eligible(SENTINEL) is False
    assert is_failover_eligible(None) is False
    assert is_failover_eligible(QuotaExceeded) is False  # the class, not an instance


def test_the_table_lists_exactly_the_eligible_kinds() -> None:
    assert set(ELIGIBLE_ERRORS) == {QuotaExceeded, ProviderTimeout, ProviderUnavailable}


class TestFailoverTurn:
    def test_the_first_untried_in_the_order_of_the_list_comes_first(self) -> None:
        turn = FailoverTurn(("a", "b", "c"))

        assert turn.next_untried() == "a"
        turn.mark("a")
        assert turn.next_untried() == "b"
        turn.mark("b")
        assert turn.next_untried() == "c"

    def test_the_order_is_the_one_of_the_list_not_the_one_of_the_marks(self) -> None:
        turn = FailoverTurn(("a", "b", "c"))
        turn.mark("c")

        assert turn.next_untried() == "a"
        turn.mark("a")
        assert turn.next_untried() == "b"

    def test_a_list_with_everything_tried_gives_none(self) -> None:
        turn = FailoverTurn(("a", "b"))
        turn.mark("a")
        turn.mark("b")

        assert turn.next_untried() is None

    def test_an_empty_list_gives_none(self) -> None:
        assert FailoverTurn(()).next_untried() is None

    def test_marking_twice_is_the_same_as_marking_once(self) -> None:
        turn = FailoverTurn(("a", "b"))
        turn.mark("a")
        turn.mark("a")

        assert turn.next_untried() == "b"
        assert turn.tried == frozenset({"a"})

    def test_a_key_that_is_not_in_the_list_can_be_marked_without_effect(self) -> None:
        turn = FailoverTurn(("a", "b"))
        turn.mark("fuera")

        assert turn.next_untried() == "a"
        assert turn.has_tried("fuera") is True
        assert turn.has_tried("a") is False

    def test_begin_forgets_everything_that_was_tried(self) -> None:
        turn = FailoverTurn(("a", "b"))
        turn.mark("a")
        turn.mark("b")

        turn.begin()

        assert turn.tried == frozenset()
        assert turn.next_untried() == "a"

    def test_the_list_is_copied_so_a_later_change_does_not_alter_the_turn(self) -> None:
        chain = ["a", "b"]
        turn = FailoverTurn(chain)
        chain.append("c")

        assert turn.chain == ("a", "b")
