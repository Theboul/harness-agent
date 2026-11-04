"""The audit of the decisions with the real system (HU-05-05 AC-01 and AC-02).

``compose()`` builds the real loop, registry, policy chain, approval gate and SQLite store on a
temporary folder; only the shell is a recording double (nothing reaches an interpreter) and the
provider is a ``FakeProvider``. A session with an approval, a rejection, an automatic denial, a
question with nobody to answer and an MCP tool leaves every decision in the audit with its tool,
redacted arguments, decision and time; the verification of the criteria, the startup routine and a
subagent leave theirs with who asks; and no secret reaches the bytes of the database file.
"""

from __future__ import annotations

import asyncio
import dataclasses
import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.mcp import register_mcp_tools
from harness_agent.adapters.mcp.tool import McpTool
from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import SubagentSettings
from harness_agent.core import (
    ApprovalAction,
    ApprovalResult,
    Approver,
    AuditRow,
    Message,
    PermissionRules,
    Provider,
    ProviderResponse,
    Role,
    Shell,
    ShellResult,
    Tool,
    ToolCall,
    ToolDefinition,
    ToolResult,
    parse_task,
    requester_label,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import FIXED_TIME, build, make_config

REASON = "MOTIVO-DE-PRUEBA-789"
SENTINEL = "VALOR-DE-PRUEBA-123"
PREFIXED_KEY = "s" + "k-" + "a" * 24
CREDENTIAL_URL = (
    "https://" + "usuario-de-prueba" + ":" + "clave-de-prueba" + "@servidor.example/r.git"
)
KEY_VARIABLE = "PROYECTO_" + "API_" + "KEY"
SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}}


class RecordingShell(Shell):
    """A shell that runs nothing: it records each command and answers success."""

    def __init__(self) -> None:
        self.commands: list[str] = []

    @property
    def interpreter_name(self) -> str:
        return "bash"

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        self.commands.append(command)
        return ShellResult(exit_code=0, output="salida-del-doble")

    def terminate_running(self) -> None:
        """Nothing runs, so there is nothing to end."""


class ScriptedApprover(Approver):
    """Answers each question with the next result; the questions are kept."""

    def __init__(self, *answers: ApprovalResult) -> None:
        self._answers = list(answers)
        self.questions: list[tuple[ToolCall, dict[str, Any]]] = []

    async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
        self.questions.append((call, details))
        return self._answers.pop(0)


APPROVE = ApprovalResult(ApprovalAction.APPROVE_ONCE)
REJECT = ApprovalResult(ApprovalAction.REJECT, REASON)


class RemoteClient:
    """Stands for a connected MCP client: one tool, every call recorded."""

    name = "remote"
    connected = True

    def __init__(self) -> None:
        self.received: list[tuple[str, dict[str, Any]]] = []

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        self.received.append((name, arguments))
        return ToolResult("", "desde el servidor")

    async def list_tools(self) -> list[Tool]:
        return [McpTool(self.name, "ping", "Ping.", SCHEMA, self.call)]


