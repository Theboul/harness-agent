"""The approval block says who asks when a subagent does (HU-09-03 / T010)."""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.cli.approval_view import approval_block

LABEL = "subagente abcdefgh"
SENTINEL = "VALOR-DE-PRUEBA-123"


def details(**extra: Any) -> dict[str, Any]:
    return {
        "tool": "shell",
        "arguments": {"command": "pytest -q"},
        "effect": "Runs a command",
        "risk": "high",
        **extra,
    }


def test_a_request_from_a_subagent_shows_who_asks_right_below_the_title() -> None:
    lines = approval_block("shell", details(requested_by=LABEL))

    assert lines[2] == "-" * 60
    assert lines[3] == " Pide:        subagente abcdefgh"
    assert lines[4] == " El agente quiere ejecutar un comando:"


def test_only_that_one_line_is_added() -> None:
    plain = approval_block("shell", details())
    with_requester = approval_block("shell", details(requested_by=LABEL))

    assert [line for line in with_requester if line not in plain] == [
        " Pide:        subagente abcdefgh"
    ]
    assert len(with_requester) == len(plain) + 1


@pytest.mark.parametrize("value", [None, "", "   ", 3, ["subagente x"], b"x"])
def test_without_a_usable_requester_the_block_is_the_same_as_ever(value: object) -> None:
    assert approval_block("shell", details(requested_by=value)) == approval_block(
        "shell", details()
    )


def test_the_name_is_shown_on_one_line_clean_and_bounded() -> None:
    dirty = "subagente\x1b[31m ab\ncd\r" + "x" * 500

    lines = approval_block("shell", details(requested_by=dirty))

    shown = next(line for line in lines if line.startswith(" Pide:"))
    assert "\x1b" not in shown and "\n" not in shown and "\r" not in shown
    assert len(shown) <= len(" Pide:        ") + 64
