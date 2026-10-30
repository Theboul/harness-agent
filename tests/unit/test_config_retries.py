"""The optional ``[retries]`` section of ``config.toml`` (HU-07-04 / FR-012).

An additive extension of the HU-00-04 schema: without the section the defaults apply, a value
that is not valid stops the start and the message never repeats what was received.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import ConfigProblem, InvalidConfigError, Retries, load_config
from tests.unit.config_support import SENTINEL, write_config

BASE = 'model = "fake/test"\n'
UNKNOWN = "campo desconocido en el esquema."
ATTEMPTS = "debe ser un entero entre 1 y 10."
BASE_DELAY = "debe ser un número de segundos mayor que 0."
MAX_DELAY = "debe ser un número de segundos entre base_delay y 600."


def retries_of(tmp_path: Path, text: str) -> Retries:
    return load_config(write_config(tmp_path, BASE + text), environ={}).retries


def problems_of(tmp_path: Path, text: str) -> tuple[ConfigProblem, ...]:
    with pytest.raises(InvalidConfigError) as raised:
        load_config(write_config(tmp_path, BASE + text), environ={})
    return raised.value.problems


def test_without_the_section_the_defaults_apply(tmp_path: Path) -> None:
    assert retries_of(tmp_path, "") == Retries(max_attempts=5, base_delay=2.0, max_delay=30.0)
    assert retries_of(tmp_path, "[retries]\n") == Retries()


def test_a_complete_section_is_read_and_integers_are_accepted_as_seconds(tmp_path: Path) -> None:
    text = "[retries]\nmax_attempts = 3\nbase_delay = 1\nmax_delay = 20.5\n"

    assert retries_of(tmp_path, text) == Retries(max_attempts=3, base_delay=1.0, max_delay=20.5)


def test_one_attempt_turns_the_retries_off(tmp_path: Path) -> None:
    assert retries_of(tmp_path, "[retries]\nmax_attempts = 1\n").max_attempts == 1


def test_a_base_above_the_default_cap_raises_the_cap_with_it(tmp_path: Path) -> None:
    settings = retries_of(tmp_path, "[retries]\nbase_delay = 40\n")

    assert (settings.base_delay, settings.max_delay) == (40.0, 40.0)


@pytest.mark.parametrize("value", ["0", "-1", "11", "true", '"3"', "2.5", "[3]"])
def test_an_invalid_max_attempts_is_a_problem(tmp_path: Path, value: str) -> None:
    problems = problems_of(tmp_path, f"[retries]\nmax_attempts = {value}\n")

    assert problems == (ConfigProblem("retries.max_attempts", ATTEMPTS),)


@pytest.mark.parametrize("value", ["0", "-1", "0.0", "true", '"2"', "inf", "nan"])
def test_an_invalid_base_delay_is_a_problem(tmp_path: Path, value: str) -> None:
    problems = problems_of(tmp_path, f"[retries]\nbase_delay = {value}\n")

    assert problems == (ConfigProblem("retries.base_delay", BASE_DELAY),)


@pytest.mark.parametrize("value", ["0", "-5", "601", "true", '"30"', "inf", "nan"])
def test_an_invalid_max_delay_is_a_problem(tmp_path: Path, value: str) -> None:
    problems = problems_of(tmp_path, f"[retries]\nmax_delay = {value}\n")

    assert problems == (ConfigProblem("retries.max_delay", MAX_DELAY),)


def test_a_cap_below_the_base_is_a_problem_on_the_cap(tmp_path: Path) -> None:
    problems = problems_of(tmp_path, "[retries]\nbase_delay = 10\nmax_delay = 5\n")

    assert problems == (ConfigProblem("retries.max_delay", MAX_DELAY),)


def test_messages_never_repeat_the_value_received(tmp_path: Path) -> None:
    text = f'[retries]\nmax_attempts = "{SENTINEL}"\nbase_delay = 123456\nmax_delay = 700\n'

    problems = problems_of(tmp_path, text)

    shown = " ".join(p.message for p in problems)
    assert SENTINEL not in shown and "123456" not in shown and "700" not in shown
    assert [p.field for p in problems] == ["retries.max_attempts", "retries.max_delay"]


def test_retries_that_is_not_a_table_is_a_problem(tmp_path: Path) -> None:
    assert problems_of(tmp_path, "retries = 3\n") == (
        ConfigProblem("retries", "debe ser una tabla."),
    )


def test_an_unknown_field_of_the_section_is_refused(tmp_path: Path) -> None:
    assert problems_of(tmp_path, "[retries]\notra = 1\n") == (
        ConfigProblem("retries.otra", UNKNOWN),
    )


def test_the_example_template_documents_the_section() -> None:
    template = (Path(__file__).resolve().parents[2] / "config.example.toml").read_text(
        encoding="utf-8"
    )

    assert "[retries]" in template
    for field in ("max_attempts", "base_delay", "max_delay"):
        assert field in template
