"""Composition root (HU-01-04 / T014): the shell, its tool, its environment and the prefix.

``compose`` picks the shell for the system, hands it the work folder and an environment without
the provider keys, registers the ``shell`` tool and builds the environment notice that opens every
conversation. Spies replace ``select_shell`` and ``ShellTool`` to observe the wiring; the provider
is an injected ``FakeProvider`` and nothing runs a real command.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.system import environment_notice, interpreter_for
from harness_agent.bootstrap import Composition, compose, main, run_session
from harness_agent.config import PROVIDER_KEY_VARIABLES
from harness_agent.core import ProviderResponse, Role, ToolCall
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import SENTINEL, build, make_config, scripted
from tests.unit.test_bootstrap_main import write_toml

KEY_NAMES = {name for name in PROVIDER_KEY_VARIABLES.values() if name}


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class Spies:
    """Records what ``compose`` passes to ``select_shell`` and to ``ShellTool``."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.shell_calls: list[tuple[str, dict[str, Any]]] = []
        self.shells: list[Any] = []
        self.tool_args: list[tuple[Any, Any, Any]] = []
        real_select = getattr(bootstrap, "select_shell")
        real_tool = getattr(bootstrap, "ShellTool")

        def select(system_name: str, **kwargs: Any) -> Any:
            self.shell_calls.append((system_name, kwargs))
            shell = real_select(system_name, **kwargs)
            self.shells.append(shell)
            return shell

        def tool(shell: Any, area: Any, on_cancel: Any = None) -> Any:
            self.tool_args.append((shell, area, on_cancel))
            return real_tool(shell, area, on_cancel)

        monkeypatch.setattr(bootstrap, "select_shell", select)
        monkeypatch.setattr(bootstrap, "ShellTool", tool)


@pytest.fixture
def spies(monkeypatch: pytest.MonkeyPatch) -> Spies:
    return Spies(monkeypatch)


class TestTheShell:
    def test_the_shell_starts_in_the_work_folder_with_the_injected_environment(
        self, tmp_path: Path, opened: list[Composition], spies: Spies
    ) -> None:
        environ = {"PATH": "/bin", "OPENAI_API_KEY": SENTINEL, "OTRA": "1"}

        build(
            opened, make_config(tmp_path, workspace=tmp_path), environ=environ, system_name="Linux"
        )

        system_name, kwargs = spies.shell_calls[0]
        assert system_name == "Linux"
        assert kwargs["cwd"] == spies.tool_args[0][1].root
        assert kwargs["environ"] == environ

    def test_the_names_to_remove_are_the_provider_key_variables_without_none(
        self, tmp_path: Path, opened: list[Composition], spies: Spies
    ) -> None:
        build(opened, make_config(tmp_path, workspace=tmp_path), environ={}, system_name="Linux")

        removed = spies.shell_calls[0][1]["removed_env"]
        assert set(removed) == KEY_NAMES
        assert None not in removed
        assert "" not in removed

    def test_the_tool_receives_the_shell_area_and_the_cancel_hook(
        self, tmp_path: Path, opened: list[Composition], spies: Spies
    ) -> None:
        build(opened, make_config(tmp_path, workspace=tmp_path), environ={}, system_name="Linux")

        shell, area, on_cancel = spies.tool_args[0]
        assert shell is spies.shells[0]
        assert area is not None
        assert on_cancel == shell.terminate_running

    def test_without_a_work_area_the_tool_is_still_registered_but_has_no_shell(
        self, tmp_path: Path, opened: list[Composition], spies: Spies
    ) -> None:
        build(opened, make_config(tmp_path, workspace=None), environ={}, system_name="Linux")

        assert spies.shell_calls == []
        assert spies.tool_args == [(None, None, None)]

    def test_the_real_environment_is_the_default(
        self,
        tmp_path: Path,
        opened: list[Composition],
        spies: Spies,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("VARIABLE_CENTINELA", "presente")

        build(opened, make_config(tmp_path, workspace=tmp_path), system_name="Linux")

        assert spies.shell_calls[0][1]["environ"]["VARIABLE_CENTINELA"] == "presente"

    def test_the_running_system_is_the_default(
        self, tmp_path: Path, opened: list[Composition], spies: Spies
    ) -> None:
        import platform

        build(opened, make_config(tmp_path, workspace=tmp_path), environ={})

        assert spies.shell_calls[0][0] == platform.system()

    async def test_a_call_to_shell_is_asked_and_denied_without_an_approver(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        marker = tmp_path / "creado.txt"
        provider = FakeProvider(
            [
                ProviderResponse(
                    tool_calls=[
                        ToolCall(id="c1", name="shell", arguments={"command": f"echo > {marker}"})
                    ]
                ),
                ProviderResponse(content="listo"),
            ]
        )
        composition = build(opened, make_config(tmp_path, workspace=tmp_path), provider, environ={})

        await composition.loop.run_turn(session_id=composition.session_id, task="corre", history=[])

        answers = [m.content for m in provider.received[1] if m.role is Role.TOOL]
        assert any("approval_required_unavailable" in text for text in answers)
        assert not marker.exists()


class TestThePrefix:
    def test_it_is_one_system_message_with_the_environment_notice(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(
            opened,
            make_config(tmp_path, workspace=tmp_path),
            environ={},
            system_name="Windows",
        )

        assert len(composition.history_prefix) == 1
        message = composition.history_prefix[0]
        assert message.role is Role.SYSTEM
        assert message.content == environment_notice("Windows", interpreter_for("Windows"))

    def test_it_exists_even_without_a_work_area(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(
            opened, make_config(tmp_path, workspace=None), environ={}, system_name="Linux"
        )

        assert composition.history_prefix[0].content == environment_notice("Linux", "bash")

    async def test_every_conversation_starts_with_it_and_it_does_not_change(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = scripted("uno", "dos")
        composition = build(
            opened,
            make_config(tmp_path, workspace=tmp_path),
            provider,
            environ={},
            system_name="Linux",
        )
        before = composition.history_prefix

        await run_session(
            composition, input_stream=io.StringIO("a\nb\n/salir\n"), output=io.StringIO()
        )

        notice = environment_notice("Linux", "bash")
        assert [m.content for m in provider.received[0]][0] == notice
        assert [m.content for m in provider.received[1]][0] == notice
        assert provider.received[0][0].role is Role.SYSTEM
        assert composition.history_prefix == before
        assert len(composition.history_prefix) == 1


class TestMain:
    def test_main_hands_its_environment_to_compose(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: dict[str, Any] = {}
        real = bootstrap.compose

        def spy(config: Any, **kwargs: Any) -> Composition:
            seen.update(kwargs)
            return real(config, **kwargs)

        monkeypatch.setattr(bootstrap, "compose", spy)
        environ = {"OPENAI_API_KEY": SENTINEL, "PROPIA": "si"}

        code = main(
            environ=environ,
            config_path=write_toml(tmp_path, workspace=tmp_path),
            input_stream=io.StringIO("/salir\n"),
            output=io.StringIO(),
            error=io.StringIO(),
            provider_factory=lambda _config: scripted("x"),
        )

        assert code == 0
        assert seen["environ"] == environ


def test_compose_accepts_no_environment_and_still_builds(tmp_path: Path) -> None:
    composition = compose(
        make_config(tmp_path, workspace=tmp_path), provider_factory=lambda _config: scripted("x")
    )
    try:
        assert len(composition.history_prefix) == 1
    finally:
        composition.close()
