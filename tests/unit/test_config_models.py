"""``[models]`` of the configuration: aliases of models (HU-06-06 / T003 / FR-001, FR-002)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.adapters.providers.model_switch import DEFAULT_ALIAS
from harness_agent.config import (
    RESERVED_ALIAS,
    HarnessConfig,
    InvalidConfigError,
    SecretInConfigFileError,
    load_config,
)
from tests.unit.config_support import MINIMAL_CONFIG, SECRET_FIELD, SENTINEL, write_config

MODELS = '[models]\nplan = "gemini/gemini-x"\nbuild = "groq/openai/gpt-y"\n'


def load(tmp_path: Path, extra: str, **environ: str) -> HarnessConfig:
    return load_config(write_config(tmp_path, MINIMAL_CONFIG + extra), environ=environ)


def problems(tmp_path: Path, extra: str) -> dict[str, str]:
    with pytest.raises(InvalidConfigError) as info:
        load(tmp_path, extra)
    return {problem.field: problem.message for problem in info.value.problems}


def test_there_are_no_aliases_by_default(tmp_path: Path) -> None:
    assert load(tmp_path, "").models == ()
    assert load(tmp_path, "[models]\n").models == ()


def test_the_reserved_word_is_the_one_of_the_switch() -> None:
    assert RESERVED_ALIAS == DEFAULT_ALIAS


def test_the_aliases_keep_the_order_of_the_file(tmp_path: Path) -> None:
    config = load(tmp_path, MODELS, GEMINI_API_KEY="g-secret-1", GROQ_API_KEY="q-secret-2")

    assert [(entry.alias, entry.model) for entry in config.models] == [
        ("plan", "gemini/gemini-x"),
        ("build", "groq/openai/gpt-y"),
    ]
    assert config.model == "fake/test"


def test_each_alias_takes_the_key_of_its_provider_from_the_environment(tmp_path: Path) -> None:
    config = load(tmp_path, MODELS, GEMINI_API_KEY="g-secret-1", GROQ_API_KEY="q-secret-2")

    plan, build = config.models
    assert (plan.key_variable, plan.api_key is not None and plan.api_key.reveal()) == (
        "GEMINI_API_KEY",
        "g-secret-1",
    )
    assert (build.key_variable, build.api_key is not None and build.api_key.reveal()) == (
        "GROQ_API_KEY",
        "q-secret-2",
    )
    assert "g-secret-1" not in repr(config) and "q-secret-2" not in repr(config)


def test_a_missing_key_does_not_stop_the_start(tmp_path: Path) -> None:
    config = load(tmp_path, MODELS, GROQ_API_KEY="  ")

    plan, build = config.models
    assert plan.api_key is None and plan.key_variable == "GEMINI_API_KEY"
    assert build.api_key is None and build.key_variable == "GROQ_API_KEY"


def test_a_provider_without_key_has_no_variable(tmp_path: Path) -> None:
    (entry,) = load(tmp_path, '[models]\nlocal = "ollama/llama"\n').models

    assert (entry.api_key, entry.key_variable) == (None, None)


@pytest.mark.parametrize("alias", ["Plan", "1plan", "a b", "x" * 33, "pl.an"])
def test_an_invalid_alias_is_reported(tmp_path: Path, alias: str) -> None:
    found = problems(tmp_path, f'[models]\n"{alias}" = "fake/x"\n')

    assert found == {
        f"models.{alias}": "el alias debe empezar con una letra minúscula y "
        "tener solo minúsculas, números, - y _ (hasta 32 caracteres)."
    }


def test_the_reserved_word_is_not_an_alias(tmp_path: Path) -> None:
    found = problems(tmp_path, f'[models]\n{RESERVED_ALIAS} = "fake/x"\n')

    assert list(found) == [f"models.{RESERVED_ALIAS}"]


@pytest.mark.parametrize("value", ['"sin-barra"', '"/modelo"', '"fake/"', "7", "true", "[]"])
def test_a_value_without_the_form_is_reported_without_repeating_it(
    tmp_path: Path, value: str
) -> None:
    found = problems(tmp_path, f"[models]\nplan = {value}\n")

    assert found == {"models.plan": "debe ser un texto con la forma <proveedor>/<modelo>."}


def test_an_unknown_provider_is_reported(tmp_path: Path) -> None:
    found = problems(tmp_path, f'[models]\nplan = "{SENTINEL}/x"\n')

    assert list(found) == ["models.plan"]
    assert SENTINEL not in found["models.plan"]
    assert found["models.plan"].startswith("el proveedor no es uno de los admitidos")


def test_models_must_be_a_table(tmp_path: Path) -> None:
    path = write_config(tmp_path, 'model = "fake/test"\nmodels = "x"\n')

    with pytest.raises(InvalidConfigError) as info:
        load_config(path, environ={})

    assert [problem.field for problem in info.value.problems] == ["models"]


def test_an_alias_that_looks_like_a_key_is_a_secret_in_the_file(tmp_path: Path) -> None:
    path = write_config(tmp_path, MINIMAL_CONFIG + f'[models]\n{SECRET_FIELD} = "{SENTINEL}"\n')

    with pytest.raises(SecretInConfigFileError):
        load_config(path, environ={})


def test_a_key_under_an_alias_is_a_secret_in_the_file(tmp_path: Path) -> None:
    path = write_config(
        tmp_path, MINIMAL_CONFIG + f'[models.plan]\n{SECRET_FIELD} = "{SENTINEL}"\n'
    )

    with pytest.raises(SecretInConfigFileError):
        load_config(path, environ={})


def test_a_table_under_an_alias_is_not_a_model(tmp_path: Path) -> None:
    found = problems(tmp_path, '[models.plan]\nname = "fake/x"\n')

    assert found == {"models.plan": "debe ser un texto con la forma <proveedor>/<modelo>."}


def test_the_template_documents_the_section() -> None:
    template = Path(__file__).resolve().parents[2] / "config.example.toml"

    text = template.read_text(encoding="utf-8")
    assert "# [models]" in text and "GEMINI_API_KEY" in text
