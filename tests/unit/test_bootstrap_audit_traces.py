"""compose() wires the audit and the traces of the calls (HU-05-05, HU-10-01 / T008).

The provider is a ``FakeProvider``; the database is a temporary file; the shell never runs. The
audit has no switch; the traces are on unless ``[traces] enabled = false``. The loop, the
subagents, the verifier and the startup routine all use the same wrapped policy.
"""

from __future__ import annotations

import dataclasses
import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.storage import SqliteAuditStore, SqliteTraceStore
from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import SubagentSettings, TraceSettings
from harness_agent.core import (
    ArgumentsTap,
    InMemoryToolRegistry,
    ProviderResponse,
    Shell,
    ShellResult,
    ToolCall,
    TracingProvider,
    TracingRegistry,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config

READ = ToolCall("r1", "leer_archivo", {"path": "notas.txt"})
READING = ProviderResponse(content="", tool_calls=[READ])
DONE = ProviderResponse(content="listo")
DELEGATE = ProviderResponse(
    content="", tool_calls=[ToolCall("d1", "delegar", {"objetivo": "Resume."})]
)
CHILD_ANSWER = ProviderResponse(
    content=json.dumps({"resultado": "ok", "hallazgos_clave": [], "fuentes": []})
)


class NoShell(Shell):
    @property
    def interpreter_name(self) -> str:
        return "bash"

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        raise AssertionError("no command runs in these tests")

    def terminate_running(self) -> None:
        """Nothing runs."""


@pytest.fixture(autouse=True)
def no_real_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: NoShell())


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def compose_with(
    tmp_path: Path,
    opened: list[Composition],
    *script: ProviderResponse,
    traces: TraceSettings = TraceSettings(),  # noqa: B008 (immutable)
    **options: Any,
) -> tuple[Composition, FakeProvider]:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "notas.txt").write_text("hola", encoding="utf-8")
    config = dataclasses.replace(make_config(tmp_path, workspace=workspace), traces=traces)
    if "subagents" in options:
        config = dataclasses.replace(config, subagents=options.pop("subagents"))
    provider = FakeProvider(list(script) or [DONE])
    return build(opened, config, provider, system_name="Linux", **options), provider


async def drive(composition: Composition, *lines: str) -> str:
    output = io.StringIO()
    await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
        output=output,
    )
    return output.getvalue()


# --- the wiring -------------------------------------------------------------------------------


def test_by_default_the_audit_and_the_traces_are_wired(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = compose_with(tmp_path, opened)

    loop: Any = composition.loop
    assert isinstance(composition.audit, SqliteAuditStore)
    assert isinstance(composition.traces, SqliteTraceStore)
    assert isinstance(loop._policy, ArgumentsTap)
    assert isinstance(loop._provider, TracingProvider)
    assert isinstance(loop._registry, TracingRegistry)


def test_the_registry_of_the_composition_stays_the_real_one(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = compose_with(tmp_path, opened)

    assert isinstance(composition.registry, InMemoryToolRegistry)
    assert composition.registry.get("leer_archivo") is not None
    loop: Any = composition.loop
    assert loop._registry is not composition.registry


def test_with_the_traces_off_nothing_is_wrapped_and_the_audit_stays(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = compose_with(tmp_path, opened, traces=TraceSettings(enabled=False))

    loop: Any = composition.loop
    assert composition.traces is None
    assert not isinstance(loop._provider, TracingProvider)
    assert loop._registry is composition.registry
    assert isinstance(composition.audit, SqliteAuditStore)
    assert isinstance(loop._policy, ArgumentsTap)


# --- what a session leaves --------------------------------------------------------------------


async def test_a_session_with_a_tool_leaves_its_decision_and_its_traces(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = compose_with(tmp_path, opened, READING, DONE)

    await drive(composition, "lee")

    assert composition.audit is not None and composition.traces is not None
    audit = composition.audit.rows(composition.session_id, 10)
    assert [(row.tool, row.decision, row.resolution) for row in audit] == [
        ("leer_archivo", "allow", "permitida")
    ]
    assert audit[0].arguments == '{"path": "notas.txt"}'
    traces = composition.traces.rows(composition.session_id, 10)
    assert [(row.kind, row.name, row.result) for row in traces] == [
        ("modelo", "openai/modelo-de-prueba", "ok"),
        ("herramienta", "leer_archivo", "ok"),
        ("modelo", "openai/modelo-de-prueba", "ok"),
    ]


async def test_with_the_traces_off_a_session_still_leaves_its_decision(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = compose_with(
        tmp_path, opened, READING, DONE, traces=TraceSettings(enabled=False)
    )

    await drive(composition, "lee")

    assert composition.audit is not None
    assert len(composition.audit.rows(composition.session_id, 10)) == 1
    raw = composition.store.connection().execute("SELECT COUNT(*) FROM trazas").fetchone()
    assert raw[0] == 0


async def test_a_subagent_leaves_its_traces_under_its_child_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = compose_with(
        tmp_path,
        opened,
        DELEGATE,
        CHILD_ANSWER,
        DONE,
        subagents=SubagentSettings(enabled=True),
    )

    await drive(composition, "delega")

    assert composition.traces is not None
    rows = composition.traces.rows(composition.session_id, 20)
    own = [(row.kind, row.name) for row in rows if row.parent_id is None]
    child = [(row.kind, row.parent_id) for row in rows if row.parent_id is not None]
    assert sorted(own) == sorted(
        [
            ("modelo", "openai/modelo-de-prueba"),
            ("modelo", "openai/modelo-de-prueba"),
            ("herramienta", "delegar"),
        ]
    )
    assert child == [("modelo", composition.session_id)]
    assert len({row.session_id for row in rows}) == 2
