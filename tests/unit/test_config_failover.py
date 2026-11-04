"""``[failover]`` of the configuration: the models to fall back to (HU-07-05 / T005 / FR-008).

The list names aliases of ``[models]``; it is off when absent or empty. A bad value stops the
start with a problem that names the field and never repeats the value.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import (
    MAX_FAILOVER_MODELS,
    RESERVED_ALIAS,
    HarnessConfig,
    InvalidConfigError,
    load_config,
)
from tests.unit.config_support import MINIMAL_CONFIG, SENTINEL, write_config

MODELS = '[models]\nuno = "gemini/gemini-x"\ndos = "groq/openai/gpt-y"\ntres = "ollama/llama"\n'
EXAMPLE = Path(__file__).resolve().parents[2] / "config.example.toml"


def load(tmp_path: Path, extra: str, **environ: str) -> HarnessConfig:
    return load_config(write_config(tmp_path, MINIMAL_CONFIG + extra), environ=environ)


def problems(tmp_path: Path, extra: str) -> dict[str, str]:
    with pytest.raises(InvalidConfigError) as info:
        load(tmp_path, extra)
    return {problem.field: problem.message for problem in info.value.problems}


def test_the_failover_is_off_by_default(tmp_path: Path) -> None:
    assert load(tmp_path, "").failover == ()
    assert load(tmp_path, MODELS).failover == ()


def test_an_empty_section_or_list_is_off(tmp_path: Path) -> None:
    assert load(tmp_path, MODELS + "[failover]\n").failover == ()
    assert load(tmp_path, MODELS + "[failover]\nmodels = []\n").failover == ()


def test_the_list_is_read_in_its_order(tmp_path: Path) -> None:
    config = load(tmp_path, MODELS + '[failover]\nmodels = ["tres", "uno"]\n')

    assert config.failover == ("tres", "uno")


def test_the_list_may_hold_every_alias(tmp_path: Path) -> None:
    config = load(tmp_path, MODELS + '[failover]\nmodels = ["uno", "dos", "tres"]\n')

    assert config.failover == ("uno", "dos", "tres")


def test_an_alias_that_does_not_exist_is_a_problem_that_does_not_repeat_it(
    tmp_path: Path,
) -> None:
    found = problems(tmp_path, MODELS + f'[failover]\nmodels = ["uno", "{SENTINEL}"]\n')

    assert set(found) == {"failover.models"}
    assert SENTINEL not in found["failover.models"]


def test_an_alias_without_a_models_table_is_a_problem(tmp_path: Path) -> None:
    assert set(problems(tmp_path, '[failover]\nmodels = ["uno"]\n')) == {"failover.models"}


def test_a_repeated_alias_is_a_problem(tmp_path: Path) -> None:
    found = problems(tmp_path, MODELS + '[failover]\nmodels = ["uno", "dos", "uno"]\n')

    assert set(found) == {"failover.models"}
    assert "uno" not in found["failover.models"]


def test_the_word_of_the_default_model_is_a_problem(tmp_path: Path) -> None:
    found = problems(tmp_path, MODELS + f'[failover]\nmodels = ["{RESERVED_ALIAS}"]\n')

    assert set(found) == {"failover.models"}


@pytest.mark.parametrize(
    "value",
    [
        f'"{SENTINEL}"',
        "5",
        "true",
        f'[1, "{SENTINEL}"]',
        f'["uno", {{ a = "{SENTINEL}" }}]',
        '["uno", ""]',
        '["uno", "  "]',
        f'[["{SENTINEL}"]]',
    ],
    ids=["text", "number", "boolean", "mixed", "table-item", "empty-text", "blank-text", "nested"],
)
def test_a_value_that_is_not_a_list_of_texts_is_a_problem(tmp_path: Path, value: str) -> None:
    found = problems(tmp_path, MODELS + f"[failover]\nmodels = {value}\n")

    assert set(found) == {"failover.models"}
    assert SENTINEL not in found["failover.models"]


def test_more_than_the_maximum_is_a_problem(tmp_path: Path) -> None:
    names = [f"m{index}" for index in range(MAX_FAILOVER_MODELS + 1)]
    table = "[models]\n" + "".join(f'{name} = "ollama/x"\n' for name in names)
    items = ", ".join(f'"{name}"' for name in names)

    found = problems(tmp_path, table + f"[failover]\nmodels = [{items}]\n")

    assert set(found) == {"failover.models"}


def test_exactly_the_maximum_is_accepted(tmp_path: Path) -> None:
    names = [f"m{index}" for index in range(MAX_FAILOVER_MODELS)]
    table = "[models]\n" + "".join(f'{name} = "ollama/x"\n' for name in names)
    items = ", ".join(f'"{name}"' for name in names)

    assert load(tmp_path, table + f"[failover]\nmodels = [{items}]\n").failover == tuple(names)


def test_an_unknown_field_of_the_section_is_a_problem(tmp_path: Path) -> None:
    found = problems(tmp_path, MODELS + f'[failover]\nmodels = ["uno"]\nextra = "{SENTINEL}"\n')

    assert set(found) == {"failover.extra"}
    assert SENTINEL not in found["failover.extra"]


def test_a_section_that_is_not_a_table_is_a_problem(tmp_path: Path) -> None:
    config_text = MINIMAL_CONFIG + 'failover = "uno"\n'
    with pytest.raises(InvalidConfigError) as info:
        load_config(write_config(tmp_path, config_text), environ={})

    assert {problem.field for problem in info.value.problems} == {"failover"}


def test_the_example_documents_the_section() -> None:
    text = EXAMPLE.read_text(encoding="utf-8")

    assert "# [failover]" in text
    assert "# models = " in text
    assert "predeterminado" in text
