"""``[mcp_servers.<name>]``: the MCP servers the harness connects to (HU-08-01 / FR-008).

An additive section of the HU-00-04 schema. Without it nothing changes. The ``env`` field lists
the **names** of the variables of the parent environment that the server receives, never values,
so the file holds no secret; a field that looks like a key is rejected as everywhere else.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import (
    ConfigProblem,
    HarnessConfig,
    InvalidConfigError,
    McpServerConfig,
    SecretInConfigFileError,
    load_config,
)
from tests.unit.config_support import SENTINEL, toml_with_field, write_config

HEADER = 'model = "fake/test"\n'
NOT_A_TABLE = "debe ser una tabla."
NOT_A_COMMAND = "debe ser un texto no vacío de una sola línea, de hasta 500 caracteres."
NOT_ARGS = "debe ser una lista de textos de una sola línea, de hasta 500 caracteres cada uno."
NOT_NAMES = "debe ser una lista de nombres de variables de entorno (letras, números y _)."
NOT_A_TIMEOUT = "debe ser un número mayor que 0 y de hasta {maximum} segundos."
MISSING = "falta el campo obligatorio."
UNKNOWN = "campo desconocido en el esquema."


def load(tmp_path: Path, body: str) -> HarnessConfig:
    return load_config(write_config(tmp_path, HEADER + body), environ={})


def problems(tmp_path: Path, body: str) -> tuple[ConfigProblem, ...]:
    with pytest.raises(InvalidConfigError) as raised:
        load(tmp_path, body)
    return raised.value.problems


class TestTheSection:
    def test_without_the_section_there_are_no_servers(self, tmp_path: Path) -> None:
        assert load(tmp_path, "").mcp_servers == ()

    def test_an_empty_section_has_no_servers_either(self, tmp_path: Path) -> None:
        assert load(tmp_path, "[mcp_servers]\n").mcp_servers == ()

    def test_a_server_with_only_the_command_gets_the_defaults(self, tmp_path: Path) -> None:
        config = load(tmp_path, '[mcp_servers.demo]\ncommand = "python"\n')

        assert config.mcp_servers == (
            McpServerConfig(
                name="demo",
                command="python",
                args=(),
                env=(),
                startup_timeout_s=15.0,
                call_timeout_s=60.0,
            ),
        )

    def test_every_field_is_read_and_servers_keep_the_order_of_the_file(
        self, tmp_path: Path
    ) -> None:
        body = (
            '[mcp_servers.primero]\ncommand = "python"\nargs = ["a.py", "--x"]\n'
            'env = ["EXTRA", "OTRA_1"]\nstartup_timeout_s = 20\ncall_timeout_s = 7.5\n'
            '[mcp_servers.segundo]\ncommand = "node"\n'
        )

        first, second = load(tmp_path, body).mcp_servers

        assert first == McpServerConfig(
            name="primero",
            command="python",
            args=("a.py", "--x"),
            env=("EXTRA", "OTRA_1"),
            startup_timeout_s=20.0,
            call_timeout_s=7.5,
        )
        assert second.name == "segundo"

    def test_repeated_environment_names_are_dropped(self, tmp_path: Path) -> None:
        config = load(tmp_path, '[mcp_servers.s]\ncommand = "x"\nenv = ["A", "B", "A"]\n')

        assert config.mcp_servers[0].env == ("A", "B")

    def test_a_variable_that_names_a_key_is_allowed_because_it_is_only_a_name(
        self, tmp_path: Path
    ) -> None:
        names = "OPENAI_API_" + "KEY"

        config = load(tmp_path, f'[mcp_servers.s]\ncommand = "x"\nenv = ["{names}"]\n')

        assert config.mcp_servers[0].env == (names,)


class TestInvalidValues:
    def test_the_command_is_required(self, tmp_path: Path) -> None:
        found = problems(tmp_path, "[mcp_servers.demo]\nargs = []\n")

        assert found == (ConfigProblem("mcp_servers.demo.command", MISSING),)

    @pytest.mark.parametrize("value", ['""', "5", '"a\\nb"', '"' + "x" * 501 + '"', "[]"])
    def test_a_bad_command(self, tmp_path: Path, value: str) -> None:
        found = problems(tmp_path, f"[mcp_servers.demo]\ncommand = {value}\n")

        assert found == (ConfigProblem("mcp_servers.demo.command", NOT_A_COMMAND),)

    @pytest.mark.parametrize("value", ['"a"', "[1]", '["a\\nb"]', '["' + "x" * 501 + '"]'])
    def test_bad_arguments(self, tmp_path: Path, value: str) -> None:
        found = problems(tmp_path, f'[mcp_servers.demo]\ncommand = "x"\nargs = {value}\n')

        assert found == (ConfigProblem("mcp_servers.demo.args", NOT_ARGS),)

    @pytest.mark.parametrize("value", ['"A"', '["1ABC"]', '["A B"]', '["A=B"]', '[""]', "[1]"])
    def test_bad_environment_names(self, tmp_path: Path, value: str) -> None:
        found = problems(tmp_path, f'[mcp_servers.demo]\ncommand = "x"\nenv = {value}\n')

        assert found == (ConfigProblem("mcp_servers.demo.env", NOT_NAMES),)

    @pytest.mark.parametrize("value", ["0", "-1", '"15"', "true", "301"])
    def test_a_bad_startup_timeout(self, tmp_path: Path, value: str) -> None:
        found = problems(
            tmp_path, f'[mcp_servers.demo]\ncommand = "x"\nstartup_timeout_s = {value}\n'
        )

        assert found == (
            ConfigProblem("mcp_servers.demo.startup_timeout_s", NOT_A_TIMEOUT.format(maximum=300)),
        )

    @pytest.mark.parametrize("value", ["0", "-1", '"60"', "false", "3601"])
    def test_a_bad_call_timeout(self, tmp_path: Path, value: str) -> None:
        found = problems(tmp_path, f'[mcp_servers.demo]\ncommand = "x"\ncall_timeout_s = {value}\n')

        assert found == (
            ConfigProblem("mcp_servers.demo.call_timeout_s", NOT_A_TIMEOUT.format(maximum=3600)),
        )

    def test_the_section_must_be_a_table(self, tmp_path: Path) -> None:
        found = problems(tmp_path, 'mcp_servers = "python"\n')

        assert found == (ConfigProblem("mcp_servers", NOT_A_TABLE),)

    def test_a_server_must_be_a_table(self, tmp_path: Path) -> None:
        found = problems(tmp_path, '[mcp_servers]\ndemo = "python"\n')

        assert found == (ConfigProblem("mcp_servers.demo", NOT_A_TABLE),)

    @pytest.mark.parametrize("name", ["con espacio", "a.b", "x" * 33])
    def test_a_bad_server_name(self, tmp_path: Path, name: str) -> None:
        found = problems(tmp_path, f'[mcp_servers."{name}"]\ncommand = "x"\n')

        assert len(found) == 1
        assert found[0].message == (
            "el nombre debe tener de 1 a 32 caracteres: letras, números, _ y -."
        )

    def test_an_unknown_field_is_reported_by_name(self, tmp_path: Path) -> None:
        found = problems(tmp_path, '[mcp_servers.demo]\ncommand = "x"\ncwd = "."\n')

        assert found == (ConfigProblem("mcp_servers.demo.cwd", UNKNOWN),)

    def test_no_message_shows_the_value_it_received(self, tmp_path: Path) -> None:
        body = (
            f'[mcp_servers.demo]\ncommand = ""\nargs = ["{SENTINEL}\\n"]\n'
            f'env = ["{SENTINEL} x"]\nstartup_timeout_s = "{SENTINEL}"\n'
        )

        with pytest.raises(InvalidConfigError) as raised:
            load(tmp_path, body)

        assert SENTINEL not in str(raised.value)


class TestNoSecretsInTheFile:
    def test_a_field_that_looks_like_a_key_is_rejected_as_everywhere_else(
        self, tmp_path: Path
    ) -> None:
        body = '[mcp_servers.demo]\ncommand = "x"\n' + toml_with_field("api_" + "key")

        with pytest.raises(SecretInConfigFileError) as raised:
            load(tmp_path, body)

        assert SENTINEL not in str(raised.value)
        assert "mcp_servers.demo.api_key" in str(raised.value)

    def test_a_table_inside_a_server_with_a_key_like_name_is_rejected_too(
        self, tmp_path: Path
    ) -> None:
        body = '[mcp_servers.demo]\ncommand = "x"\n[mcp_servers.demo.' + "pass" + 'word]\nx = "y"\n'

        with pytest.raises(SecretInConfigFileError):
            load(tmp_path, body)

    def test_a_server_named_like_a_key_is_rejected(self, tmp_path: Path) -> None:
        body = "[mcp_servers.my-" + "to" + 'ken]\ncommand = "x"\n'

        with pytest.raises(SecretInConfigFileError):
            load(tmp_path, body)
