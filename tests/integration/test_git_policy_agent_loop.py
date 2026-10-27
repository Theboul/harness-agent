"""HU-11-02 with the real composition and a recording shell (T007).

``compose()`` builds the real loop, registry, ``ShellTool`` and the policy chain
``ProtectedPolicy(CommandPolicy(GitPolicy(ExactCallPolicy(DefaultPermissionPolicy))))``. Only the
shell is replaced: ``select_shell`` returns a double that records each command and **runs
nothing**, so no git command ever runs here (the real git test is
``test_git_real_repository.py``). Both dialects are checked on any system.

* AC-01: git reads run without an approver, and a long output comes back cut.
* AC-02: commit, push and merge are asked; reset --hard, clean and push --force are denied and
  never reach the shell.
* A task that declares ``git push`` (HU-11-03) does not let it run by itself; a session approval of
  a commit does not authorize a push; a denied push never reaches the approver.
* The protected area and the deny and ask lists still rule; ``.git`` cannot be read or written
  with the file tools while ``git status`` runs; credentials of URLs never reach the model.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.bootstrap import Composition
from harness_agent.config import Limits
from harness_agent.core import (
    Event,
    EventType,
    PermissionRules,
    ProviderResponse,
    Role,
    ShellResult,
    TaskDefinition,
    ToolCall,
    parse_task,
)
from tests.doubles import FakeProvider
from tests.integration.test_command_policy_agent_loop import RecordingShell, SessionApprover
from tests.unit.bootstrap_support import build, make_config

DENIED = "[permission_denied]"
ASKED = "[approval_required_unavailable]"
RAN = "Código de salida: 0"
OMITTED = "[salida recortada: se omitieron"
SYSTEMS = {"bash": "Linux", "powershell": "Windows"}
USER = "usuario" + "-de-prueba"
SECRET = "secreto" + "-de-prueba"


class TalkativeShell(RecordingShell):
    """A recording shell whose answer is chosen by the test; it runs nothing."""

    def __init__(self, interpreter: str, output: str) -> None:
        super().__init__(interpreter)
        self._output = output

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        self.commands.append(command)
        return ShellResult(exit_code=0, output=self._output)


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
        interpreter: str,
        calls: list[tuple[str, dict[str, Any]]],
        *,
        output: str = "salida-del-doble",
        approver: SessionApprover | None = None,
        rules: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
        task: TaskDefinition | None = None,
    ) -> None:
        self.shell = TalkativeShell(interpreter, output)
        monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: self.shell)
        self.workspace = tmp_path / "trabajo"
        (self.workspace / ".git").mkdir(parents=True, exist_ok=True)
        (self.workspace / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        script = [
            ProviderResponse(tool_calls=[ToolCall(id=f"c{i}", name=name, arguments=arguments)])
            for i, (name, arguments) in enumerate(calls)
        ]
        script.append(ProviderResponse(content="listo"))
        config = make_config(tmp_path, workspace=self.workspace, permissions=rules)
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

    async def answers(self) -> list[str]:
        result = await self.composition.loop.run_turn(
            session_id=self.composition.session_id, task="trabaja", history=[]
        )
        return [str(m.content) for m in result.history if m.role is Role.TOOL]


def shell(command: str) -> tuple[str, dict[str, Any]]:
    return ("shell", {"command": command})


INTERPRETERS = ["bash", "powershell"]


# --- AC-01 and AC-02 ------------------------------------------------------------------------------


@pytest.mark.parametrize("interpreter", INTERPRETERS)
async def test_ac_01_reads_run_without_an_approver(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, interpreter: str
) -> None:
    reads = ["git status", "git diff", "git log --oneline", "git status && git diff"]
    run = Run(tmp_path, opened, monkeypatch, interpreter, [shell(c) for c in reads])

    answers = await run.answers()

    assert all(answer.startswith(RAN) for answer in answers), answers
    assert run.shell.commands == reads


@pytest.mark.parametrize("interpreter", INTERPRETERS)
async def test_ac_01_a_long_output_comes_back_cut(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, interpreter: str
) -> None:
    long_output = "inicio\n" + "commit abc\n" * 10_000 + "fin\n"
    run = Run(tmp_path, opened, monkeypatch, interpreter, [shell("git log")], output=long_output)

    (answer,) = await run.answers()

    # The double skips the cut of the real shell (``[salida recortada: se omitieron N]``, checked
    # with real git in ``test_git_real_repository.py``); here the bound of the tool cuts it.
    assert answer.startswith(RAN)
    assert OMITTED in answer or "[resultado recortado]" in answer
    assert len(answer) <= Limits().max_tool_output_chars
    assert "fin\n" not in answer


@pytest.mark.parametrize("interpreter", INTERPRETERS)
async def test_ac_02_writes_are_asked_and_destructive_calls_denied(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, interpreter: str
) -> None:
    commands = [
        ("git commit -m mensaje", ASKED),
        ("git push origin main", ASKED),
        ("git merge rama", ASKED),
        ("git reset --hard", DENIED),
        ("git clean -fd", DENIED),
        ("git push --force", DENIED),
        ("git status && git push -f", DENIED),
    ]
    run = Run(tmp_path, opened, monkeypatch, interpreter, [shell(c) for c, _ in commands])

    answers = await run.answers()

    for (command, expected), answer in zip(commands, answers, strict=True):
        assert answer.startswith(expected), (command, answer)
    assert run.shell.commands == []


# --- nothing lets a push or a merge run by itself ------------------------------------------------


def task_declaring(command: str) -> TaskDefinition:
    return parse_task(
        "## Objetivo\nEntregar.\n\n## Criterios de aceptación\n- Entregado\n\n"
        f"## Comandos\n- pruebas: {command}\n"
    )


@pytest.mark.parametrize("command", ["git push origin main", "git merge rama"])
async def test_a_task_declaration_does_not_let_a_push_or_a_merge_run(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    run = Run(tmp_path, opened, monkeypatch, "bash", [shell(command)], task=task_declaring(command))

    (answer,) = await run.answers()

    assert answer.startswith(ASKED)
    assert run.shell.commands == []


async def test_with_an_approver_the_declared_push_is_still_a_question(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    approver = SessionApprover()
    command = "git push origin main"
    run = Run(
        tmp_path,
        opened,
        monkeypatch,
        "bash",
        [shell(command)],
        approver=approver,
        task=task_declaring(command),
    )

    (answer,) = await run.answers()

    assert [call.arguments["command"] for call in approver.questions] == [command]
    assert answer.startswith(RAN)  # it ran only because the person approved it


@pytest.mark.parametrize("interpreter", INTERPRETERS)
async def test_a_session_approval_of_a_commit_does_not_authorize_a_push(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, interpreter: str
) -> None:
    approver = SessionApprover()
    calls = [
        "git commit -m mensaje",
        "git push origin main",
        "git push origin main",
        "git push --force",
        "git commit -m mensaje",
    ]
    run = Run(
        tmp_path, opened, monkeypatch, interpreter, [shell(c) for c in calls], approver=approver
    )

    commit, push, same_push, forced, same_commit = await run.answers()

    assert [call.arguments["command"] for call in approver.questions] == [
        "git commit -m mensaje",
        "git push origin main",
    ]
    assert commit.startswith(RAN)
    assert push.startswith(RAN)  # asked and approved on its own
    assert same_push.startswith(RAN)  # the same push reuses its session approval (Q3, PO)
    assert forced.startswith(DENIED)  # a denied push never reaches the approver
    assert same_commit.startswith(RAN)
    assert "git push --force" not in run.shell.commands


# --- protected area, lists of tools, .git ---------------------------------------------------------


async def test_the_protected_area_and_the_lists_of_tools_still_rule(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    run = Run(tmp_path, opened, monkeypatch, "bash", [shell("git log sesiones.db")])

    (protected,) = await run.answers()

    assert protected.startswith(DENIED)
    assert run.shell.commands == []


@pytest.mark.parametrize(
    ("rules", "expected"),
    [
        (PermissionRules(ask=("shell",)), ASKED),
        (PermissionRules(deny=("shell",)), DENIED),
    ],
)
async def test_the_ask_and_deny_lists_rule_over_a_read(
    tmp_path: Path,
    opened: list[Composition],
    monkeypatch: pytest.MonkeyPatch,
    rules: PermissionRules,
    expected: str,
) -> None:
    run = Run(tmp_path, opened, monkeypatch, "bash", [shell("git status")], rules=rules)

    (answer,) = await run.answers()

    assert answer.startswith(expected)
    assert run.shell.commands == []


@pytest.mark.parametrize("interpreter", INTERPRETERS)
async def test_git_folder_is_closed_to_the_file_tools_but_git_status_runs(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, interpreter: str
) -> None:
    calls = [
        ("leer_archivo", {"path": ".git/HEAD"}),
        ("escribir_archivo", {"path": ".git/config", "content": "[core]\n"}),
        shell("git status"),
    ]
    run = Run(tmp_path, opened, monkeypatch, interpreter, calls)

    read, write, status = await run.answers()

    assert read.startswith(DENIED)
    assert write.startswith(DENIED)
    assert status.startswith(RAN)
    assert not (run.workspace / ".git" / "config").exists()


# --- credentials and events -----------------------------------------------------------------------


@pytest.mark.parametrize("interpreter", INTERPRETERS)
async def test_credentials_never_reach_the_model_nor_the_events(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, interpreter: str
) -> None:
    output = f"origin\thttps://{USER}:{SECRET}@servidor.example/repo.git (fetch)\n"
    run = Run(
        tmp_path,
        opened,
        monkeypatch,
        interpreter,
        [shell("git log --oneline"), shell(f"git push https://{USER}:{SECRET}@x.example/r.git")],
        output=output,
    )

    log, push = await run.answers()

    assert log.startswith(RAN)
    assert USER not in log and SECRET not in log
    assert push.startswith(ASKED)
    assert SECRET not in push
    assert all(SECRET not in repr(event.payload) for event in run.events)
    assert all(USER not in repr(event.payload) for event in run.events)
