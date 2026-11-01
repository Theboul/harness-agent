"""The retry of the provider has its own line (HU-06-02 / UX-c)."""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.cli import render_event
from harness_agent.core import Event, EventType


def retry(**payload: Any) -> Event:
    base: dict[str, Any] = {
        "reason": "retry",
        "error_type": "RateLimited",
        "attempt": 1,
        "max_attempts": 5,
        "delay_seconds": 2.0,
    }
    return Event(
        id="e1", session_id="s1", type=EventType.PROVIDER_ERROR, payload={**base, **payload}
    )


def test_a_retry_shows_the_attempt_and_the_wait() -> None:
    assert render_event(retry()) == "  [~] Reintentando (1 de 5) en 2 s..."


@pytest.mark.parametrize(
    ("delay", "shown"),
    [(0, "0 s"), (0.5, "0,5 s"), (2.25, "2,2 s"), (30.0, "30 s"), (1.0, "1 s")],
)
def test_the_wait_is_short_and_in_spanish_format(delay: float, shown: str) -> None:
    assert render_event(retry(delay_seconds=delay)) == f"  [~] Reintentando (1 de 5) en {shown}..."


def test_the_error_type_is_not_shown() -> None:
    line = render_event(retry(error_type="VALOR-DE-PRUEBA-123"))

    assert line is not None and "VALOR-DE-PRUEBA-123" not in line and "Error" not in line


COUNT = "  [~] Reintentando (1 de 5) en 2 s..."


@pytest.mark.parametrize(
    "payload",
    [
        {"attempt": "1"},
        {"attempt": True},
        {"attempt": 0},
        {"attempt": 6},
        {"max_attempts": None},
        {"max_attempts": 0},
    ],
)
def test_an_invalid_count_is_left_out_and_not_invented(payload: dict[str, Any]) -> None:
    assert render_event(retry(**payload)) == "  [~] Reintentando en 2 s..."


@pytest.mark.parametrize("delay", ["2", -1, float("nan"), float("inf"), True, None])
def test_an_invalid_wait_is_left_out_and_not_invented(delay: Any) -> None:
    assert render_event(retry(delay_seconds=delay)) == "  [~] Reintentando (1 de 5)..."


def test_a_retry_without_any_field_is_still_a_retry() -> None:
    event = Event(
        id="e1",
        session_id="s1",
        type=EventType.PROVIDER_ERROR,
        payload={"reason": "retry"},
    )

    assert render_event(event) == "  [~] Reintentando..."


def test_the_other_provider_errors_keep_their_lines() -> None:
    event = Event(
        id="e1",
        session_id="s1",
        type=EventType.PROVIDER_ERROR,
        payload={"reason": "provider_exception", "error_type": "RateLimited", "message": "x"},
    )

    line = render_event(event)

    assert line is not None and line.startswith("[x] Error:")
