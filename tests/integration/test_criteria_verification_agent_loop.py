"""Automatic verification of the criteria with the real composition (HU-11-04.1 / Sp2-53).

``compose(task=...)`` builds the whole system: policy chain, registry, the verifier and the runner.
The matrix of cases uses a **recording shell double** (it runs nothing, so a denied or asked command
can never reach an interpreter); a single flow at the end uses the real shell with trivial Python
scripts of the sample project. The provider is a ``FakeProvider``: no network, no keys.

The sample ticket has three criteria: two with a command and one semantic (nobody can check it by
running something).
"""

from __future__ import annotations

import io
import json
import os
import platform
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.system import interpreter_for
from harness_agent.bootstrap import Composition
from harness_agent.core import (
    ApprovalAction,
    Approver,
    Event,
    EventType,
    Message,
    PermissionRules,
    ProviderResponse,
    Role,
    Shell,
    ShellResult,
    ToolCall,
    parse_task,
)
from tests.doubles import DummyApprover, FakeProvider
from tests.unit.bootstrap_support import SENTINEL, build, make_config

OUTPUT_SENTINEL = "SALIDA-DE-PRUEBA-456"
CREDENTIAL = (
    "https://" + "usuario-de-prueba" + ":" + "secreto-de-prueba" + "@servidor.example/r.git"
)
DESCRIPTIONS = (
    "El email es obligatorio",
    "La contraseña tiene 8 caracteres",
    "El mensaje de error es claro",
)
FINAL = "listo"


def ticket(*commands: str | None) -> str:
    """A ticket whose criteria have the given commands (``None``: a semantic one).

    ``check-a`` and ``check-b`` are also declared as the test and lint commands of the task, so
    the policy allows them exactly; anything else is asked.
    """
    lines = [
        "# TAREA-14",
        "## Objetivo",
        "Validar el formulario.",
        "",
        "## Criterios de aceptación",
    ]
    for index, command in enumerate(commands):
        lines.append(f"- {DESCRIPTIONS[index] if index < 3 else f'Criterio {index + 1}'}")
        if command is not None:
            lines += [f"  - comando: {command}", "  - espera: codigo_salida == 0"]
    lines += ["", "## Comandos", "- pruebas: check-a", "  - tiempo: 300", "- lint: check-b"]
    return "\n".join(lines) + "\n"


class ScriptedShell(Shell):
    """Records every command and answers by command; it runs nothing."""

    def __init__(self, results: dict[str, list[ShellResult]] | None = None) -> None:
        self._results = results or {}
        self.calls: list[tuple[str, float]] = []

    @property
    def interpreter_name(self) -> str:
        return "bash"

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        self.calls.append((command, timeout_seconds))
        queue = self._results.get(command, [ShellResult(0, "ok")])
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def terminate_running(self) -> None:
        """Nothing runs, so there is nothing to end."""


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class Rig:
    """One composed system with the shell double and the events it publishes."""

    def __init__(
        self,
        tmp_path: Path,
        opened: list[Composition],
        monkeypatch: pytest.MonkeyPatch,
        text: str,
        *,
        proposals: int = 1,
        results: dict[str, list[ShellResult]] | None = None,
        approver: Approver | None = None,
        rules: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
    ) -> None:
        self.shell = ScriptedShell(results)
        monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: self.shell)
        workspace = tmp_path / "trabajo"
        workspace.mkdir(exist_ok=True)
        self.provider = FakeProvider([ProviderResponse(content=FINAL)] * proposals)
        config = make_config(tmp_path, workspace=workspace, permissions=rules)
        self.composition = build(
            opened,
            config,
            self.provider,
            system_name="Linux",
            task=parse_task(text),
            approver=approver,
        )
        self.events: list[Event] = []
        self.calls_when_met: list[int] = []
        for event_type in EventType:
            self.composition.bus.subscribe(event_type, self.events.append)
        self.composition.bus.subscribe(EventType.CRITERION_VERIFIED, self._seen)
        self.history: list[Message] = list(self.composition.history_prefix)

    def _seen(self, event: Event) -> None:
        if event.payload["status"] == "cumplido":
            self.calls_when_met.append(len(self.shell.calls))

    async def propose(self, task: str = "trabaja") -> None:
        assert self.composition.runner is not None
        await self.composition.runner.run(task, self.history)

    def statuses(self) -> list[str]:
        return [e.payload["status"] for e in self.events if e.type is EventType.CRITERION_VERIFIED]

    def passes(self) -> list[bool]:
        assert self.composition.task_store is not None
        items = self.composition.task_store.load_criteria(self.composition.session_id)
        return [item.passes for item in items]

    def sent_to_the_model(self, request: int) -> list[Message]:
        return self.provider.received[request]

    def published(self) -> str:
        return json.dumps([e.payload for e in self.events], ensure_ascii=False)

    def stored_events(self) -> str:
        connection = self.composition.store.connection()
        return " ".join(str(row) for row in connection.execute("SELECT content FROM events"))


