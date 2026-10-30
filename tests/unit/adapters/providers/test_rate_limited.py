"""``RateLimited``: the rate-limit subtype of ``QuotaExceeded`` (HU-07-04 / FR-002)."""

from __future__ import annotations

import math

import pytest

from harness_agent.adapters.providers.errors import RateLimited
from harness_agent.core import ProviderError, QuotaExceeded

SENTINEL = "VALOR-DE-PRUEBA-123"


def test_is_a_quota_exceeded_so_existing_handlers_still_catch_it() -> None:
    error = RateLimited("límite de tasa")
    assert isinstance(error, QuotaExceeded)
    assert isinstance(error, ProviderError)


def test_retry_after_defaults_to_none() -> None:
    assert RateLimited("x").retry_after is None


@pytest.mark.parametrize("hint", [0, 0.0, 1, 2.5, 60])
def test_valid_hint_is_kept(hint: float) -> None:
    assert RateLimited("x", retry_after=hint).retry_after == hint


@pytest.mark.parametrize(
    "hint", [-1, -0.1, math.inf, -math.inf, math.nan, True, False, "5", None, [3], b"3"]
)
def test_invalid_hint_is_ignored(hint: object) -> None:
    assert RateLimited("x", retry_after=hint).retry_after is None  # type: ignore[arg-type]


def test_the_message_is_the_one_given_and_the_hint_is_not_added_to_it() -> None:
    error = RateLimited(f"texto fijo {SENTINEL}", retry_after=3)
    assert str(error) == f"texto fijo {SENTINEL}"
