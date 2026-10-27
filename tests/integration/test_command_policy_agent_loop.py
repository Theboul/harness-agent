"""HU-05-02 with the real composition: deny list, approvals, protection and task commands (T010).

``compose()`` builds the real loop, registry, ``ShellTool`` and the whole policy chain
``ProtectedPolicy(CommandPolicy(ExactCallPolicy(DefaultPermissionPolicy)))``. Only the shell is
replaced: ``select_shell`` returns a **recording double**, so no command ever reaches a real
interpreter (not even while a test is red) and both dialects are checked on any system. A denied
command must never reach the double.

* AC-02: with the real ``ApprovalGate`` and a session approval already given, a denied command is
  still denied and the approver is not asked.
* Composition: protected area, ``deny`` and ``ask`` lists of tools, the exact commands of a task
  (HU-11-03) and the chained examples of Sp2-28.
* No data leaks: neither events nor tool results carry the command.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.bootstrap import Composition
from harness_agent.config import HarnessConfig
from harness_agent.core import (
    ApprovalAction,
    ApprovalResult,
    Approver,
    Event,
    EventType,
    PermissionRules,
    ProviderResponse,
    Role,
    Shell,
    ShellResult,
    TaskDefinition,
    ToolCall,
    parse_task,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import SENTINEL, build, make_config

DENIED = "[permission_denied]"
ASKED = "[approval_required_unavailable]"
RAN = "Código de salida: 0"
SYSTEMS = {"bash": "Linux", "powershell": "Windows"}


class RecordingShell(Shell):
    """A shell that runs nothing: it records each command and answers success."""

    def __init__(self, interpreter: str) -> None:
        self._interpreter = interpreter
        self.commands: list[str] = []

    @property
    def interpreter_name(self) -> str:
        return self._interpreter

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        self.commands.append(command)
        return ShellResult(exit_code=0, output="salida-del-doble")

    def terminate_running(self) -> None:
        """Nothing runs, so there is nothing to end."""


class SessionApprover(Approver):
    """Answers "approve for the session" to everything and counts the questions."""

    def __init__(self) -> None:
        self.questions: list[ToolCall] = []

    async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
        self.questions.append(call)
        return ApprovalResult(action=ApprovalAction.APPROVE_SESSION)


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class Run:
    """One composed system with the recording shell; one turn per ``turn()``."""

    def __init__(
        self,
        tmp_path: Path,
        opened: list[Composition],
        monkeypatch: pytest.MonkeyPatch,
        interpreter: str,
        commands: list[str],
        *,
        approver: Approver | None = None,
        rules: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
        task: TaskDefinition | None = None,
    ) -> None:
        self.shell = RecordingShell(interpreter)
        monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: self.shell)
        workspace = tmp_path / "trabajo"
        workspace.mkdir(exist_ok=True)
        config: HarnessConfig = make_config(tmp_path, workspace=workspace, permissions=rules)
        script: list[ProviderResponse] = []
        for index, command in enumerate(commands):
            call = ToolCall(id=f"c{index}", name="shell", arguments={"command": command})
            script.append(ProviderResponse(tool_calls=[call]))
        script.append(ProviderResponse(content="listo"))
        self.composition = build(
            opened,
            config,
            FakeProvider(script),
            system_name=SYSTEMS[interpreter],
            approver=approver,
            task=task,
        )
        self.events: list[Event] = []
        for event_type in EventType:
            self.composition.bus.subscribe(event_type, self.events.append)
        self.workspace = workspace

    async def answers(self) -> list[str]:
        result = await self.composition.loop.run_turn(
            session_id=self.composition.session_id, task="trabaja", history=[]
        )
        return [str(m.content) for m in result.history if m.role is Role.TOOL]


# --- AC-02: a session approval never lets a denied command run ------------------------------------

AC02 = {
    "bash": ("ls -la", "reboot", f"ls -la; echo {SENTINEL} > marcador.txt; reboot"),
    "powershell": ("dir", "Stop-Computer", f"dir; echo {SENTINEL} > marcador.txt; Stop-Computer"),
}


@pytest.mark.parametrize("interpreter", ["bash", "powershell"])
async def test_ac_02_a_session_approval_does_not_override_a_denial(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, interpreter: str
) -> None:
    innocent, denied, chained = AC02[interpreter]
    approver = SessionApprover()
    run = Run(
        tmp_path,
        opened,
        monkeypatch,
        interpreter,
        [innocent, chained, denied, denied, innocent],
        approver=approver,
    )

    first, with_denied, alone, again, repeated = await run.answers()

    assert first.startswith(RAN)  # asked once, approved for the session
    assert with_denied.startswith(DENIED)
    assert alone.startswith(DENIED)
    assert again.startswith(DENIED)
    assert repeated.startswith(RAN)  # the session approval is still alive
    assert [call.arguments["command"] for call in approver.questions] == [innocent]
    assert run.shell.commands == [innocent, innocent]
    assert not (run.workspace / "marcador.txt").exists()


# --- the whole chain of policies ------------------------------------------------------------------


async def test_the_protected_area_wins(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    approver = SessionApprover()
    run = Run(tmp_path, opened, monkeypatch, "bash", ["echo sesiones.db"], approver=approver)

    (answer,) = await run.answers()

    assert answer.startswith(DENIED)
    assert approver.questions == []
    assert run.shell.commands == []


async def test_the_deny_list_of_tools_denies_the_shell(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rules = PermissionRules(deny=("shell",))
    run = Run(tmp_path, opened, monkeypatch, "bash", ["ls"], rules=rules)

    (answer,) = await run.answers()

    assert answer.startswith(DENIED)
    assert run.shell.commands == []


async def test_the_ask_list_asks_and_a_denied_command_still_wins(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rules = PermissionRules(ask=("shell",))
    run = Run(tmp_path, opened, monkeypatch, "bash", ["ls", "ls && reboot"], rules=rules)

    asked, denied = await run.answers()

    assert asked.startswith(ASKED)
    assert denied.startswith(DENIED)
    assert run.shell.commands == []


def task_with(*lines: str) -> TaskDefinition:
    commands = "\n".join(lines)
    return parse_task(
        "## Objetivo\nProbar.\n\n## Criterios de aceptación\n- Algo pasa\n\n"
        f"## Comandos\n{commands}\n"
    )


async def test_an_exact_task_command_that_is_understood_runs_without_asking(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    task = task_with("- pruebas: python -m pytest -q")
    run = Run(tmp_path, opened, monkeypatch, "bash", ["python -m pytest -q"], task=task)

    (answer,) = await run.answers()

    assert answer.startswith(RAN)
    assert run.shell.commands == ["python -m pytest -q"]


async def test_a_declared_command_that_is_not_understood_is_asked(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    task = task_with("- pruebas: echo $(whoami)")
    run = Run(tmp_path, opened, monkeypatch, "bash", ["echo $(whoami)"], task=task)

    (answer,) = await run.answers()

    assert answer.startswith(ASKED)
    assert run.shell.commands == []


async def test_a_declared_command_that_holds_a_denied_one_is_denied(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    task = task_with("- pruebas: python -m pytest && reboot")
    run = Run(tmp_path, opened, monkeypatch, "bash", ["python -m pytest && reboot"], task=task)

    (answer,) = await run.answers()

    assert answer.startswith(DENIED)
    assert run.shell.commands == []


# --- no data leaks --------------------------------------------------------------------------------


@pytest.mark.parametrize("interpreter", ["bash", "powershell"])
async def test_neither_events_nor_results_carry_the_denied_command(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, interpreter: str
) -> None:
    _, _, chained = AC02[interpreter]
    run = Run(tmp_path, opened, monkeypatch, interpreter, [chained], approver=SessionApprover())

    (answer,) = await run.answers()

    assert answer.startswith(DENIED)
    assert SENTINEL not in answer
    assert all(SENTINEL not in repr(event.payload) for event in run.events)
    assert any(event.type is EventType.PERMISSION_DECIDED for event in run.events)


# --- Sp2-28: chained examples through the loop ---------------------------------------------------

CHAINED = {
    "bash": [
        ("git status && git diff", ASKED),
        ("python -m pytest || echo falló", ASKED),
        ("ls; pwd", ASKED),
        ("cat a.txt | grep x", ASKED),
        ("ls\npwd", ASKED),
        ("git status && reboot", DENIED),
        ("ls || shutdown -h now", DENIED),
        ("echo hola; rm -rf /", DENIED),
        ("cat x | sudo halt", DENIED),
        ("ls\ndd if=/dev/zero of=/dev/sda", DENIED),
        ("echo $(poweroff) && ls", DENIED),
        ('ls && bash -c "rm -rf ~"', DENIED),
        ("echo $(whoami) && ls", ASKED),
    ],
    "powershell": [
        ("git status; git diff", ASKED),
        ("Get-ChildItem | Select-Object Name", ASKED),
        ("python -m pytest || echo fallo", ASKED),
        ("dir && dir", ASKED),
        ("dir\nGet-Location", ASKED),
        ("git status; Stop-Computer", DENIED),
        ("dir | Restart-Computer", DENIED),
        ("dir && Format-Volume -DriveLetter D", DENIED),
        ("dir || ri -r -fo C:\\", DENIED),
        ("dir\nClear-Disk -Number 1", DENIED),
        ('pwsh -Command "Stop-Computer"', DENIED),
        ("echo $(Stop-Computer)", DENIED),
        ("iex 'dir'", ASKED),
    ],
}


@pytest.mark.parametrize("interpreter", ["bash", "powershell"])
async def test_chained_examples_through_the_loop(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, interpreter: str
) -> None:
    examples = CHAINED[interpreter]
    assert len(examples) >= 10
    run = Run(tmp_path, opened, monkeypatch, interpreter, [command for command, _ in examples])

    answers = await run.answers()

    for (command, expected), answer in zip(examples, answers, strict=True):
        assert answer.startswith(expected), (command, answer)
    assert run.shell.commands == []
