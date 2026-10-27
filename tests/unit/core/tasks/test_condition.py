"""The expected condition of a criterion: grammar, evaluation and examples (HU-11-04.1)."""

from __future__ import annotations

import pytest

from harness_agent.core import MAX_EXIT_CODE, Condition, condition_met, parse_condition

SENTINEL = "VALOR-DE-PRUEBA-123"

PARSED = [
    ("codigo_salida == 0", Condition("==", 0)),
    ("codigo_salida==0", Condition("==", 0)),
    ("  codigo_salida != 1  ", Condition("!=", 1)),
    ("codigo_salida == 4294967295", Condition("==", 4294967295)),
    ("codigo_salida\t!=\t7", Condition("!=", 7)),
    ("codigo_salida == 007", Condition("==", 7)),
]

REJECTED = [
    "salida 0",
    "ok",
    "codigo_salida >= 0",
    "codigo_salida == -1",
    "CODIGO_SALIDA == 0",
    "codigo_salida = 0",
    "codigo_salida == 4294967296",
    "codigo_salida ==",
    "codigo_salida == 0 y ok",
    "",
    "   ",
    "codigo_salida == 12345678901",
    "codigo_salida == 0\ncodigo_salida == 1",
    "codigo_salida == 1.5",
]

MET = [
    (Condition("==", 0), 0, True),
    (Condition("==", 0), 1, False),
    (Condition("==", 0), None, False),
    (Condition("!=", 0), 1, True),
    (Condition("!=", 0), 0, False),
    (Condition("!=", 0), None, False),
    (Condition("==", 3), 3, True),
]


def test_the_maximum_is_the_one_of_the_contract() -> None:
    assert MAX_EXIT_CODE == 4_294_967_295


@pytest.mark.parametrize(("text", "expected"), PARSED)
def test_valid_conditions_are_parsed_exactly(text: str, expected: Condition) -> None:
    assert parse_condition(text) == expected


@pytest.mark.parametrize("text", REJECTED)
def test_everything_else_is_not_a_condition(text: str) -> None:
    assert parse_condition(text) is None


@pytest.mark.parametrize(
    "value", [None, 5, b"codigo_salida == 0", ["codigo_salida == 0"], object()]
)
def test_a_value_that_is_not_text_is_not_a_condition(value: object) -> None:
    assert parse_condition(value) is None


@pytest.mark.parametrize(("condition", "exit_code", "expected"), MET)
def test_the_exit_code_is_compared_as_the_contract_says(
    condition: Condition, exit_code: int | None, expected: bool
) -> None:
    assert condition_met(condition, exit_code) is expected


def test_a_negative_exit_code_never_matches_a_number_but_differs_from_it() -> None:
    assert condition_met(Condition("==", 0), -9) is False
    assert condition_met(Condition("!=", 0), -9) is True


def test_a_bad_exit_code_or_condition_is_not_met_and_never_raises() -> None:
    assert condition_met(Condition("==", 0), True) is False  # a bool is not an exit code
    assert condition_met(Condition("==", 0), "0") is False  # type: ignore[arg-type]
    assert condition_met(Condition("<", 0), 0) is False
    assert condition_met(None, 0) is False  # type: ignore[arg-type]
    assert condition_met(Condition("==", SENTINEL), 0) is False  # type: ignore[arg-type]
