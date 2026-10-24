"""Tests for the schema of the configuration: valid values, defaults and invalid files.

HU-00-04 / T008 (``TestEsquemaValido``) and T009 (``TestEsquemaInvalido``). The model comes only
from the file (AC-01); the limits are positive integers; the paths are resolved against the folder
of the file; every problem is reported together, in a deterministic order, and never with the
received value.
"""

from __future__ import annotations

import dataclasses
import os
import time
from pathlib import Path

import pytest

from harness_agent.config import (
    ConfigProblem,
    HarnessConfig,
    InvalidConfigError,
    Limits,
    Paths,
    load_config,
)
from tests.unit.config_support import SENTINEL, write_config

UNKNOWN = "campo desconocido en el esquema."
NOT_AN_INTEGER = "debe ser un entero mayor que 0."
NOT_TEXT = "debe ser un texto no vacío."
BAD_MODEL = "debe ser un texto con la forma <proveedor>/<modelo>."
FULL_CONFIG = """\
model = "fake/test"

[limits]
max_turns = 12
max_seconds = 90
max_tokens = 5000

[paths]
workspace_root = "trabajo"
sessions_db = "datos/sesiones.db"
"""


def load(tmp_path: Path, text: str) -> HarnessConfig:
    return load_config(write_config(tmp_path, text), environ={})


def problems_of(tmp_path: Path, text: str) -> tuple[ConfigProblem, ...]:
    path = write_config(tmp_path, text)
    with pytest.raises(InvalidConfigError) as info:
        load_config(path, environ={})
    return info.value.problems


class TestEsquemaValido:
    def test_ac01_another_model_in_the_file_is_the_model_in_use(self, tmp_path: Path) -> None:
        first = write_config(tmp_path, 'model = "fake/a"\n', name="a.toml")
        second = write_config(tmp_path, 'model = "fake/b"\n', name="b.toml")

        assert load_config(first, environ={}).model == "fake/a"
        assert load_config(second, environ={}).model == "fake/b"

    def test_ac01_editing_the_same_file_changes_the_model(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, 'model = "fake/a"\n')
        before = load_config(path, environ={}).model

        write_config(tmp_path, 'model = "fake/b"\n')
        after = load_config(path, environ={}).model

        assert (before, after) == ("fake/a", "fake/b")

    def test_a_file_with_only_the_model_takes_every_default(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, 'model = "fake/test"\n')

        config = load_config(path, environ={})

        assert config.limits == Limits(max_turns=30, max_seconds=600, max_tokens=200000)
        assert config.paths.workspace_root is None
        assert config.paths.sessions_db == path.parent / ".harness" / "sessions.db"
        assert config.api_key is None
        assert config.key_variable is None

    def test_the_values_of_the_file_are_respected(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, FULL_CONFIG)

        config = load_config(path, environ={})

        assert config.limits == Limits(max_turns=12, max_seconds=90, max_tokens=5000)
        assert config.paths.workspace_root == path.parent / "trabajo"
        assert config.paths.sessions_db == path.parent / "datos" / "sesiones.db"

    def test_relative_paths_are_relative_to_the_file_not_to_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        folder = tmp_path / "carpeta"
        folder.mkdir()
        elsewhere = tmp_path / "otro"
        elsewhere.mkdir()
        path = write_config(folder, FULL_CONFIG)
        monkeypatch.chdir(elsewhere)

        config = load_config(path, environ={})

        assert config.paths.workspace_root == folder.resolve() / "trabajo"
        assert config.paths.sessions_db == folder.resolve() / "datos" / "sesiones.db"

    def test_an_absolute_path_is_kept_normalized(self, tmp_path: Path) -> None:
        absolute = tmp_path / "abs" / ".." / "espacio"
        text = f"model = \"fake/test\"\n[paths]\nworkspace_root = '{absolute}'\n"

        config = load(tmp_path, text)

        assert config.paths.workspace_root == Path(os.path.normpath(absolute))
        assert config.paths.workspace_root is not None
        assert config.paths.workspace_root.is_absolute()

    def test_each_field_has_its_own_type(self, tmp_path: Path) -> None:
        config = load(tmp_path, FULL_CONFIG)

        assert isinstance(config.model, str)
        assert isinstance(config.limits, Limits)
        assert isinstance(config.paths, Paths)
        assert isinstance(config.source, Path)
        for number in (
            config.limits.max_turns,
            config.limits.max_seconds,
            config.limits.max_tokens,
        ):
            assert type(number) is int
        assert isinstance(config.paths.workspace_root, Path)
        assert isinstance(config.paths.sessions_db, Path)

    def test_the_configuration_is_immutable(self, tmp_path: Path) -> None:
        config = load(tmp_path, FULL_CONFIG)

        for target, name in (
            (config, "model"),
            (config, "limits"),
            (config.limits, "max_turns"),
            (config.paths, "sessions_db"),
        ):
            with pytest.raises(dataclasses.FrozenInstanceError):
                setattr(target, name, None)

    @pytest.mark.parametrize("cls", [HarnessConfig, Limits, Paths])
    def test_the_classes_have_no_dict(self, tmp_path: Path, cls: type) -> None:
        config = load(tmp_path, FULL_CONFIG)
        instance = {HarnessConfig: config, Limits: config.limits, Paths: config.paths}[cls]

        assert not hasattr(instance, "__dict__")

    def test_environment_variables_never_override_a_non_secret_value(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, FULL_CONFIG)
        environ = {"MODEL": "fake/otro", "HARNESS_MODEL": "fake/otro", "LIMITS_MAX_TURNS": "1"}

        config = load_config(path, environ=environ)

        assert config.model == "fake/test"
        assert config.limits.max_turns == 12

    def test_smoke_loading_a_complete_configuration_is_well_under_100_ms(
        self, tmp_path: Path
    ) -> None:
        path = write_config(tmp_path, FULL_CONFIG)
        load_config(path, environ={})  # warm-up
        runs = 200

        start = time.perf_counter()
        for _ in range(runs):
            load_config(path, environ={})
        average = (time.perf_counter() - start) / runs

        assert average < 0.1


