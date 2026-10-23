"""Tests of the ``[permissions]`` section of the configuration (HU-05-01 / T007).

The section has two lists, ``deny`` and ``ask``, of tool names; both are empty by default and
there is no way to define a rule to allow: any other field is unknown and stops the start. The
messages follow ``specs/007-permission-policy/contracts/permissions_config_contract.md`` and never
reproduce the received value.
"""

from __future__ import annotations

import dataclasses
import tomllib
from pathlib import Path

import pytest

from harness_agent.config import (
    ConfigProblem,
    HarnessConfig,
    InvalidConfigError,
    Limits,
    Paths,
    SecretInConfigFileError,
    load_config,
)
from harness_agent.core.permissions import PermissionRules
from tests.unit.config_support import MINIMAL_CONFIG, SENTINEL, write_config

NOT_A_LIST = "debe ser una lista de textos no vacíos."
UNKNOWN = "campo desconocido en el esquema."
TEMPLATE = Path(__file__).resolve().parents[2] / "config.example.toml"


def load(tmp_path: Path, extra: str) -> HarnessConfig:
    return load_config(write_config(tmp_path, MINIMAL_CONFIG + extra), environ={})


def problems_of(tmp_path: Path, text: str) -> tuple[ConfigProblem, ...]:
    path = write_config(tmp_path, text)
    with pytest.raises(InvalidConfigError) as info:
        load_config(path, environ={})
    return info.value.problems


class TestSeccionValida:
    def test_without_the_section_the_rules_are_empty(self, tmp_path: Path) -> None:
        config = load(tmp_path, "")

        assert config.permissions == PermissionRules()
        assert isinstance(config.permissions, PermissionRules)

    def test_the_lists_are_loaded_in_order(self, tmp_path: Path) -> None:
        config = load(tmp_path, '[permissions]\ndeny = ["b", "a"]\nask = ["c"]\n')

        assert config.permissions == PermissionRules(deny=("b", "a"), ask=("c",))

    def test_empty_lists_and_a_missing_list_are_valid(self, tmp_path: Path) -> None:
        assert (
            load(tmp_path, "[permissions]\ndeny = []\nask = []\n").permissions == PermissionRules()
        )
        only_ask = load(tmp_path, '[permissions]\nask = ["x"]\n')
        assert only_ask.permissions == PermissionRules(ask=("x",))
        assert load(tmp_path, "[permissions]\n").permissions == PermissionRules()

    def test_the_duplicates_are_dropped_and_the_names_are_kept_as_they_are(
        self, tmp_path: Path
    ) -> None:
        config = load(
            tmp_path, '[permissions]\ndeny = ["Escribir", "escribir", "Escribir", "a b"]\n'
        )

        assert config.permissions.deny == ("Escribir", "escribir", "a b")

    def test_a_name_in_both_lists_is_valid(self, tmp_path: Path) -> None:
        config = load(tmp_path, '[permissions]\ndeny = ["x"]\nask = ["x"]\n')

        assert config.permissions == PermissionRules(deny=("x",), ask=("x",))

    def test_the_section_does_not_change_the_rest_of_the_configuration(
        self, tmp_path: Path
    ) -> None:
        plain = load(tmp_path, "[limits]\nmax_turns = 7\n")
        with_section = load(tmp_path, '[limits]\nmax_turns = 7\n[permissions]\ndeny = ["a"]\n')

        assert dataclasses.replace(with_section, permissions=PermissionRules()) == plain

    def test_the_configuration_stays_immutable_and_buildable_without_the_new_field(self) -> None:
        config = HarnessConfig(
            model="fake/x",
            limits=Limits(),
            paths=Paths(),
            source=Path("config.toml"),
        )

        assert config.permissions == PermissionRules()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.permissions = PermissionRules(deny=("a",))  # type: ignore[misc]