def call(identifier: str, name: str, **arguments: Any) -> ProviderResponse:
    return ProviderResponse(tool_calls=[ToolCall(identifier, name, dict(arguments))])


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class Rig:
    def __init__(
        self,
        tmp_path: Path,
        opened: list[Composition],
        monkeypatch: pytest.MonkeyPatch,
        *script: ProviderResponse,
        approver: Approver | None,
        rules: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
        environ: dict[str, str] | None = None,
        subagents: SubagentSettings | None = None,
        task_text: str | None = None,
    ) -> None:
        self.shell = RecordingShell()
        monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: self.shell)
        self.workspace = tmp_path / "trabajo"
        self.workspace.mkdir(exist_ok=True)
        (self.workspace / "notas.txt").write_text("hola", encoding="utf-8")
        self.provider = FakeProvider(list(script) or [ProviderResponse(content="listo")])
        config = make_config(tmp_path, workspace=self.workspace, permissions=rules)
        if subagents is not None:
            config = dataclasses.replace(config, subagents=subagents)
        options: dict[str, Any] = {} if environ is None else {"environ": environ}
        if task_text is not None:
            options["task"] = parse_task(task_text)
            options["clock"] = lambda: FIXED_TIME
        self.composition = build(
            opened, config, self.provider, system_name="Linux", approver=approver, **options
        )
        self.database_dir = config.paths.sessions_db.parent

    async def session(self, *lines: str) -> str:
        output = io.StringIO()
        await run_session(
            self.composition,
            input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
            output=output,
        )
        return output.getvalue().replace("tarea> ", "")

    def audit(self, session: str | None = None) -> list[AuditRow]:
        assert self.composition.audit is not None
        return self.composition.audit.rows(session or self.composition.session_id, 100)

    def raw_bytes(self) -> bytes:
        self.composition.close()
        files = [path for path in self.database_dir.rglob("*") if path.is_file()]
        assert files
        return b"".join(path.read_bytes() for path in files)


def shape(rows: list[AuditRow]) -> list[tuple[str, str, str, str | None]]:
    return [(row.tool, row.decision, row.resolution, row.action) for row in rows]


# --- AC-01: every decision, with its data -----------------------------------------------------


async def test_every_kind_of_decision_leaves_a_complete_row_and_the_command_shows_them(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    approver = ScriptedApprover(APPROVE, REJECT, APPROVE)
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        call("c1", "leer_archivo", path="notas.txt"),
        call("c2", "shell", command="echo hola"),
        call("c3", "shell", command="ls -la"),
        call("c4", "escribir_archivo", path="nuevo.txt", content="x"),
        call("c5", "ping", text="hi"),
        ProviderResponse(content="listo"),
        approver=approver,
        rules=PermissionRules(deny=("escribir_archivo",)),
    )
    client = RemoteClient()
    await register_mcp_tools(
        [client], rig.composition.registry, print, rig.composition.mcp_tool_names
    )

    shown = await rig.session("trabaja", "/auditoria")

    rows = rig.audit()
    assert shape(rows) == [
        ("leer_archivo", "allow", "permitida", None),
        ("shell", "ask", "aprobada", "approve_once"),
        ("shell", "ask", "rechazada", "reject"),
        ("escribir_archivo", "deny", "denegada", None),
        ("ping", "ask", "aprobada", "approve_once"),
    ]
    assert [row.arguments for row in rows] == [
        '{"path": "notas.txt"}',
        '{"command": "echo hola"}',
        '{"command": "ls -la"}',
        '{"content": "x", "path": "nuevo.txt"}',
        '{"text": "hi"}',
    ]
    assert all(row.source in (None, "user") for row in rows)
    assert all(row.resolved_at is not None for row in rows if row.decision == "ask")
    assert all(row.resolved_at is None for row in rows if row.decision != "ask")
    times = [row.decided_at for row in rows]
    assert times == sorted(times) and all(moment.tzinfo is not None for moment in times)
    assert rig.shell.commands == ["echo hola"]  # the rejected and the denied never ran
    assert client.received == [("ping", {"text": "hi"})]
    assert [call.name for call, _ in approver.questions] == ["shell", "shell", "ping"]  # no denial
    for row in rows:
        assert row.origin == "agente" and row.parent_id is None
        assert row.tool in shown
    assert "5 registros" in shown and "rechazada" in shown and "denegada" in shown


async def test_a_question_with_nobody_to_answer_is_recorded_as_denied(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        call("c1", "shell", command="ls -la"),
        ProviderResponse(content="listo"),
        approver=None,
    )

    await rig.session("trabaja")

    assert shape(rig.audit()) == [("shell", "ask", "denegada", None)]
    assert rig.shell.commands == []


