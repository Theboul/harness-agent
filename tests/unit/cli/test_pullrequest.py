"""ConsolePullRequestPrompter: one confirmation per outgoing action (HU-11-06)."""

from __future__ import annotations

import io

import pytest

from harness_agent.cli import ConsolePullRequestPrompter
from harness_agent.core import PullRequestDraft, PullRequestPrompter

DRAFT = PullRequestDraft("TAREA-1: Validar", "## Objetivo\nValidar\n\n- [x] ok", "feature/x")


def make(typed: str, attempts: int = 3) -> tuple[ConsolePullRequestPrompter, io.StringIO]:
    output = io.StringIO()
    return ConsolePullRequestPrompter(io.StringIO(typed), output, max_attempts=attempts), output


def test_it_implements_the_port() -> None:
    prompter: PullRequestPrompter = make("")[0]
    assert prompter is not None


@pytest.mark.parametrize(("typed", "expected"), [("1\n", True), ("2\n", False), (" 1 \n", True)])
async def test_push_answers(typed: str, expected: bool) -> None:
    prompter, output = make(typed)
    assert await prompter.confirm_push("feature/x") is expected
    assert "feature/x" in output.getvalue() and "origin" in output.getvalue()


@pytest.mark.parametrize(("typed", "expected"), [("1\n", True), ("2\n", False)])
async def test_create_answers_and_shows_the_draft(typed: str, expected: bool) -> None:
    prompter, output = make(typed)
    assert await prompter.confirm_create(DRAFT) is expected
    shown = output.getvalue()
    assert "TAREA-1: Validar" in shown and "- [x] ok" in shown and "feature/x" in shown


@pytest.mark.parametrize("typed", ["", "/salir\n", "x\ny\nz\n1\n", "si\n"])
async def test_everything_but_a_clear_yes_is_no(typed: str) -> None:
    prompter, output = make(typed)
    assert await prompter.confirm_push("feature/x") is False
    assert "x\ny" not in output.getvalue()


async def test_invalid_answers_are_not_echoed_and_the_next_one_counts() -> None:
    prompter, output = make("VALOR-RARO\n1\n")
    assert await prompter.confirm_push("feature/x") is True
    assert "VALOR-RARO" not in output.getvalue()
    assert "Opción no válida" in output.getvalue()


def test_at_least_one_attempt() -> None:
    with pytest.raises(ValueError):
        ConsolePullRequestPrompter(io.StringIO(""), io.StringIO(), max_attempts=0)


def test_show_cleans_terminal_sequences() -> None:
    prompter, output = make("")
    prompter.show(["linea\x1b[31m roja", "otra"])
    assert "\x1b" not in output.getvalue()
    assert "otra" in output.getvalue()


async def test_the_draft_is_cleaned_before_it_is_shown() -> None:
    prompter, output = make("2\n")
    odd = PullRequestDraft("t\x1b[31m", "b\x07", "feature/x")
    await prompter.confirm_create(odd)
    assert "\x1b" not in output.getvalue() and "\x07" not in output.getvalue()
