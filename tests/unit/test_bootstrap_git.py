"""Composition root (HU-11-02 / T006): git rules in the chain, ``.git`` protected, instructions.

``compose()`` puts ``GitPolicy`` between ``CommandPolicy`` and ``ExactCallPolicy``, adds the
``.git`` folder of the work area to the protected folders (as data, without changing the code of
the protected area) and adds the git instructions to the prefix when there is a work area. Checked
by behaviour through the loop.

Safety: without a work area there is no shell at all; with one, ``select_shell`` is replaced by a
recording double, so no command ever runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.bootstrap import Composition
from harness_agent.core import (
    PermissionRules,
    ProviderResponse,
    Role,
    ToolCall,
    commands_notice,
    git_instructions,
    parse_task,
)
from tests.doubles import FakeProvider
from tests.integration.test_command_policy_agent_loop import RecordingShell
from tests.unit.bootstrap_support import build, make_config, one_turn

DENIED = "[permission_denied]"
ASKED = "[approval_required_unavailable]"
NO_AREA = "[sin_area]"
RAN = "Código de salida: 0"


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def calls(*items: tuple[str, dict[str, Any]]) -> FakeProvider:
    script = [
        ProviderResponse(tool_calls=[ToolCall(id=f"c{i}", name=name, arguments=arguments)])
        for i, (name, arguments) in enumerate(items)
    ]
    return FakeProvider([*script, ProviderResponse(content="listo")])


async def answers(composition: Composition) -> list[str]:
    result = await one_turn(composition)
    return [str(m.content) for m in result.history if m.role is Role.TOOL]


class TestWithoutAWorkArea:
    """No shell at all: the policy decides, and nothing can run."""

    async def test_reads_are_allowed_writes_asked_and_destructive_denied(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = calls(
            ("shell", {"command": "git status"}),
            ("shell", {"command": "git push origin main"}),
            ("shell", {"command": "git reset --hard"}),
        )
        composition = build(opened, make_config(tmp_path), provider, system_name="Linux")

        read, write, destructive = await answers(composition)

        assert read.startswith(NO_AREA)  # allowed by the policy; the tool has no area
        assert write.startswith(ASKED)
        assert destructive.startswith(DENIED)

    async def test_the_prefix_has_no_git_instructions(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path), system_name="Linux")

        assert [m.content for m in composition.history_prefix if "git" in m.content] == []


class TestWithAWorkArea:
    @pytest.fixture
    def shell(self, monkeypatch: pytest.MonkeyPatch) -> RecordingShell:
        double = RecordingShell("bash")
        monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: double)
        return double

    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Path:
        folder = tmp_path / "trabajo"
        (folder / ".git").mkdir(parents=True)
        (folder / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (folder / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        return folder

    async def test_git_folder_cannot_be_read_or_written_but_git_status_runs(
        self,
        tmp_path: Path,
        opened: list[Composition],
        shell: RecordingShell,
        workspace: Path,
    ) -> None:
        provider = calls(
            ("leer_archivo", {"path": ".git/HEAD"}),
            ("escribir_archivo", {"path": ".git/config", "content": "[core]\n"}),
            ("shell", {"command": "git status"}),
            ("leer_archivo", {"path": ".gitignore"}),
        )
        config = make_config(tmp_path, workspace=workspace)
        composition = build(opened, config, provider, system_name="Linux")

        read_git, write_git, status, read_ignore = await answers(composition)

        assert read_git.startswith(DENIED)
        assert write_git.startswith(DENIED)
        assert not (workspace / ".git" / "config").exists()
        assert status.startswith(RAN)
        assert shell.commands == ["git status"]
        assert "*.pyc" in read_ignore  # only the .git folder is protected

    async def test_a_command_naming_gitignore_is_not_denied(
        self,
        tmp_path: Path,
        opened: list[Composition],
        shell: RecordingShell,
        workspace: Path,
    ) -> None:
        provider = calls(("shell", {"command": "cat .gitignore"}))
        composition = build(
            opened, make_config(tmp_path, workspace=workspace), provider, system_name="Linux"
        )

        (answer,) = await answers(composition)

        assert answer.startswith(ASKED)  # asked as any shell command, not denied

    def test_the_prefix_has_the_git_instructions_after_the_environment(
        self, tmp_path: Path, opened: list[Composition], shell: RecordingShell, workspace: Path
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=workspace), system_name="Linux")

        environment, instructions = composition.history_prefix
        assert environment.role is Role.SYSTEM and "git" not in environment.content.lower()
        assert instructions.role is Role.SYSTEM
        assert instructions.content == git_instructions()

    def test_with_task_commands_they_come_last(
        self, tmp_path: Path, opened: list[Composition], shell: RecordingShell, workspace: Path
    ) -> None:
        task = parse_task(
            "## Objetivo\nProbar.\n\n## Criterios de aceptación\n- Algo\n\n"
            "## Comandos\n- pruebas: python -m pytest\n"
        )
        composition = build(
            opened, make_config(tmp_path, workspace=workspace), task=task, system_name="Linux"
        )

        _, instructions, commands = composition.history_prefix
        assert instructions.content == git_instructions()
        assert commands.content == commands_notice(task.commands)


class TestTheChain:
    async def test_the_base_list_and_the_protected_area_still_win(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = calls(
            ("shell", {"command": "git status && reboot"}),
            ("shell", {"command": "git log sesiones.db"}),
        )
        composition = build(opened, make_config(tmp_path), provider, system_name="Linux")

        reboot, protected = await answers(composition)

        assert reboot.startswith(DENIED)
        assert protected.startswith(DENIED)

    async def test_the_ask_list_of_tools_asks_even_a_read(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        rules = PermissionRules(ask=("shell",))
        provider = calls(("shell", {"command": "git status"}))
        composition = build(
            opened, make_config(tmp_path, permissions=rules), provider, system_name="Linux"
        )

        (answer,) = await answers(composition)

        assert answer.startswith(ASKED)

    @pytest.mark.parametrize("command", ["git status", "git push origin main"])
    async def test_the_deny_list_of_tools_denies_every_git_call(
        self, tmp_path: Path, opened: list[Composition], command: str
    ) -> None:
        rules = PermissionRules(deny=("shell",))
        provider = calls(("shell", {"command": command}))
        composition = build(
            opened, make_config(tmp_path, permissions=rules), provider, system_name="Linux"
        )

        (answer,) = await answers(composition)

        assert answer.startswith(DENIED)

    async def test_powershell_reads_are_allowed_too(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = calls(("shell", {"command": "git.exe log --oneline"}))
        composition = build(opened, make_config(tmp_path), provider, system_name="Windows")

        (answer,) = await answers(composition)

        assert answer.startswith(NO_AREA)
