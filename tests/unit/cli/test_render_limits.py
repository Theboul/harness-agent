"""Render of ``LIMIT_REACHED``: the reason and the maximum, never the raw payload (HU-01-06)."""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.cli.render import LIMIT_GUIDE, render_event
from harness_agent.core import Event, EventType

SENTINEL = "VALOR-DE-PRUEBA-123"
GENERIC = "[x] Límite: Se alcanzó un límite de la sesión. Sugerencia: " + LIMIT_GUIDE.suggestion


def make(**payload: Any) -> Event:
    return Event.create("session-1", EventType.LIMIT_REACHED, dict(payload))


@pytest.mark.parametrize(
    ("limit", "cause"),
    [
        ("turns", "Se alcanzó el máximo de 3 turnos de la sesión."),
        ("time", "Se alcanzó el tiempo máximo de 3 segundos de la sesión."),
        ("tokens", "Se alcanzó el presupuesto de 3 tokens de la sesión."),
    ],
)
def test_each_limit_is_named_with_its_maximum(limit: str, cause: str) -> None:
    line = render_event(make(limit=limit, used=9, maximum=3))

    suggestion = "Ajusta [limits] en la configuración y empieza una sesión nueva."
    assert line == f"[x] Límite: {cause} Sugerencia: {suggestion}"


def test_the_line_is_a_single_line_without_the_raw_payload() -> None:
    line = render_event(make(limit="turns", used=7, maximum=3))

    assert line is not None and "\n" not in line
    assert "limit=" not in line and "{" not in line


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"limit": "turns"},
        {"limit": "turns", "maximum": "3"},
        {"limit": "turns", "maximum": True},
        {"limit": "turns", "maximum": 0},
        {"limit": "turns", "maximum": -4},
        {"limit": "money", "maximum": 3},
        {"limit": SENTINEL, "maximum": 3},
        {"limit": None, "maximum": None},
        {"limit": ["turns"], "maximum": [3]},
    ],
)
def test_an_unknown_or_incomplete_payload_keeps_the_generic_line(payload: dict[str, Any]) -> None:
    line = render_event(make(**payload))

    assert line == GENERIC
    assert SENTINEL not in (line or "")
