"""ContextSettings and the threshold per model (HU-02-03, contracts/context_settings.md)."""

from __future__ import annotations

import dataclasses

import pytest

from harness_agent.core import (
    ContextConfigError,
    ContextSettings,
    recent_budget_tokens,
    summary_cap_tokens,
    threshold_tokens,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
GPT = "openai/gpt-4o"


@pytest.mark.parametrize(
    ("settings", "model", "window", "threshold", "recent"),
    [
        (ContextSettings(), "fake/test", 32_000, 25_600, 7_680),
        (ContextSettings(windows=((GPT, 128_000),)), GPT, 128_000, 102_400, 30_720),
        (ContextSettings(windows=((GPT, 128_000),)), "fake/test", 32_000, 25_600, 7_680),
        (ContextSettings(window_tokens=10_000, threshold_percent=50), "x/y", 10_000, 5_000, 1_500),
    ],
)
def test_the_table_of_the_contract(
    settings: ContextSettings, model: str, window: int, threshold: int, recent: int
) -> None:
    assert settings.window_for(model) == window
    assert threshold_tokens(settings, model) == threshold
    assert recent_budget_tokens(settings, model) == recent


def test_the_defaults_are_the_ones_of_the_clarification() -> None:
    settings = ContextSettings()

    assert (settings.window_tokens, settings.windows) == (32_000, ())
    assert (settings.threshold_percent, settings.recent_percent) == (80, 30)
    assert (settings.min_recent_messages, settings.summary_tokens) == (4, 2_000)
    assert summary_cap_tokens(settings) == 4_000


def test_the_window_depends_on_the_model_in_use() -> None:
    settings = ContextSettings(windows=((GPT, 128_000), ("a/b", 8_000)))

    assert [threshold_tokens(settings, m) for m in (GPT, "a/b", "c/d")] == [102_400, 6_400, 25_600]
    assert settings.window_for(5) == 32_000  # type: ignore[arg-type]


def test_it_is_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        ContextSettings().window_tokens = 5  # type: ignore[misc]


@pytest.mark.parametrize(
    "fields",
    [
        {"window_tokens": 999},
        {"window_tokens": 10_000_001},
        {"window_tokens": True},
        {"window_tokens": "32000"},
        {"threshold_percent": 9},
        {"threshold_percent": 96},
        {"recent_percent": 4},
        {"recent_percent": 61},
        {"min_recent_messages": 0},
        {"min_recent_messages": 51},
        {"summary_tokens": 99},
        {"summary_tokens": 8_001},
        {"summary_tokens": 2.5},
        {"windows": (("", 8_000),)},
        {"windows": ((GPT, 999),)},
        {"windows": ((GPT, True),)},
        {"windows": ((GPT, "8000"),)},
        {"windows": ((5, 8_000),)},
        {"windows": ("no es una tupla",)},
        {"windows": 7},
    ],
)
def test_an_invalid_value_is_refused_without_repeating_it(fields: dict[str, object]) -> None:
    with pytest.raises(ContextConfigError) as raised:
        ContextSettings(**fields)  # type: ignore[arg-type]

    message = str(raised.value)
    assert message.startswith("La configuración de contexto no es válida: ")
    assert message.endswith(".")
    assert next(iter(fields)) in message


def test_the_message_never_repeats_the_value_or_the_model() -> None:
    with pytest.raises(ContextConfigError) as raised:
        ContextSettings(windows=((SENTINEL, 5),))
    with pytest.raises(ContextConfigError) as other:
        ContextSettings(summary_tokens=SENTINEL)  # type: ignore[arg-type]

    assert SENTINEL not in str(raised.value) and SENTINEL not in str(other.value)