async def test_a_call_rejected_before_any_decision_leaves_no_row(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        call("c1", "no_existe", x=1),
        call("c2", "leer_archivo"),  # the path is missing: the arguments are invalid
        ProviderResponse(content="listo"),
        approver=None,
    )

    await rig.session("trabaja")

    assert rig.audit() == []


# --- the other sources of decisions -----------------------------------------------------------


def ticket(*commands: str) -> str:
    lines = [
        "# TAREA-14",
        "## Objetivo",
        "Validar el formulario.",
        "",
        "## Criterios de aceptación",
    ]
    for index, command in enumerate(commands):
        lines += [
            f"- Criterio {index + 1}",
            f"  - comando: {command}",
            "  - espera: codigo_salida == 0",
        ]
    lines += ["", "## Comandos", "- pruebas: check-a"]
    return "\n".join(lines) + "\n"


async def test_the_verification_of_the_criteria_leaves_its_decisions_with_its_origin(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        ProviderResponse(content="listo"),
        approver=ScriptedApprover(APPROVE),
        task_text=ticket("check-a", "otro-comando"),
    )
    runner = rig.composition.runner
    assert runner is not None

    await runner.run("trabaja", list(rig.composition.history_prefix))

    rows = rig.audit()
    assert [(row.arguments, row.resolution, row.origin) for row in rows] == [
        ('{"command": "check-a", "timeout_seconds": 300}', "permitida", "verificacion"),
        ('{"command": "otro-comando"}', "aprobada", "verificacion"),
    ]
    assert [row.call_id for row in rows] == ["verificacion-1", "verificacion-2"]


async def test_the_startup_routine_leaves_its_decisions_with_its_origin(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    (workspace / "progreso-TAREA-14.md").write_text("# Progreso\n- Hecho: algo\n", encoding="utf-8")
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        ProviderResponse(content="listo"),
        approver=None,
        task_text=ticket("check-a"),
    )

    await rig.session("mi pedido")

    rows = [row for row in rig.audit() if row.origin == "arranque"]
    assert [row.call_id for row in rows] == ["arranque-git", "arranque-prueba"]
    assert [row.resolution for row in rows] == ["permitida", "permitida"]
    assert "git log" in rows[0].arguments and "check-a" in rows[1].arguments


async def test_a_subagent_leaves_its_decisions_under_its_session_and_the_command_shows_who_asks(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    answer = ProviderResponse(
        content=json.dumps({"resultado": "ok", "hallazgos_clave": [], "fuentes": []})
    )
    approver = ScriptedApprover(APPROVE)
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        call("d1", "delegar", objetivo="Mira el módulo."),
        call("h1", "shell", command="echo hijo"),
        answer,
        ProviderResponse(content="listo"),
        approver=approver,
        subagents=SubagentSettings(enabled=True),
    )

    shown = await rig.session("delega", "/auditoria")

    rows = rig.audit()
    own = [row for row in rows if row.parent_id is None]
    child = [row for row in rows if row.parent_id is not None]
    assert [(row.tool, row.resolution) for row in own] == [("delegar", "permitida")]
    assert [(row.tool, row.resolution) for row in child] == [("shell", "aprobada")]
    assert child[0].session_id != rig.composition.session_id
    assert child[0].parent_id == rig.composition.session_id
    assert requester_label(child[0].session_id) in shown
    assert rig.audit(child[0].session_id)[0].tool == "shell"
    assert "requested_by" in approver.questions[0][1]  # the person was told who asks


# --- AC-02: nothing secret reaches the file ---------------------------------------------------