class TestSeccionInvalida:
    @pytest.mark.parametrize("field", ["deny", "ask"])
    @pytest.mark.parametrize(
        "value",
        ['"escribir"', "5", "true", '{ a = "b" }', "[1]", '[""]', '["  "]', "[true]", '[["a"]]'],
    )
    def test_a_value_that_is_not_a_list_of_non_empty_texts(
        self, tmp_path: Path, field: str, value: str
    ) -> None:
        problems = problems_of(tmp_path, f"{MINIMAL_CONFIG}[permissions]\n{field} = {value}\n")

        assert problems == (ConfigProblem(f"permissions.{field}", NOT_A_LIST),)

    def test_the_message_does_not_reproduce_the_value(self, tmp_path: Path) -> None:
        path = write_config(
            tmp_path, f'{MINIMAL_CONFIG}[permissions]\ndeny = ["bueno", 5, "{SENTINEL}", ""]\n'
        )

        with pytest.raises(InvalidConfigError) as info:
            load_config(path, environ={})

        assert f"- permissions.deny: {NOT_A_LIST}" in str(info.value)
        assert SENTINEL not in str(info.value)
        assert SENTINEL not in repr(info.value)

    @pytest.mark.parametrize("value", ["5", '"x"', "[]"])
    def test_a_permissions_value_that_is_not_a_table(self, tmp_path: Path, value: str) -> None:
        text = f"permissions = {value}\n{MINIMAL_CONFIG}"

        assert problems_of(tmp_path, text) == (ConfigProblem("permissions", "debe ser una tabla."),)

    @pytest.mark.parametrize("name", ["allow", "permit", "permitir", "allow_all", "otra"])
    def test_there_is_no_way_to_define_an_allow_rule(self, tmp_path: Path, name: str) -> None:
        text = f'{MINIMAL_CONFIG}[permissions]\n{name} = ["escribir"]\n'

        assert problems_of(tmp_path, text) == (ConfigProblem(f"permissions.{name}", UNKNOWN),)

    def test_a_nested_table_inside_the_section_is_reported_once(self, tmp_path: Path) -> None:
        text = f'{MINIMAL_CONFIG}[permissions]\ndeny = ["a"]\n[permissions.allow]\nx = 1\n'

        assert problems_of(tmp_path, text) == (ConfigProblem("permissions.allow", UNKNOWN),)

    def test_several_problems_come_together_in_the_documented_order(self, tmp_path: Path) -> None:
        text = (
            "[limits]\nmax_turns = 0\n"
            "[paths]\nsessions_db = 5\n"
            '[permissions]\ndeny = 5\nask = [""]\nallow = ["x"]\n'
        )

        assert problems_of(tmp_path, text) == (
            ConfigProblem("model", "falta el campo obligatorio."),
            ConfigProblem("limits.max_turns", "debe ser un entero mayor que 0."),
            ConfigProblem("paths.sessions_db", "debe ser un texto no vacío."),
            ConfigProblem("permissions.deny", NOT_A_LIST),
            ConfigProblem("permissions.ask", NOT_A_LIST),
            ConfigProblem("permissions.allow", UNKNOWN),
        )

    def test_a_field_named_like_a_key_inside_the_section_is_still_a_secret_field(
        self, tmp_path: Path
    ) -> None:
        field = "api_" + "key"
        path = write_config(tmp_path, f'{MINIMAL_CONFIG}[permissions]\n{field} = "{SENTINEL}"\n')

        with pytest.raises(SecretInConfigFileError) as info:
            load_config(path, environ={})

        assert info.value.fields == (f"permissions.{field}",)
        assert SENTINEL not in str(info.value)


class TestPlantilla:
    def test_the_template_still_declares_only_model_limits_and_paths(self) -> None:
        raw = tomllib.loads(TEMPLATE.read_bytes().decode("utf-8"))

        assert set(raw) == {"model", "limits", "paths"}

    def test_the_template_still_loads_and_gives_empty_rules(self) -> None:
        assert load_config(TEMPLATE, environ={}).permissions == PermissionRules()

    def test_the_template_has_the_commented_section_with_its_warning(self) -> None:
        lines = TEMPLATE.read_bytes().decode("utf-8").splitlines()

        assert "# [permissions]" in lines
        assert "# deny = []" in lines
        assert "# ask = []" in lines
        warning = " ".join(line for line in lines if line.startswith("#"))
        assert "reglas de permitir" in warning
