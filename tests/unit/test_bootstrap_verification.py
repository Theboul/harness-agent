"""compose() wires the verifier and the runner only when there is a task (HU-11-04.1).

Only the shell is replaced by a recording double: nothing reaches a real interpreter, and a
command the policy denies or asks (without an approver) never reaches the double either.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent import bootstrap
from harness_agent.bootstrap import Composition
from harness_agent.core import (
    ApprovalAction,
    Approver,
    Event,
    EventType,
    ProviderResponse,
    Shell,
    ShellResult,
    TaskDefinition,
    parse_task,
)
from tests.doubles import DummyApprover, FakeProvider
from tests.unit.bootstrap_support import build, make_config

TASK_TEXT = (
    "## Objetivo\nProbar.\n\n"
    "## Criterios de aceptación\n"
    "- Pasa la comprobación\n  - comando: check-ok\n  - espera: codigo_salida == 0\n"
    "- Se ve bien\n\n"
    "## Comandos\n- pruebas: check-ok\n  - tiempo: 300\n"
)
OTHER_TEXT = (
    "## Objetivo\nProbar.\n\n## Criterios de aceptación\n"
    "- Algo\n  - comando: check-other\n  - espera: codigo_salida == 0\n"
    "- Prohibido\n  - comando: reboot\n  - espera: codigo_salida == 0\n"
)


class RecordingShell(Shell):
    def __init__(self) -> None:
        self.calls: list[tuple[str, float]] = []

    @property
    def interpreter_name(self) -> str:
        return "bash"

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        self.calls.append((command, timeout_seconds))
        return ShellResult(exit_code=0, output="listo")

    def terminate_running(self) -> None:
        """Nothing runs, so there is nothing to end."""


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def compose_with(
    tmp_path: Path,
    opened: list[Composition],
    monkeypatch: pytest.MonkeyPatch,
    task: TaskDefinition | None,
    *,
    approver: Approver | None = None,
    answers: int = 1,
) -> tuple[Composition, RecordingShell]:
    shell = RecordingShell()
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: shell)
    workspace = tmp_path / "trabajo"
    workspace.mkdir(exist_ok=True)
    provider = FakeProvider([ProviderResponse(content="listo") for _ in range(answers)])
    composition = build(
        opened,
        make_config(tmp_path, workspace=workspace),
        provider,
        system_name="Linux",
        task=task,
        approver=approver,
    )
    return composition, shell


def events_of(composition: Composition, kind: EventType) -> list[Event]:
    seen: list[Event] = []
    composition.bus.subscribe(kind, seen.append)
    return seen


def test_without_a_task_there_is_no_runner(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, _ = compose_with(tmp_path, opened, monkeypatch, None)

    assert composition.runner is None


def test_with_a_task_there_is_a_runner(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, _ = compose_with(tmp_path, opened, monkeypatch, parse_task(TASK_TEXT))

    assert composition.runner is not None


async def test_a_declared_command_runs_with_its_time_and_without_asking(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, shell = compose_with(tmp_path, opened, monkeypatch, parse_task(TASK_TEXT))
    seen = events_of(composition, EventType.CRITERION_VERIFIED)
    assert composition.runner is not None

    await composition.runner.run("trabaja", list(composition.history_prefix))

    assert shell.calls == [("check-ok", 300.0)]
    assert [(e.payload["status"], e.payload["exit_code"]) for e in seen] == [
        ("cumplido", 0),
        ("pendiente_humano", None),
    ]
    assert composition.task_store is not None
    passes = [item.passes for item in composition.task_store.load_criteria(composition.session_id)]
    assert passes == [True, False]


async def test_what_the_policy_asks_without_an_approver_does_not_run_and_the_denied_neither(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, shell = compose_with(tmp_path, opened, monkeypatch, parse_task(OTHER_TEXT))
    seen = events_of(composition, EventType.CRITERION_VERIFIED)
    assert composition.runner is not None

    await composition.runner.run("trabaja", list(composition.history_prefix))

    assert shell.calls == []
    assert [e.payload["status"] for e in seen] == ["no_ejecutado", "no_ejecutado"]


async def test_the_approver_of_the_session_is_the_one_asked(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    composition, shell = compose_with(
        tmp_path, opened, monkeypatch, parse_task(OTHER_TEXT), approver=approver, answers=3
    )
    assert composition.runner is not None

    await composition.runner.run("trabaja", list(composition.history_prefix))

    asked = [call.arguments["command"] for call, _ in approver.recorded_requests]
    assert asked == ["check-other"]  # the denied command never reaches the approver
    assert shell.calls == [("check-other", 120.0)]


async def test_the_session_shows_the_state_and_answers_the_command(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, _ = compose_with(tmp_path, opened, monkeypatch, parse_task(TASK_TEXT))
    output = io.StringIO()

    code = await bootstrap.run_session(
        composition,
        input_stream=io.StringIO("trabaja\n/criterios\n/ayuda\n/salir\n"),
        output=output,
    )

    shown = output.getvalue()
    assert code == 0
    assert shown.count("[x] 1 Pasa la comprobación (check-ok: salida 0)") == 2
    assert shown.count("Tarea: pendiente de validación humana (1 de 1 criterios objetivos") == 2
    assert "  /criterios  Muestra el estado de los criterios.\n" in shown


async def test_a_session_without_a_task_has_no_criteria_command(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, _ = compose_with(tmp_path, opened, monkeypatch, None)
    output = io.StringIO()

    await bootstrap.run_session(
        composition, input_stream=io.StringIO("/criterios\n/salir\n"), output=output
    )

    assert "Comando desconocido: '/criterios'." in output.getvalue()
