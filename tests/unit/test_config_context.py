"""The optional ``[context]`` section of ``config.toml`` (HU-02-03 / FR-020, SC-011, R18).

An additive extension of the HU-00-04 schema: without the section the defaults apply, a value
that is not valid stops the start and the message never repeats what was received.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import (
    ConfigProblem,
    InvalidConfigError,
    SecretInConfigFileError,
    load_config,
)
from harness_agent.core import ContextSettings
from tests.unit.config_support import SENTINEL, write_config

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "config.example.toml"
BASE = 'model = "fake/test"\n'
UNKNOWN = "campo desconocido en el esquema."
WINDOWS_MESSAGE = (
    "debe ser una tabla de modelo y tamaño de ventana (enteros entre 1000 y 10000000)."
)
RANGES = {
    "window_tokens": "debe ser un entero entre 1000 y 10000000.",
    "threshold_percent": "debe ser un entero entre 10 y 95.",
    "recent_percent": "debe ser un entero entre 5 y 60.",
    "min_recent_messages": "debe ser un entero entre 1 y 50.",
    "summary_tokens": "debe ser un entero entre 100 y 8000.",
}


def context_of(tmp_path: Path, text: str) -> ContextSettings:
    return load_config(write_config(tmp_path, BASE + text), environ={}).context


def problems_of(tmp_path: Path, text: str) -> tuple[ConfigProblem, ...]:
    with pytest.raises(InvalidConfigError) as raised:
        load_config(write_config(tmp_path, BASE + text), environ={})
    return raised.value.problems


def test_without_the_section_the_defaults_apply(tmp_path: Path) -> None:
    assert context_of(tmp_path, "") == ContextSettings()
    assert context_of(tmp_path, "[context]\n") == ContextSettings()


def test_a_complete_section_is_read(tmp_path: Path) -> None:
    text = (
        "[context]\nwindow_tokens = 64000\nthreshold_percent = 70\nrecent_percent = 20\n"
        "min_recent_messages = 6\nsummary_tokens = 1500\n"
        '[context.windows]\n"openai/gpt-4o" = 128000\n'
    )

    settings = context_of(tmp_path, text)

    assert settings == ContextSettings(
        window_tokens=64_000,
        windows=(("openai/gpt-4o", 128_000),),
        threshold_percent=70,
        recent_percent=20,
        min_recent_messages=6,
        summary_tokens=1_500,
    )


@pytest.mark.parametrize("field", RANGES)
@pytest.mark.parametrize("value", ["0", "-5", "true", '"texto"', "1.5", "100000000"])
def test_an_invalid_value_stops_the_start_with_the_field_and_a_fixed_message(
    tmp_path: Path, field: str, value: str
) -> None:
    problems = problems_of(tmp_path, f"[context]\n{field} = {value}\n")

    assert problems == (ConfigProblem(f"context.{field}", RANGES[field]),)


def test_example_e1_of_the_contract(tmp_path: Path) -> None:
    text = f'[context]\nsummary_tokens = "{SENTINEL}"\nthreshold_percent = 99\n'

    problems = problems_of(tmp_path, text)

    assert [p.field for p in problems] == ["context.threshold_percent", "context.summary_tokens"]
    shown = " ".join(p.message for p in problems)
    assert SENTINEL not in shown and "99" not in shown


def test_a_context_that_is_not_a_table_is_a_problem(tmp_path: Path) -> None:
    assert problems_of(tmp_path, "context = 3\n") == (
        ConfigProblem("context", "debe ser una tabla."),
    )


def test_an_unknown_field_of_the_section_is_refused(tmp_path: Path) -> None:
    problems = problems_of(tmp_path, "[context]\notra = 1\n")

    assert problems == (ConfigProblem("context.otra", UNKNOWN),)


# --- R18: names of models as quoted keys ----------------------------------------------------------


def test_a_quoted_key_with_a_slash_and_a_dot_is_accepted_and_used(tmp_path: Path) -> None:
    text = '[context.windows]\n"proveedor/modelo-1.5" = 128000\n"otro/m" = 8000\n'

    settings = context_of(tmp_path, text)

    assert settings.window_for("proveedor/modelo-1.5") == 128_000
    assert settings.window_for("otro/m") == 8_000
    assert settings.window_for("desconocido/x") == 32_000


@pytest.mark.parametrize("value", ["0", "-5", "true", '"texto"', "999", "1.5"])
def test_an_invalid_value_for_a_model_is_a_problem_that_repeats_neither_value_nor_name(
    tmp_path: Path, value: str
) -> None:
    problems = problems_of(tmp_path, f'[context.windows]\n"proveedor/modelo-1.5" = {value}\n')

    assert problems == (ConfigProblem("context.windows", WINDOWS_MESSAGE),)
    shown = " ".join(p.message + p.field for p in problems)
    assert "modelo-1.5" not in shown and "texto" not in shown


def test_windows_that_is_not_a_table_is_a_problem(tmp_path: Path) -> None:
    problems = problems_of(tmp_path, "[context]\nwindows = 5\n")

    assert problems == (ConfigProblem("context.windows", WINDOWS_MESSAGE),)


def test_a_model_name_that_looks_like_a_key_is_refused_as_a_possible_secret(
    tmp_path: Path,
) -> None:
    """The known limit of R10: the check of names with the shape of a key applies to any name."""
    text = '[context.windows]\n"proveedor/modelo-' + "ke" + 'y" = 8000\n'

    with pytest.raises(SecretInConfigFileError):
        load_config(write_config(tmp_path, BASE + text), environ={})


# --- the template ---------------------------------------------------------------------------------


def commented_section() -> str:
    """The lines of the ``[context]`` block of the template, uncommented."""
    lines = TEMPLATE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "# [context]")
    block = []
    for line in lines[start:]:
        text = line[2:] if line.startswith("# ") else ""
        if text.startswith("[") or ("=" in text and not text.startswith("#")):
            block.append(text)
    return "\n".join(block) + "\n"


def test_the_template_has_the_section_commented_and_it_loads_as_it_is() -> None:
    config = load_config(TEMPLATE, environ={})

    assert config.context == ContextSettings()


def test_the_section_of_the_template_is_valid_once_uncommented(tmp_path: Path) -> None:
    section = commented_section()

    assert "[context]" in section and "[context.windows]" in section
    settings = context_of(tmp_path, section)

    assert settings.window_tokens == 32_000
    assert settings.windows and all(window >= 1_000 for _, window in settings.windows)