# --- the matrix of cases --------------------------------------------------------------------------


async def test_all_the_criteria_are_met(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(tmp_path, opened, monkeypatch, ticket("check-a", "check-b"))

    await rig.propose()

    assert rig.statuses() == ["cumplido", "cumplido"]
    assert rig.passes() == [True, True]
    assert rig.shell.calls == [("check-a", 300.0), ("check-b", 300.0)]
    assert len(rig.provider.received) == 1  # nothing to correct: no second turn


async def test_the_objective_ones_are_met_and_there_is_a_semantic_one(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(tmp_path, opened, monkeypatch, ticket("check-a", "check-b", None))

    await rig.propose()

    assert rig.statuses() == ["cumplido", "cumplido", "pendiente_humano"]
    assert rig.passes() == [True, True, False]  # the semantic one is never marked
    assert len(rig.shell.calls) == 2


async def test_the_claim_of_the_model_marks_nothing_before_the_commands_ran(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(tmp_path, opened, monkeypatch, ticket("check-a", "check-b", None))

    assert rig.passes() == [False, False, False]
    await rig.propose()

    assert rig.calls_when_met == [1, 2]  # each "cumplido" came after its command ran


async def test_one_that_fails_goes_back_to_the_agent_and_every_criterion_runs_again(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    results = {"check-b": [ShellResult(1, f"{OUTPUT_SENTINEL} mal"), ShellResult(0, "bien")]}
    rig = Rig(
        tmp_path, opened, monkeypatch, ticket("check-a", "check-b"), proposals=2, results=results
    )

    await rig.propose()

    assert rig.statuses() == ["cumplido", "no_cumplido", "cumplido", "cumplido"]
    assert rig.passes() == [True, True]
    assert [c for c, _ in rig.shell.calls] == ["check-a", "check-b", "check-a", "check-b"]
    second_request = rig.sent_to_the_model(1)
    external = [m for m in second_request if m.is_external]
    assert len(external) == 1 and external[0].role is Role.USER
    assert OUTPUT_SENTINEL in external[0].content
    notice = second_request[-1]
    assert notice.role is Role.USER and not notice.is_external
    assert "Criterio 2 (La contraseña tiene 8 caracteres): no cumplido, código de salida 1." in (
        notice.content
    )
    assert "check-b" not in notice.content and OUTPUT_SENTINEL not in notice.content


async def test_a_regression_is_reported_and_passes_is_not_revoked(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    results = {"check-a": [ShellResult(0, "bien"), ShellResult(2, "roto"), ShellResult(0, "bien")]}
    rig = Rig(
        tmp_path, opened, monkeypatch, ticket("check-a", "check-b"), proposals=3, results=results
    )

    await rig.propose("primero")
    assert rig.statuses() == ["cumplido", "cumplido"]
    await rig.propose("segundo")

    assert rig.statuses()[2:4] == ["regresion", "cumplido"]
    assert rig.passes() == [True, True]  # never revoked
    notice = rig.sent_to_the_model(2)[-1].content
    assert (
        "Criterio 1 (El email es obligatorio): regresión (antes cumplía), código de salida 2."
        in notice
    )


async def test_a_tampered_database_runs_nothing(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(tmp_path, opened, monkeypatch, ticket("check-a", "check-b", None))
    connection = rig.composition.store.connection()

    def tamper(event: Event) -> None:
        # After the first round has gone out: the essential block fails closed on a tampered source
        # before any round (HU-02-06.1, FR-010), so the verifier is shown the database tampered
        # only once the agent has proposed to finish.
        connection.execute("UPDATE criterios SET comando = 'otro' WHERE orden = 1")
        connection.commit()

    rig.composition.bus.subscribe(EventType.ASSISTANT_MESSAGE, tamper)

    await rig.propose()

    assert rig.statuses() == ["alterado", "alterado", "pendiente_humano"]
    assert rig.shell.calls == []
    assert "otro" not in rig.published()


async def test_what_the_policy_asks_without_an_approver_does_not_run(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(tmp_path, opened, monkeypatch, ticket("check-a", "check-ask"))

    await rig.propose()

    assert rig.statuses() == ["cumplido", "no_ejecutado"]
    assert rig.shell.calls == [("check-a", 300.0)]
    assert len(rig.provider.received) == 1  # the agent cannot fix it: no round


async def test_what_the_policy_asks_is_run_only_if_the_person_approves(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    rig = Rig(tmp_path, opened, monkeypatch, ticket("check-a", "check-ask"), approver=approver)

    await rig.propose()

    assert [c.arguments["command"] for c, _ in approver.recorded_requests] == ["check-ask"]
    assert rig.shell.calls == [("check-a", 300.0), ("check-ask", 120.0)]
    assert rig.statuses() == ["cumplido", "cumplido"]


async def test_a_person_who_rejects_stops_the_command(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    approver = DummyApprover(ApprovalAction.REJECT, "no " + SENTINEL)
    rig = Rig(tmp_path, opened, monkeypatch, ticket("check-ask"), approver=approver)

    await rig.propose()

    assert rig.statuses() == ["no_ejecutado"] and rig.shell.calls == []
    assert SENTINEL not in rig.published() + rig.stored_events()


@pytest.mark.parametrize(
    "command",
    ["reboot", "git push --force origin main", "echo sesiones.db"],
    ids=["base-list", "destructive-git", "protected-area"],
)
async def test_a_denied_command_never_reaches_the_approver_or_the_shell(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    rig = Rig(tmp_path, opened, monkeypatch, ticket("check-a", command), approver=approver)

    await rig.propose()

    assert rig.statuses() == ["cumplido", "no_ejecutado"]
    assert approver.recorded_requests == []
    assert rig.shell.calls == [("check-a", 300.0)]


async def test_the_deny_list_of_tools_wins_over_the_task(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        ticket("check-a"),
        approver=approver,
        rules=PermissionRules(deny=("shell",)),
    )

    await rig.propose()

    assert rig.statuses() == ["no_ejecutado"]
    assert approver.recorded_requests == [] and rig.shell.calls == []


async def test_a_timeout_goes_back_to_the_agent_with_its_limit(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    results = {"check-a": [ShellResult(-1, "a medias", timed_out=True), ShellResult(0, "bien")]}
    rig = Rig(tmp_path, opened, monkeypatch, ticket("check-a"), proposals=2, results=results)

    await rig.propose()

    assert rig.statuses() == ["tiempo_agotado", "cumplido"]
    notice = rig.sent_to_the_model(1)[-1].content
    assert "Criterio 1 (El email es obligatorio): tiempo agotado tras 300 s." in notice


async def test_a_criterion_without_a_command_is_pending_and_runs_nothing(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(tmp_path, opened, monkeypatch, ticket(None, None))

    await rig.propose()

    assert rig.statuses() == ["pendiente_humano", "pendiente_humano"]
    assert rig.shell.calls == [] and rig.passes() == [False, False]


# --- nothing leaks, only the harness marks passes -------------------------------------------------


async def test_the_command_and_the_output_are_in_no_event_error_or_evidence(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    command = "check-leak " + SENTINEL
    results = {command: [ShellResult(1, f"{OUTPUT_SENTINEL} {CREDENTIAL}"), ShellResult(0, "bien")]}
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        ticket("check-a", command),
        proposals=2,
        results=results,
        approver=approver,
    )

    await rig.propose()

    everything = rig.published() + rig.stored_events()
    for secret in (SENTINEL, OUTPUT_SENTINEL, "secreto-de-prueba", "usuario-de-prueba"):
        assert secret not in everything, secret
    assert "El email es obligatorio" in everything  # the description is text of the task
    notice = rig.sent_to_the_model(1)[-1].content
    assert SENTINEL not in notice and "check-leak" not in notice
    assert "secreto-de-prueba" not in "".join(m.content for m in rig.sent_to_the_model(1))
    assert rig.composition.task_store is not None
    for item in rig.composition.task_store.load_criteria(rig.composition.session_id):
        assert item.evidence is not None and SENTINEL not in item.evidence
        assert "check-" not in item.evidence


async def test_no_registered_tool_exposes_the_marking_of_passes(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(tmp_path, opened, monkeypatch, ticket("check-a"))
    registry = getattr(rig.composition.loop, "_registry")  # noqa: B009

    tools = registry.list()

    assert tools
    for tool in tools:
        text = f"{tool.name} {tool.description} {json.dumps(tool.schema)}"
        assert "mark_passes" not in text and "passes" not in text.lower()
        assert not hasattr(tool, "mark_passes")


# --- the terminal ---------------------------------------------------------------------------------


async def test_the_terminal_shows_the_state_after_the_verification_and_on_request(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    results = {"check-b": [ShellResult(1, "mal"), ShellResult(0, "bien")]}
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        ticket("check-a", "check-b", None),
        proposals=2,
        results=results,
    )
    output = io.StringIO()

    code = await bootstrap.run_session(
        rig.composition, input_stream=io.StringIO("revisa\n/criterios\n/salir\n"), output=output
    )

    shown = output.getvalue()
    first_round = (
        "[x] 1 El email es obligatorio (check-a: salida 0)\n"
        "[ ] 2 La contraseña tiene 8 caracteres (check-b: salida 1)\n"
        "[?] 3 El mensaje de error es claro (pendiente de validación humana)\n"
        "Tarea: no terminada (1 de 2 criterios objetivos cumplidos)\n"
    )
    last_round = (
        "[x] 1 El email es obligatorio (check-a: salida 0)\n"
        "[x] 2 La contraseña tiene 8 caracteres (check-b: salida 0)\n"
        "[?] 3 El mensaje de error es claro (pendiente de validación humana)\n"
        "Tarea: pendiente de validación humana (2 de 2 criterios objetivos cumplidos)\n"
    )
    assert code == 0
    assert first_round in shown
    assert shown.count(last_round) == 2  # after the round and again on /criterios


# --- one flow with the real shell: trivial Python scripts of the project --------------------------

SYSTEM = platform.system()
EXECUTABLES = {"powershell": ("pwsh", "powershell"), "bash": ("bash",)}
INTERPRETER = interpreter_for(SYSTEM)
CHECK_EMAIL = (
    "import pathlib\nimport sys\n\nsys.exit(0 if pathlib.Path('email.txt').exists() else 1)\n"
)
CHECK_PASSWORD = "import sys\n\nsys.exit(0)\n"
REAL_COMMANDS = ("python check_email.py", "python check_password.py")


def child_environment() -> dict[str, str]:
    """The interpreter of the tests first on the path and no coverage variables in the child."""
    kept = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COV_CORE", "COVERAGE", "PYTEST_"))
    }
    path_key = next((key for key in kept if key.upper() == "PATH"), "PATH")
    kept[path_key] = os.pathsep.join([str(Path(sys.executable).parent), kept.get(path_key, "")])
    kept["PYTHONDONTWRITEBYTECODE"] = "1"
    return kept


@pytest.mark.skipif(
    not any(shutil.which(name) for name in EXECUTABLES[INTERPRETER]),
    reason=f"el intérprete de la plataforma ({INTERPRETER}) no está instalado",
)
async def test_end_to_end_with_the_real_shell_and_trivial_python_scripts(
    tmp_path: Path, opened: list[Composition]
) -> None:
    project = tmp_path / "proyecto"
    project.mkdir()
    (project / "check_email.py").write_text(CHECK_EMAIL, encoding="utf-8")
    (project / "check_password.py").write_text(CHECK_PASSWORD, encoding="utf-8")
    text = (
        "# TAREA-14\n## Objetivo\nValidar el formulario.\n\n## Criterios de aceptación\n"
        f"- {DESCRIPTIONS[0]}\n  - comando: {REAL_COMMANDS[0]}\n  - espera: codigo_salida == 0\n"
        f"- {DESCRIPTIONS[1]}\n  - comando: {REAL_COMMANDS[1]}\n  - espera: codigo_salida == 0\n"
        f"- {DESCRIPTIONS[2]}\n\n"
        f"## Comandos\n- pruebas: {REAL_COMMANDS[0]}\n  - tiempo: 60\n- lint: {REAL_COMMANDS[1]}\n"
    )
    write = ToolCall(
        id="w1", name="escribir_archivo", arguments={"path": "email.txt", "content": "a@b.c"}
    )
    provider = FakeProvider(
        [
            ProviderResponse(content=FINAL),
            ProviderResponse(tool_calls=[write]),
            ProviderResponse(content="arreglado"),
        ]
    )
    composition = build(
        opened,
        make_config(tmp_path, workspace=project),
        provider,
        task=parse_task(text),
        environ=child_environment(),
    )
    output = io.StringIO()

    code = await bootstrap.run_session(
        composition, input_stream=io.StringIO("revisa\n/salir\n"), output=output
    )

    shown = output.getvalue()
    assert code == 0
    assert (project / "email.txt").exists()
    assert "[ ] 1 El email es obligatorio (python: salida 1)" in shown
    assert "[x] 2 La contraseña tiene 8 caracteres (python: salida 0)" in shown
    assert "Tarea: no terminada (1 de 2 criterios objetivos cumplidos)" in shown
    assert "[x] 1 El email es obligatorio (python: salida 0)" in shown
    assert "Tarea: pendiente de validación humana (2 de 2 criterios objetivos cumplidos)" in shown
    assert composition.task_store is not None
    passes = [i.passes for i in composition.task_store.load_criteria(composition.session_id)]
    assert passes == [True, True, False]
    external = [m for m in provider.received[1] if m.is_external]
    assert len(external) == 1 and "[salida de verificación]" in external[0].content