async def test_a_key_an_environment_value_and_a_credential_never_reach_the_database_file(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    command = f"echo {PREFIXED_KEY} {SENTINEL} {CREDENTIAL_URL}"
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        call("c1", "shell", command=command),
        call("c2", "shell", command="ls -la"),
        ProviderResponse(content="listo"),
        approver=ScriptedApprover(APPROVE, REJECT),
        environ={KEY_VARIABLE: SENTINEL},
    )

    shown = await rig.session("trabaja", "/auditoria")

    rows = rig.audit()
    hidden = "<secreto oculto>"
    assert hidden in rows[0].arguments
    for secret in (PREFIXED_KEY, SENTINEL, "clave-de-prueba"):
        assert secret not in rows[0].arguments and secret not in shown
    assert rig.shell.commands == [command]  # the real command still ran with the real values
    raw = rig.raw_bytes()
    for secret in (PREFIXED_KEY, SENTINEL, "clave-de-prueba", REASON):
        assert secret.encode() not in raw, secret


async def test_the_audit_never_holds_the_text_of_a_rejection_reason(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        call("c1", "shell", command="ls -la"),
        ProviderResponse(content="listo"),
        approver=ScriptedApprover(REJECT),
    )

    await rig.session("trabaja")

    assert shape(rig.audit()) == [("shell", "ask", "rechazada", "reject")]
    assert REASON.encode() not in rig.raw_bytes()


# --- the audit fails closed -------------------------------------------------------------------


async def test_a_decision_that_cannot_be_recorded_stops_the_tool(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        call("c1", "shell", command="echo no-debe-correr"),
        ProviderResponse(content="listo"),
        approver=ScriptedApprover(APPROVE),
    )
    rig.composition.store.connection().execute("DROP TABLE auditoria")

    with pytest.raises(Exception) as raised:
        await rig.composition.loop.run_turn(
            session_id=rig.composition.session_id, task="trabaja", history=[]
        )

    assert type(raised.value).__name__ == "EventDeliveryError"
    assert rig.shell.commands == []


# --- the model cannot reach the table ----------------------------------------------------------


async def test_the_model_cannot_touch_the_database_through_the_shell_or_the_file_tools(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    rig = Rig(
        tmp_path,
        opened,
        monkeypatch,
        call("c1", "shell", command='sqlite3 sesiones.db "DELETE FROM auditoria"'),
        call("c2", "escribir_archivo", path="../datos/sesiones.db", content="x"),
        ProviderResponse(content="listo"),
        approver=ScriptedApprover(),
    )

    await rig.session("trabaja")

    assert [(row.tool, row.resolution) for row in rig.audit()] == [
        ("shell", "denegada"),
        ("escribir_archivo", "denegada"),
    ]
    assert rig.shell.commands == []


# --- the arguments follow their own decision, also when two turns overlap ---------------------


class ByTask(Provider):
    """Answers by what the person asked, not by the order of the calls: it keeps the two turns
    apart however their steps interleave. Each task reads its own file with the same call id."""

    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        if messages[-1].role is Role.TOOL:
            return ProviderResponse(content="listo")
        task = next(m.content for m in reversed(messages) if m.role is Role.USER)
        name = "notas.txt" if "tarea-A" in task else "otras.txt"
        return ProviderResponse(tool_calls=[ToolCall("c1", "leer_archivo", {"path": name})])


async def test_two_turns_that_overlap_keep_the_arguments_of_their_own_decision(
    tmp_path: Path, opened: list[Composition]
) -> None:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    (workspace / "notas.txt").write_text("hola", encoding="utf-8")
    (workspace / "otras.txt").write_text("otras", encoding="utf-8")
    composition = build(
        opened, make_config(tmp_path, workspace=workspace), ByTask(), system_name="Linux"
    )
    other = composition.store.create_session(model="fake/test").id
    loop = composition.loop

    await asyncio.gather(
        loop.run_turn(session_id=composition.session_id, task="tarea-A", history=[]),
        loop.run_turn(session_id=other, task="tarea-B", history=[]),
    )

    assert composition.audit is not None
    first = composition.audit.rows(composition.session_id, 10)
    second = composition.audit.rows(other, 10)
    assert [row.arguments for row in first] == ['{"path": "notas.txt"}']
    assert [row.arguments for row in second] == ['{"path": "otras.txt"}']
