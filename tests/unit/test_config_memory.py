"""The optional ``[memory]`` section of ``config.toml`` (HU-04-01 and HU-04-02 / FR-016).

The memory is off by default: without the section nothing is registered or loaded. A value that is
not valid, an unknown field or a section that is not a table stops the start, and the message never
repeats the value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import ConfigProblem, InvalidConfigError, load_config
from harness_agent.core import MEMORY_FIELD_RANGES, MemorySettings
from tests.unit.config_support import SENTINEL, write_config

ROOT = Path(__file__).resolve().parents[2]
BASE = 'model = "fake/test"\n'
UNKNOWN = "campo desconocido en el esquema."
BOOLEAN = "debe ser true o false."


def settings_of(tmp_path: Path, text: str) -> MemorySettings:
    return load_config(write_config(tmp_path, BASE + text), environ={}).memory


def problems_of(tmp_path: Path, text: str) -> tuple[ConfigProblem, ...]:
    with pytest.raises(InvalidConfigError) as raised:
        load_config(write_config(tmp_path, BASE + text), environ={})
    return raised.value.problems


def test_without_the_section_the_memory_is_off_with_the_default_values(tmp_path: Path) -> None:
    expected = MemorySettings(
        enabled=False, budget_tokens=2_000, max_entries=200, max_content_chars=500
    )

    assert settings_of(tmp_path, "") == expected
    assert settings_of(tmp_path, "[memory]\n") == expected


def test_the_memory_is_on_only_if_the_section_turns_it_on(tmp_path: Path) -> None:
    assert settings_of(tmp_path, "[memory]\nbudget_tokens = 1000\n").enabled is False
    assert settings_of(tmp_path, "[memory]\nenabled = false\n").enabled is False
    assert settings_of(tmp_path, "[memory]\nenabled = true\n").enabled is True


def test_a_complete_section_is_read(tmp_path: Path) -> None:
    text = (
        "[memory]\nenabled = true\nbudget_tokens = 800\nmax_entries = 50\nmax_content_chars = 300\n"
    )

    assert settings_of(tmp_path, text) == MemorySettings(True, 800, 50, 300)


@pytest.mark.parametrize("field", sorted(MEMORY_FIELD_RANGES))
def test_the_ends_of_each_range_are_valid(tmp_path: Path, field: str) -> None:
    low, high = MEMORY_FIELD_RANGES[field]

    assert getattr(settings_of(tmp_path, f"[memory]\n{field} = {low}\n"), field) == low
    assert getattr(settings_of(tmp_path, f"[memory]\n{field} = {high}\n"), field) == high


@pytest.mark.parametrize("value", ["1", "0", '"true"', "2.5", "[true]", '"si"'])
def test_an_enabled_that_is_not_a_boolean_is_a_problem(tmp_path: Path, value: str) -> None:
    problems = problems_of(tmp_path, f"[memory]\nenabled = {value}\n")

    assert problems == (ConfigProblem("memory.enabled", BOOLEAN),)


@pytest.mark.parametrize("field", sorted(MEMORY_FIELD_RANGES))
def test_an_integer_out_of_its_range_or_of_another_type_is_a_problem(
    tmp_path: Path, field: str
) -> None:
    low, high = MEMORY_FIELD_RANGES[field]
    message = f"debe ser un entero entre {low} y {high}."

    for bad in (str(low - 1), str(high + 1), "true", '"3"', "2.5", "[3]"):
        problems = problems_of(tmp_path, f"[memory]\n{field} = {bad}\n")
        assert problems == (ConfigProblem(f"memory.{field}", message),)


def test_messages_never_repeat_the_value_received(tmp_path: Path) -> None:
    text = f'[memory]\nbudget_tokens = "{SENTINEL}"\nmax_entries = -123456\n'

    problems = problems_of(tmp_path, text)

    shown = " ".join(problem.message for problem in problems)
    assert SENTINEL not in shown and "123456" not in shown
    assert [problem.field for problem in problems] == ["memory.budget_tokens", "memory.max_entries"]


def test_memory_that_is_not_a_table_is_a_problem(tmp_path: Path) -> None:
    assert problems_of(tmp_path, "memory = 3\n") == (
        ConfigProblem("memory", "debe ser una tabla."),
    )


def test_an_unknown_field_of_the_section_is_refused(tmp_path: Path) -> None:
    assert problems_of(tmp_path, "[memory]\notra = 1\n") == (ConfigProblem("memory.otra", UNKNOWN),)


def test_the_example_template_documents_the_section_and_loads_as_it_is() -> None:
    template = (ROOT / "config.example.toml").read_text(encoding="utf-8")

    assert "[memory]" in template and "# enabled = false" in template
    assert load_config(ROOT / "config.example.toml", environ={}).memory == MemorySettings()


def test_the_section_of_the_template_is_valid_once_uncommented(tmp_path: Path) -> None:
    lines = (ROOT / "config.example.toml").read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "# [memory]")
    block: list[str] = []
    for line in lines[start:]:
        if not line.startswith("# "):
            break  # the section ends at the first blank line
        block.append(line[2:])
    section = "\n".join(text for text in block if text.startswith("[") or "=" in text) + "\n"

    settings = settings_of(tmp_path, section)

    assert settings == MemorySettings()
    assert "enabled = false" in section and "budget_tokens = 2000" in section
