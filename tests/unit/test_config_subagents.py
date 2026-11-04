"""The optional ``[subagents]`` section of ``config.toml`` (HU-09-04 / FR-011).

The limits of a subagent are its own, apart from those of the orchestrator: without the section the
defaults apply, a value that is not valid stops the start and the message never repeats it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import (
    ConfigProblem,
    InvalidConfigError,
    SubagentSettings,
    load_config,
)
from tests.unit.config_support import SENTINEL, write_config

BASE = 'model = "fake/test"\n'
UNKNOWN = "campo desconocido en el esquema."
INTEGER = "debe ser un entero mayor que 0."
BOOLEAN = "debe ser true o false."


def settings_of(tmp_path: Path, text: str) -> SubagentSettings:
    return load_config(write_config(tmp_path, BASE + text), environ={}).subagents


def problems_of(tmp_path: Path, text: str) -> tuple[ConfigProblem, ...]:
    with pytest.raises(InvalidConfigError) as raised:
        load_config(write_config(tmp_path, BASE + text), environ={})
    return raised.value.problems


def test_without_the_section_the_defaults_apply(tmp_path: Path) -> None:
    expected = SubagentSettings(enabled=False, max_turns=10, max_seconds=300, max_tokens=50000)

    assert settings_of(tmp_path, "") == expected
    assert settings_of(tmp_path, "[subagents]\n") == expected


def test_the_limits_of_the_subagent_are_apart_from_those_of_the_orchestrator(
    tmp_path: Path,
) -> None:
    config = load_config(
        write_config(tmp_path, BASE + "[limits]\nmax_turns = 99\n[subagents]\nmax_turns = 3\n"),
        environ={},
    )

    assert (config.limits.max_turns, config.subagents.max_turns) == (99, 3)


def test_a_complete_section_is_read(tmp_path: Path) -> None:
    text = "[subagents]\nenabled = true\nmax_turns = 4\nmax_seconds = 60\nmax_tokens = 1000\n"

    assert settings_of(tmp_path, text) == SubagentSettings(True, 4, 60, 1000)


def test_the_delegation_is_off_unless_the_section_turns_it_on(tmp_path: Path) -> None:
    assert settings_of(tmp_path, "").enabled is False
    assert settings_of(tmp_path, "[subagents]\nmax_turns = 4\n").enabled is False
    assert settings_of(tmp_path, "[subagents]\nenabled = false\n").enabled is False
    assert settings_of(tmp_path, "[subagents]\nenabled = true\n").enabled is True


@pytest.mark.parametrize("value", ["1", "0", '"true"', "2.5", "[true]", '"si"'])
def test_an_enabled_that_is_not_a_boolean_is_a_problem(tmp_path: Path, value: str) -> None:
    problems = problems_of(tmp_path, f"[subagents]\nenabled = {value}\n")

    assert problems == (ConfigProblem("subagents.enabled", BOOLEAN),)


@pytest.mark.parametrize("field", ["max_turns", "max_seconds", "max_tokens"])
@pytest.mark.parametrize("value", ["0", "-1", "true", '"3"', "2.5", "[3]"])
def test_an_invalid_limit_is_a_problem_that_names_the_field(
    tmp_path: Path, field: str, value: str
) -> None:
    problems = problems_of(tmp_path, f"[subagents]\n{field} = {value}\n")

    assert problems == (ConfigProblem(f"subagents.{field}", INTEGER),)


def test_messages_never_repeat_the_value_received(tmp_path: Path) -> None:
    text = f'[subagents]\nmax_turns = "{SENTINEL}"\nmax_seconds = -123456\n'

    problems = problems_of(tmp_path, text)

    shown = " ".join(p.message for p in problems)
    assert SENTINEL not in shown and "123456" not in shown
    assert [p.field for p in problems] == ["subagents.max_turns", "subagents.max_seconds"]


def test_subagents_that_is_not_a_table_is_a_problem(tmp_path: Path) -> None:
    assert problems_of(tmp_path, "subagents = 3\n") == (
        ConfigProblem("subagents", "debe ser una tabla."),
    )


def test_an_unknown_field_of_the_section_is_refused(tmp_path: Path) -> None:
    assert problems_of(tmp_path, "[subagents]\notra = 1\n") == (
        ConfigProblem("subagents.otra", UNKNOWN),
    )


def test_the_example_template_documents_the_section() -> None:
    template = (Path(__file__).resolve().parents[2] / "config.example.toml").read_text(
        encoding="utf-8"
    )

    assert "[subagents]" in template
    assert "# enabled = false" in template
