"""Composition root (HU-05-02 / T009): the deny list is compiled and put in the policy chain.

``compose()`` compiles the base list of the chosen interpreter and ``[permissions] deny_commands``
and builds ``ProtectedPolicy(CommandPolicy(ExactCallPolicy(DefaultPermissionPolicy)))``. The
order is checked by behaviour, not by looking at private attributes.

Safety: these compositions have **no work area**, so there is no shell and the ``shell`` tool can
never run anything; a denied command is only evaluated by the policy. A dangerous command is never
executed, not even while a test is red.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent.bootstrap import EXIT_STARTUP, Composition, main
from harness_agent.config import HarnessConfig
from harness_agent.core import PermissionRules, ProviderResponse, Role, ToolCall
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import SENTINEL, build, make_config, one_turn, scripted

DENIED = "[permission_denied]"
KEY = "clave-de-prueba"
ASKED = "[approval_required_unavailable]"


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def call_once(name: str, arguments: dict[str, Any]) -> FakeProvider:
    return FakeProvider(
        [
            ProviderResponse(tool_calls=[ToolCall(id="c1", name=name, arguments=arguments)]),
            ProviderResponse(content="listo"),
        ]
    )


def with_deny_commands(config: HarnessConfig, *commands: str) -> HarnessConfig:
    return HarnessConfig(
        model=config.model,
        limits=config.limits,
        paths=config.paths,
        source=config.source,
        api_key=config.api_key,
        permissions=config.permissions,
        deny_commands=commands,
    )


async def answer(
    tmp_path: Path,
    opened: list[Composition],
    command: str,
    *,
    system: str = "Linux",
    deny_commands: tuple[str, ...] = (),
    rules: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
    tool: str = "shell",
) -> str:
    config = with_deny_commands(make_config(tmp_path, permissions=rules), *deny_commands)
    assert config.paths.workspace_root is None  # no shell: nothing can run
    arguments = {"command": command} if tool == "shell" else {"path": command}
    composition = build(opened, config, call_once(tool, arguments), system_name=system)
    result = await one_turn(composition)
    return str([m for m in result.history if m.role is Role.TOOL][0].content)


@pytest.mark.parametrize(
    ("system", "command"),
    [
        ("Linux", "shutdown now"),
        ("Linux", "echo hola && rm -rf /"),
        ("Linux", "sudo /sbin/reboot"),
        ("Linux", "echo $(halt)"),
        ("Windows", "Stop-Computer"),
        ("Windows", "dir | Format-Volume -DriveLetter D"),
        ("Windows", "ri -r -fo C:\\"),
    ],
)
async def test_a_command_of_the_base_list_is_denied(
    tmp_path: Path, opened: list[Composition], system: str, command: str
) -> None:
    assert (await answer(tmp_path, opened, command, system=system)).startswith(DENIED)


async def test_the_list_follows_the_interpreter_of_the_system(
    tmp_path: Path, opened: list[Composition]
) -> None:
    # Stop-Computer is in the PowerShell list only; with bash it is just an unknown program.
    assert (await answer(tmp_path, opened, "Stop-Computer", system="Linux")).startswith(ASKED)


async def test_a_command_added_by_the_configuration_is_denied(
    tmp_path: Path, opened: list[Composition]
) -> None:
    text = await answer(
        tmp_path,
        opened,
        "ls && terraform destroy -auto-approve",
        deny_commands=("terraform destroy",),
    )

    assert text.startswith(DENIED)


async def test_an_empty_configuration_keeps_the_base(
    tmp_path: Path, opened: list[Composition]
) -> None:
    assert (await answer(tmp_path, opened, "reboot", deny_commands=())).startswith(DENIED)


async def test_a_usual_command_is_still_asked(tmp_path: Path, opened: list[Composition]) -> None:
    assert (await answer(tmp_path, opened, "python -m pytest -q")).startswith(ASKED)


async def test_the_deny_list_of_tools_still_denies_the_shell(
    tmp_path: Path, opened: list[Composition]
) -> None:
    text = await answer(tmp_path, opened, "ls", rules=PermissionRules(deny=("shell",)))

    assert text.startswith(DENIED)


async def test_a_denied_command_wins_over_the_ask_list(
    tmp_path: Path, opened: list[Composition]
) -> None:
    rules = PermissionRules(ask=("shell",))

    assert (await answer(tmp_path, opened, "reboot", rules=rules)).startswith(DENIED)
    assert (await answer(tmp_path, opened, "ls", rules=rules)).startswith(ASKED)


async def test_the_file_tools_are_decided_as_before(
    tmp_path: Path, opened: list[Composition]
) -> None:
    # Without a work area a read is asked (HU-05-01); the deny list does not touch other tools.
    text = await answer(tmp_path, opened, "shutdown", tool="leer_archivo")

    assert text.startswith(ASKED)


def write_config(tmp_path: Path, deny_commands: str) -> Path:
    path = tmp_path / "config.toml"
    database = (tmp_path / "datos" / "sesiones.db").as_posix()
    path.write_text(
        'model = "openai/modelo-de-prueba"\n'
        f'[paths]\nsessions_db = "{database}"\n'
        f"[permissions]\ndeny_commands = {deny_commands}\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "entry",
    [f'"echo $({SENTINEL})"', f'"a {SENTINEL} && b"', f'"echo {SENTINEL} > x"'],
)
def test_an_entry_that_is_not_understood_stops_the_start(tmp_path: Path, entry: str) -> None:
    error = io.StringIO()

    code = main(
        environ={"OPENAI_API_KEY": KEY},
        config_path=write_config(tmp_path, f"[{entry}]"),
        input_stream=io.StringIO("/salir\n"),
        output=io.StringIO(),
        error=error,
        provider_factory=lambda _config: scripted("listo"),
    )

    assert code == EXIT_STARTUP
    line = error.getvalue()
    assert line.startswith("No se pudo iniciar: ")
    assert "permissions.deny_commands" in line
    assert "no se entiende" in line
    assert SENTINEL not in line


def test_a_valid_entry_lets_the_start_go_on(tmp_path: Path) -> None:
    code = main(
        environ={"OPENAI_API_KEY": KEY},
        config_path=write_config(tmp_path, '["terraform destroy"]'),
        input_stream=io.StringIO("/salir\n"),
        output=io.StringIO(),
        error=io.StringIO(),
        provider_factory=lambda _config: scripted("listo"),
    )

    assert code == 0
