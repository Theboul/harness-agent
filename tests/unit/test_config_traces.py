"""The optional ``[traces]`` section of ``config.toml`` (HU-10-01 / FR-016).

The traces are on by default and the section only exists to turn them off. A value that is not a
boolean, an unknown field or a section that is not a table stops the start, and the message never
repeats the value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import ConfigProblem, InvalidConfigError, TraceSettings, load_config
from tests.unit.config_support import SENTINEL, write_config

ROOT = Path(__file__).resolve().parents[2]
BASE = 'model = "fake/test"\n'
UNKNOWN = "campo desconocido en el esquema."
BOOLEAN = "debe ser true o false."


def settings_of(tmp_path: Path, text: str) -> TraceSettings:
    return load_config(write_config(tmp_path, BASE + text), environ={}).traces


def problems_of(tmp_path: Path, text: str) -> tuple[ConfigProblem, ...]:
    with pytest.raises(InvalidConfigError) as raised:
        load_config(write_config(tmp_path, BASE + text), environ={})
    return raised.value.problems


def test_without_the_section_the_traces_are_on() -> None:
    assert TraceSettings() == TraceSettings(enabled=True)


def test_an_absent_or_empty_section_keeps_the_traces_on(tmp_path: Path) -> None:
    assert settings_of(tmp_path, "") == TraceSettings(enabled=True)
    assert settings_of(tmp_path, "[traces]\n") == TraceSettings(enabled=True)


def test_the_section_can_turn_them_off_or_on(tmp_path: Path) -> None:
    assert settings_of(tmp_path, "[traces]\nenabled = false\n").enabled is False
    assert settings_of(tmp_path, "[traces]\nenabled = true\n").enabled is True


@pytest.mark.parametrize("value", ["1", "0", '"true"', "2.5", "[true]", '"si"'])
def test_an_enabled_that_is_not_a_boolean_is_a_problem(tmp_path: Path, value: str) -> None:
    problems = problems_of(tmp_path, f"[traces]\nenabled = {value}\n")

    assert problems == (ConfigProblem("traces.enabled", BOOLEAN),)


def test_messages_never_repeat_the_value_received(tmp_path: Path) -> None:
    problems = problems_of(tmp_path, f'[traces]\nenabled = "{SENTINEL}"\n')

    assert SENTINEL not in " ".join(problem.message for problem in problems)
    assert [problem.field for problem in problems] == ["traces.enabled"]


def test_traces_that_is_not_a_table_is_a_problem(tmp_path: Path) -> None:
    assert problems_of(tmp_path, "traces = 3\n") == (
        ConfigProblem("traces", "debe ser una tabla."),
    )


def test_an_unknown_field_of_the_section_is_refused(tmp_path: Path) -> None:
    assert problems_of(tmp_path, "[traces]\notra = 1\n") == (ConfigProblem("traces.otra", UNKNOWN),)


def test_the_example_template_documents_the_section_and_loads_as_it_is() -> None:
    template = (ROOT / "config.example.toml").read_text(encoding="utf-8")

    assert "[traces]" in template and "# enabled = true" in template
    assert load_config(ROOT / "config.example.toml", environ={}).traces == TraceSettings()


def test_the_section_of_the_template_is_valid_once_uncommented(tmp_path: Path) -> None:
    lines = (ROOT / "config.example.toml").read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "# [traces]")
    block: list[str] = []
    for line in lines[start:]:
        if not line.startswith("# "):
            break  # the section ends at the first blank line
        block.append(line[2:])
    section = "\n".join(text for text in block if text.startswith("[") or "=" in text) + "\n"

    assert settings_of(tmp_path, section) == TraceSettings()
    assert "enabled = true" in section
