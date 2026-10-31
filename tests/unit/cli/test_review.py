"""ConsoleReviewer: shows the review and reads the decision of the person (HU-11-05)."""

from __future__ import annotations

import io

import pytest

from harness_agent.cli import ConsoleReviewer
from harness_agent.core import (
    ChangeReviewer,
    ChangeSet,
    ChangeStatus,
    Choice,
    FileChange,
    ReviewDecision,
    ReviewView,
    TaskCriteriaItem,
    build_view,
)

CHANGES = ChangeSet((FileChange("a.py", ChangeStatus.NEW, 2, 0),), "+uno\n+dos\n")


def make_view(*pending: bool) -> ReviewView:
    items = [TaskCriteriaItem("c0", "pruebas", True, None, "pytest")]
    items += [
        TaskCriteriaItem(f"c{i}", f"semántico {i}", False, None, None)
        for i, _ in enumerate(pending, 1)
    ]
    return build_view("T-1", CHANGES, items)


async def ask(
    typed: str, view: ReviewView | None = None, attempts: int = 3
) -> tuple[ReviewDecision, str]:
    output = io.StringIO()
    reviewer = ConsoleReviewer(io.StringIO(typed), output, max_attempts=attempts)
    decision = await reviewer.choose(view or make_view(True))
    return decision, output.getvalue()


def test_it_is_a_change_reviewer() -> None:
    reviewer: ChangeReviewer = ConsoleReviewer(io.StringIO(), io.StringIO())

    assert reviewer is not None


async def test_it_shows_the_summary_and_the_diff_before_asking() -> None:
    _, shown = await ask("1\n")

    assert shown.index("REVISIÓN DE CAMBIOS") < shown.index("+uno") < shown.index("opción>")


async def test_one_approves() -> None:
    decision, _ = await ask("1\n", make_view())

    assert decision == ReviewDecision(Choice.APPROVE)


async def test_three_rejects_with_a_cleaned_reason_that_is_not_echoed() -> None:
    decision, shown = await ask('3\nfalta el "caso" vacío\n')

    assert decision.choice is Choice.REJECT
    assert decision.reason == "falta el ’caso’ vacío"
    assert "falta el" not in shown


@pytest.mark.parametrize("typed", ["3\n\n", "3\n", "3\n/salir\n"])
async def test_a_rejection_may_have_no_reason(typed: str) -> None:
    decision, _ = await ask(typed)

    assert decision == ReviewDecision(Choice.REJECT)


async def test_two_shows_the_whole_diff_and_keeps_asking() -> None:
    decision, shown = await ask("2\n1\n", make_view())

    assert decision.choice is Choice.APPROVE
    assert shown.count("+dos") == 2  # in the preview and in the full diff


async def test_four_and_five_take_a_criterion_number() -> None:
    confirm, _ = await ask("4 2\n", make_view(True, True))
    reject, _ = await ask("5 2\nno se entiende\n", make_view(True, True))

    assert confirm == ReviewDecision(Choice.CONFIRM, 2)
    assert reject == ReviewDecision(Choice.REJECT_CRITERION, 2, "no se entiende")


async def test_a_bare_four_works_when_one_criterion_waits() -> None:
    decision, _ = await ask("4\n")

    assert decision == ReviewDecision(Choice.CONFIRM, 2)


async def test_a_bare_four_with_several_waiting_asks_for_the_number() -> None:
    decision, shown = await ask("4\n/salir\n", make_view(True, True))

    assert decision.choice is Choice.NONE
    assert "Indica el número del criterio" in shown


@pytest.mark.parametrize("typed", ["4 x\n", "4 -1\n", "4 99999999\n", "4 ٣\n"])
async def test_a_bad_number_is_invalid(typed: str) -> None:
    decision, shown = await ask(typed + "/salir\n", make_view(True))

    assert decision.choice is Choice.NONE
    assert "Opción no válida" in shown


@pytest.mark.parametrize("typed", ["", "/salir\n", "  /salir  \n"])
async def test_the_end_of_the_input_or_exit_is_no_decision(typed: str) -> None:
    decision, _ = await ask(typed)

    assert decision == ReviewDecision(Choice.NONE)


async def test_invalid_options_are_not_echoed_and_run_out_of_attempts() -> None:
    decision, shown = await ask("VALOR-DE-PRUEBA-123\nquiza\n11\n1\n", attempts=3)

    assert decision.choice is Choice.NONE
    assert shown.count("Opción no válida") == 3 and "VALOR-DE-PRUEBA-123" not in shown


async def test_the_second_time_the_same_diff_is_not_repeated() -> None:
    output = io.StringIO()
    reviewer = ConsoleReviewer(io.StringIO("4\n1\n"), output)
    view = make_view(True)

    await reviewer.choose(view)
    await reviewer.choose(make_view())

    assert output.getvalue().count("-- diff --") == 1
    assert output.getvalue().count("== REVISIÓN") == 2


def test_inform_writes_one_clean_line() -> None:
    output = io.StringIO()
    reviewer = ConsoleReviewer(io.StringIO(), output)

    reviewer.inform("Commit hecho: abc\x1b[31m\nfin")

    assert output.getvalue() == "Commit hecho: abc[31m fin\n"


def test_it_needs_at_least_one_attempt() -> None:
    with pytest.raises(ValueError):
        ConsoleReviewer(io.StringIO(), io.StringIO(), max_attempts=0)


async def test_the_defaults_are_the_standard_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    out = io.StringIO()
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))
    monkeypatch.setattr("sys.stdout", out)

    decision = await ConsoleReviewer().choose(make_view())

    assert decision.choice is Choice.APPROVE and "REVISIÓN" in out.getvalue()
