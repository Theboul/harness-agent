"""``[permissions] deny_commands``: shell commands added to the base deny list (HU-05-02 / T008).

An additive extension of the HU-00-04 / HU-05-01 schema
(``specs/026-shell-deny-compound/contracts/deny_commands_config_contract.md``). The field can only
add commands: there is no field to remove, empty or replace the base list, and any such attempt is
an unknown field that stops the start. The value is kept apart from ``PermissionRules``.
"""

from __future__ import annotations

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
from harness_agent.core import PermissionRules
from tests.unit.config_support import SENTINEL, write_config

ROOT = Path(__file__).resolve().parents[2]
NOT_A_COMMAND_LIST = (
    "debe ser una lista de comandos no vacíos, de hasta 500 caracteres y sin caracteres de control."
)
UNKNOWN = "campo desconocido en el esquema."


def load(tmp_path: Path, permissions: str) -> HarnessConfig:
    text = f'model = "fake/test"\n[permissions]\n{permissions}\n'
    return load_config(write_config(tmp_path, text), environ={})


def problems(tmp_path: Path, permissions: str) -> tuple[ConfigProblem, ...]:
    with pytest.raises(InvalidConfigError) as raised:
        load(tmp_path, permissions)
    return raised.value.problems


class TestTheField:
    def test_without_the_field_there_is_nothing_to_add(self, tmp_path: Path) -> None:
        config = load_config(write_config(tmp_path, 'model = "fake/test"\n'), environ={})

        assert config.deny_commands == ()

    def test_an_empty_list_adds_nothing(self, tmp_path: Path) -> None:
        assert load(tmp_path, "deny_commands = []").deny_commands == ()

    def test_a_list_of_commands_is_kept_in_order_without_duplicates(self, tmp_path: Path) -> None:
        config = load(
            tmp_path,
            'deny_commands = ["terraform destroy", "kubectl delete namespace", '
            '"terraform destroy"]',
        )

        assert config.deny_commands == ("terraform destroy", "kubectl delete namespace")

    def test_a_command_of_500_characters_is_accepted(self, tmp_path: Path) -> None:
        text = "x" * 500

        assert load(tmp_path, f'deny_commands = ["{text}"]').deny_commands == (text,)

    def test_it_is_not_part_of_the_permission_rules(self, tmp_path: Path) -> None:
        config = load(tmp_path, 'deny = ["a"]\nask = ["b"]\ndeny_commands = ["reboot"]')

        assert config.permissions == PermissionRules(deny=("a",), ask=("b",))
        assert config.deny_commands == ("reboot",)

    def test_the_default_of_the_dataclass_is_empty(self) -> None:
        config = HarnessConfig(
            model="fake/test",
            limits=Limits(),
            paths=Paths(workspace_root=None, sessions_db=Path("x.db").resolve()),
            source=Path("config.toml").resolve(),
        )

        assert config.deny_commands == ()


class TestAnInvalidValue:
    @pytest.mark.parametrize(
        "value",
        [
            f'"{SENTINEL}"',
            "[1]",
            '[""]',
            '["   "]',
            f'["{"x" * 501}"]',
            f'["{SENTINEL}\\n reboot"]',
            f'["{SENTINEL}\\u0000"]',
            "true",
            "{ a = 1 }",
        ],
    )
    def test_it_is_rejected_without_repeating_the_value(self, tmp_path: Path, value: str) -> None:
        (problem,) = problems(tmp_path, f"deny_commands = {value}")

        assert problem == ConfigProblem("permissions.deny_commands", NOT_A_COMMAND_LIST)
        assert SENTINEL not in problem.message

    def test_it_is_reported_with_the_other_problems(self, tmp_path: Path) -> None:
        found = problems(tmp_path, 'deny = [1]\ndeny_commands = [""]')

        assert {problem.field for problem in found} == {
            "permissions.deny",
            "permissions.deny_commands",
        }


class TestTheBaseCannotBeRemoved:
    @pytest.mark.parametrize(
        "field",
        ["allow_commands", "replace", "base", "deny_commands_base", "allow"],
    )
    def test_a_field_to_remove_or_replace_the_base_stops_the_start(
        self, tmp_path: Path, field: str
    ) -> None:
        found = problems(tmp_path, f"{field} = []")

        assert ConfigProblem(f"permissions.{field}", UNKNOWN) in found


def test_the_template_shows_the_field_commented_under_permissions() -> None:
    lines = (ROOT / "config.example.toml").read_text(encoding="utf-8").splitlines()

    index = lines.index("# deny_commands = []")
    assert lines.index("# [permissions]") < index
    explanation = " ".join(lines[index - 3 : index]).lower()
    assert "añade" in explanation
    assert "comando real" in explanation