class TestEsquemaInvalido:
    def test_a_missing_model(self, tmp_path: Path) -> None:
        assert problems_of(tmp_path, "") == (ConfigProblem("model", "falta el campo obligatorio."),)

    def test_a_model_that_is_not_text(self, tmp_path: Path) -> None:
        assert problems_of(tmp_path, "model = 5\n") == (ConfigProblem("model", BAD_MODEL),)

    @pytest.mark.parametrize("model", ["sin-barra", "/x", "fake/", "   "])
    def test_a_model_without_the_provider_slash_model_form(
        self, tmp_path: Path, model: str
    ) -> None:
        assert problems_of(tmp_path, f'model = "{model}"\n') == (ConfigProblem("model", BAD_MODEL),)

    def test_an_unknown_provider_lists_the_admitted_ones(self, tmp_path: Path) -> None:
        assert problems_of(tmp_path, 'model = "desconocido/x"\n') == (
            ConfigProblem(
                "model",
                "el proveedor no es uno de los admitidos "
                "(anthropic, fake, gemini, groq, ollama, openai, openrouter).",
            ),
        )

    @pytest.mark.parametrize("value", ["0", "-1", '"3"', "2.5", "true"])
    @pytest.mark.parametrize("field", ["max_turns", "max_seconds", "max_tokens"])
    def test_a_limit_must_be_an_integer_greater_than_zero(
        self, tmp_path: Path, field: str, value: str
    ) -> None:
        text = f'model = "fake/test"\n[limits]\n{field} = {value}\n'

        assert problems_of(tmp_path, text) == (ConfigProblem(f"limits.{field}", NOT_AN_INTEGER),)

    @pytest.mark.parametrize("value", ['""', "5", '"   "'])
    @pytest.mark.parametrize("field", ["workspace_root", "sessions_db"])
    def test_a_path_must_be_a_non_empty_text(self, tmp_path: Path, field: str, value: str) -> None:
        text = f'model = "fake/test"\n[paths]\n{field} = {value}\n'

        assert problems_of(tmp_path, text) == (ConfigProblem(f"paths.{field}", NOT_TEXT),)

    @pytest.mark.parametrize("table", ["limits", "paths"])
    def test_a_table_that_is_not_a_table(self, tmp_path: Path, table: str) -> None:
        text = f'{table} = 5\nmodel = "fake/test"\n'

        assert problems_of(tmp_path, text) == (ConfigProblem(table, "debe ser una tabla."),)

    def test_unknown_fields_are_named_with_their_dotted_path(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\nmodelo2 = 1\n[limits]\nmax_turn = 3\n[paths]\nroot = "x"\n'

        assert problems_of(tmp_path, text) == (
            ConfigProblem("modelo2", UNKNOWN),
            ConfigProblem("limits.max_turn", UNKNOWN),
            ConfigProblem("paths.root", UNKNOWN),
        )

    def test_an_unknown_table_is_reported_once_without_descending(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\n[extra]\nx = 1\n[extra.deep]\ny = 2\n'

        assert problems_of(tmp_path, text) == (ConfigProblem("extra", UNKNOWN),)

    def test_an_array_of_unknown_tables_is_reported_once(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\n[[extra]]\nx = 1\n[[extra]]\ny = 2\n'

        assert problems_of(tmp_path, text) == (ConfigProblem("extra", UNKNOWN),)

    def test_an_array_of_tables_where_a_table_is_expected(self, tmp_path: Path) -> None:
        text = 'model = "fake/test"\n[[limits]]\nx = 1\n'

        assert problems_of(tmp_path, text) == (ConfigProblem("limits", "debe ser una tabla."),)

    def test_every_problem_is_reported_together_in_the_documented_order(
        self, tmp_path: Path
    ) -> None:
        text = 'zeta = 1\n[limits]\nmax_turns = 0\n[paths]\nsessions_db = ""\nalfa = 2\n'

        assert problems_of(tmp_path, text) == (
            ConfigProblem("model", "falta el campo obligatorio."),
            ConfigProblem("limits.max_turns", NOT_AN_INTEGER),
            ConfigProblem("paths.sessions_db", NOT_TEXT),
            ConfigProblem("zeta", UNKNOWN),
            ConfigProblem("paths.alfa", UNKNOWN),
        )

    def test_the_text_follows_the_format_of_the_contract(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, "limites = 3\n[limits]\nmax_turns = 0\n")

        with pytest.raises(InvalidConfigError) as info:
            load_config(path, environ={})

        assert str(info.value) == (
            f"Configuración inválida en '{path}':\n"
            "- model: falta el campo obligatorio.\n"
            f"- limits.max_turns: {NOT_AN_INTEGER}\n"
            f"- limites: {UNKNOWN}"
        )

    def test_no_message_reproduces_the_invalid_value(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, f'model = "{SENTINEL}"\n[limits]\nmax_turns = "{SENTINEL}"\n')

        with pytest.raises(InvalidConfigError) as info:
            load_config(path, environ={})

        assert SENTINEL not in str(info.value)
        assert SENTINEL not in repr(info.value)

    def test_a_long_field_name_is_clipped_in_the_text(self, tmp_path: Path) -> None:
        name = "x" * 70
        path = write_config(tmp_path, f'model = "fake/test"\n{name} = 1\n')

        with pytest.raises(InvalidConfigError) as info:
            load_config(path, environ={})

        assert name not in str(info.value)
        assert "x" * 63 + "…" in str(info.value)
        assert info.value.problems[0].field == name
