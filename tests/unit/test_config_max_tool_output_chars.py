"""``limits.max_tool_output_chars``: the longest result of a tool (HU-02-02 / FR-009, FR-010).

An additive extension of the HU-00-04 schema, in the same way as ``limits.max_output_tokens``
(HU-07-02). It is unrelated to the tokens of the model: it bounds the text a tool returns.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import ConfigProblem, InvalidConfigError, Limits, load_config
from harness_agent.core import DEFAULT_MAX_OUTPUT_CHARS, MIN_MAX_OUTPUT_CHARS
from tests.unit.config_support import SENTINEL, write_config

TOO_SMALL = "debe ser un entero de al menos 256."
FIELD = "limits.max_tool_output_chars"


def limits_of(tmp_path: Path, text: str) -> Limits:
    return load_config(write_config(tmp_path, text), environ={}).limits


def problems_of(tmp_path: Path, text: str) -> tuple[ConfigProblem, ...]:
    with pytest.raises(InvalidConfigError) as raised:
        load_config(write_config(tmp_path, text), environ={})
    return raised.value.problems


class TestTheDefault:
    def test_the_default_is_the_one_of_the_core(self) -> None:
        assert Limits().max_tool_output_chars == DEFAULT_MAX_OUTPUT_CHARS == 24000

    def test_a_file_without_the_field_takes_the_default(self, tmp_path: Path) -> None:
        limits = limits_of(tmp_path, 'model = "fake/test"\n')

        assert limits.max_tool_output_chars == 24000

    def test_the_other_limits_keep_their_defaults(self, tmp_path: Path) -> None:
        limits = limits_of(tmp_path, 'model = "fake/test"\n')

        assert (limits.max_turns, limits.max_seconds, limits.max_tokens) == (30, 600, 200000)
        assert limits.max_output_tokens == 4096


class TestAConfiguredValue:
    @pytest.mark.parametrize("value", [MIN_MAX_OUTPUT_CHARS, 12000, 500000])
    def test_it_is_read_from_the_limits_table(self, tmp_path: Path, value: int) -> None:
        text = f'model = "fake/test"\n[limits]\nmax_tool_output_chars = {value}\n'

        assert limits_of(tmp_path, text).max_tool_output_chars == value

    def test_it_does_not_change_the_other_limits(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\n[limits]\nmax_tokens = 5000\nmax_tool_output_chars = 900\n'

        limits = limits_of(tmp_path, text)

        assert (limits.max_tokens, limits.max_tool_output_chars) == (5000, 900)
        assert limits.max_output_tokens == 4096


class TestAnInvalidValue:
    @pytest.mark.parametrize(
        "value",
        ["true", "false", "0", "-1", "255", "12.5", f'"{SENTINEL}"', '"1000"', "[300]"],
    )
    def test_it_is_rejected_with_a_message_that_hides_the_value(
        self, tmp_path: Path, value: str
    ) -> None:
        text = f'model = "fake/test"\n[limits]\nmax_tool_output_chars = {value}\n'

        problems = problems_of(tmp_path, text)

        assert problems == (ConfigProblem(FIELD, TOO_SMALL),)
        assert SENTINEL not in str(problems)

    def test_it_is_reported_together_with_the_other_problems(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\n[limits]\nmax_turns = 0\nmax_tool_output_chars = 10\n'

        problems = problems_of(tmp_path, text)

        assert ConfigProblem("limits.max_turns", "debe ser un entero mayor que 0.") in problems
        assert ConfigProblem(FIELD, TOO_SMALL) in problems
        assert len(problems) == 2
