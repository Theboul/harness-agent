"""HU-05-07 with the real composition, loop and policy chain (T006).

The shell is a recording double that runs nothing. AC-01: with the read-only mode on, a write or a
command that writes is denied (nothing reaches the shell or the disk); the reads (files, git
reads) still work; without the mode a write is asked as before.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.bootstrap import Composition
from harness_agent.core import ProviderResponse, Role, ToolCall, parse_task
from tests.doubles import FakeProvider
from tests.integration.test_command_policy_agent_loop import RecordingShell
from tests.unit.bootstrap_support import build, make_config

DENIED = "[permission_denied]"
ASKED = "[approval_required_unavailable]"


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class Run:
    def __init__(
        self,
        tmp_path: Path,
        opened: list[Composition],
        monkeypatch: pytest.MonkeyPatch,
        calls: list[tuple[str, dict[str, Any]]],
        *,
        read_only: bool = True,
        **options: Any,
    ) -> None:
        self.shell = RecordingShell("bash")
        monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: self.shell)
        self.workspace = tmp_path / "trabajo"
        self.workspace.mkdir(exist_ok=True)
        (self.workspace / "datos.txt").write_text("contenido", encoding="utf-8")
        script = [
            ProviderResponse(tool_calls=[ToolCall(id=f"c{i}", name=name, arguments=arguments)])
            for i, (name, arguments) in enumerate(calls)
        ]
        script.append(ProviderResponse(content="listo"))
        self.composition = build(
            opened,
            make_config(tmp_path, workspace=self.workspace),
            FakeProvider(script),
            system_name="Linux",
            read_only=read_only,
            **options,
        )

    async def answers(self) -> list[str]:
        result = await self.composition.loop.run_turn(
            session_id=self.composition.session_id, task="explora", history=[]
        )
        return [str(m.content) for m in result.history if m.role is Role.TOOL]


def shell(command: str) -> tuple[str, dict[str, Any]]:
    return ("shell", {"command": command})


async def test_ac_01_a_write_is_denied_and_nothing_is_written(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    run = Run(
        tmp_path,
        opened,
        monkeypatch,
        [("escribir_archivo", {"path": "nuevo.txt", "content": "x"})],
    )

    (answer,) = await run.answers()

    assert answer.startswith(DENIED)
    assert not (run.workspace / "nuevo.txt").exists()


@pytest.mark.parametrize(
    "command",
    ["git commit -m x", "git push origin main", "rm datos.txt", "echo a > datos.txt", "ls", "$(x)"],
)
async def test_ac_01_a_command_that_is_not_a_git_read_is_denied(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    run = Run(tmp_path, opened, monkeypatch, [shell(command)])

    (answer,) = await run.answers()

    assert answer.startswith(DENIED)
    assert run.shell.commands == []


async def test_the_reads_still_work(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    run = Run(
        tmp_path,
        opened,
        monkeypatch,
        [
            ("leer_archivo", {"path": "datos.txt"}),
            ("listar_archivos", {"path": "."}),
            shell("git status"),
            shell("git log --oneline"),
        ],
    )

    answers = await run.answers()

    assert "contenido" in answers[0]
    assert not any(answer.startswith(DENIED) for answer in answers)
    assert run.shell.commands == ["git status", "git log --oneline"]


async def test_an_unknown_tool_is_not_run(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    run = Run(tmp_path, opened, monkeypatch, [("herramienta_mcp", {})])

    (answer,) = await run.answers()

    assert answer.startswith(("[unknown_tool]", DENIED))


async def test_the_declared_commands_of_a_task_do_not_get_around_the_mode(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    task = parse_task(
        "# T-1\n## Objetivo\nProbar\n## Criterios de aceptación\n- Pasa\n"
        "## Comandos\n- pruebas: pytest -q\n"
    )
    run = Run(tmp_path, opened, monkeypatch, [shell("pytest -q")], task=task)

    (answer,) = await run.answers()

    assert answer.startswith(DENIED)
    assert run.shell.commands == []


async def test_without_the_mode_a_write_is_asked_as_before(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    run = Run(
        tmp_path,
        opened,
        monkeypatch,
        [("escribir_archivo", {"path": "nuevo.txt", "content": "x"})],
        read_only=False,
    )

    (answer,) = await run.answers()

    assert not answer.startswith(DENIED)
