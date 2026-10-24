"""``limits.max_output_tokens``: the cap of one model call (HU-07-02 / FR-009, FR-014a).

An additive extension of the HU-00-04 schema. ``limits.max_tokens`` stays the budget of the whole
run (HU-01-06) and is never used as the cap of one call.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import ConfigProblem, InvalidConfigError, Limits, load_config
from tests.unit.config_support import SENTINEL, write_config

NOT_AN_INTEGER = "debe ser un entero mayor que 0."
DEFAULT = 4096


def limits_of(tmp_path: Path, text: str) -> Limits:
    return load_config(write_config(tmp_path, text), environ={}).limits


def problems_of(tmp_path: Path, text: str) -> tuple[ConfigProblem, ...]:
    with pytest.raises(InvalidConfigError) as raised:
        load_config(write_config(tmp_path, text), environ={})
    return raised.value.problems


class TestTheDefault:
    def test_the_dataclass_default_is_4096(self) -> None:
        assert Limits().max_output_tokens == DEFAULT

    def test_a_file_without_the_field_takes_the_default(self, tmp_path: Path) -> None:
        assert limits_of(tmp_path, 'model = "fake/test"\n').max_output_tokens == DEFAULT

    def test_the_existing_limits_keep_their_defaults(self, tmp_path: Path) -> None:
        limits = limits_of(tmp_path, 'model = "fake/test"\n')

        assert limits == Limits(max_turns=30, max_seconds=600, max_tokens=200000)
        assert (limits.max_turns, limits.max_seconds, limits.max_tokens) == (30, 600, 200000)


class TestAConfiguredValue:
    def test_it_is_read_from_the_limits_table(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\n[limits]\nmax_output_tokens = 8000\n'

        assert limits_of(tmp_path, text).max_output_tokens == 8000

    def test_it_does_not_change_the_run_budget(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\n[limits]\nmax_output_tokens = 8000\n'

        assert limits_of(tmp_path, text).max_tokens == 200000

    def test_the_run_budget_does_not_change_the_cap_of_a_call(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\n[limits]\nmax_tokens = 1000\n'

        limits = limits_of(tmp_path, text)

        assert limits.max_tokens == 1000
        assert limits.max_output_tokens == DEFAULT

    def test_both_can_be_set_together(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\n[limits]\nmax_tokens = 5000\nmax_output_tokens = 512\n'

        limits = limits_of(tmp_path, text)

        assert (limits.max_tokens, limits.max_output_tokens) == (5000, 512)


class TestAnInvalidValue:
    @pytest.mark.parametrize("value", ["0", "-1", '"10"', "1.5", "true", "false", "[1]"])
    def test_it_must_be_an_integer_greater_than_zero(self, tmp_path: Path, value: str) -> None:
        text = f'model = "fake/test"\n[limits]\nmax_output_tokens = {value}\n'

        assert problems_of(tmp_path, text) == (
            ConfigProblem("limits.max_output_tokens", NOT_AN_INTEGER),
        )

    def test_the_message_never_reproduces_the_received_value(self, tmp_path: Path) -> None:
        text = f'model = "fake/test"\n[limits]\nmax_output_tokens = "{SENTINEL}"\n'

        (problem,) = problems_of(tmp_path, text)

        assert SENTINEL not in problem.message
        assert SENTINEL not in problem.field

    def test_it_is_reported_together_with_the_other_problems(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\n[limits]\nmax_turns = 0\nmax_output_tokens = 0\n'

        assert {problem.field for problem in problems_of(tmp_path, text)} == {
            "limits.max_turns",
            "limits.max_output_tokens",
        }


class TestTheSchemaStaysClosed:
    def test_an_unknown_field_in_limits_is_still_rejected(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\n[limits]\nmax_output_limit = 3\n'

        assert problems_of(tmp_path, text) == (
            ConfigProblem("limits.max_output_limit", "campo desconocido en el esquema."),
        )
