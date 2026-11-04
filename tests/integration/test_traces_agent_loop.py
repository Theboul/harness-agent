"""The traces of the calls with the real system (HU-10-01 AC-01 and the rule of the secrets).

``compose()`` builds the real loop, registry, retries, failover, compactor and SQLite store on a
temporary folder; the providers are ``FakeProvider`` doubles. A session leaves one trace per call
to the model and to a tool, with duration, tokens (or «sin dato») and result, in order; a call
with retries or a failover is one trace; no content of a message, argument or result reaches the
table; a failing trace store changes nothing; the subagent leaves its traces under its session;
and with the traces off, or on, a conversation is the same conversation.
"""

from __future__ import annotations

import dataclasses
import io
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent.bootstrap import Composition, compose, run_session
from harness_agent.config import ModelAlias, Retries, Secret, SubagentSettings, TraceSettings
from harness_agent.core import (
    TRACE_WARNING,
    ContextSettings,
    EventType,
    Message,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    QuotaExceeded,
    TokenUsage,
    ToolCall,
    TraceRow,
    requester_label,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import make_config

DEFAULT, UNO = "openai/base", "gemini/uno"
UNO_ALIAS = ModelAlias("uno", UNO, Secret("clave-de-prueba-uno"), "GEMINI_API_KEY")
USER_MARK, REPLY_MARK = "MARCA-DEL-USUARIO-111", "MARCA-DE-LA-RESPUESTA-222"
ARGUMENT_MARK, RESULT_MARK = "MARCA-DEL-ARGUMENTO-333", "MARCA-DEL-RESULTADO-444"
Step = ProviderResponse | ProviderError


def read(path: str, identifier: str = "c1") -> ProviderResponse:
    return ProviderResponse(tool_calls=[ToolCall(identifier, "leer_archivo", {"path": path})])


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class World:
    """One provider per model, each a ``FakeProvider`` of its own script."""

    def __init__(self, scripts: dict[str, list[Step]]) -> None:
        self.scripts = scripts
        self.providers: dict[str, FakeProvider] = {}

    def __call__(self, config: Any) -> Provider:
        model = config.model
        if model not in self.providers:
            self.providers[model] = FakeProvider(
                self.scripts.get(model, [ProviderResponse("x")] * 8)
            )
        return self.providers[model]


def make(
    tmp_path: Path,
    opened: list[Composition],
    world: World,
    *,
    traces: bool = True,
    failover: tuple[str, ...] = (),
    attempts: int = 1,
    context: ContextSettings | None = None,
    subagents: bool = False,
) -> Composition:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "notas.txt").write_text("hola", encoding="utf-8")
    (workspace / f"{ARGUMENT_MARK}.txt").write_text(RESULT_MARK, encoding="utf-8")
    config = dataclasses.replace(
        make_config(tmp_path, workspace=workspace, model=DEFAULT),
        models=(UNO_ALIAS,),
        failover=failover,
        retries=Retries(max_attempts=attempts),
        subagents=SubagentSettings(enabled=subagents),
        traces=TraceSettings(enabled=traces),
    )
    if context is not None:
        config = dataclasses.replace(config, context=context)

    async def no_wait(seconds: float) -> None:
        return None

    composition = compose(config, provider_factory=world, system_name="Linux", retry_sleep=no_wait)
    opened.append(composition)
    return composition


def without_durations(text: str) -> str:
    """The console text with the durations of the steps taken out (they differ in every run)."""
    return re.sub(r"\(\d[\d,.]* (?:ms|s)\)", "(…)", text)


async def run(composition: Composition, *lines: str) -> str:
    output = io.StringIO()
    await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
        output=output,
    )
    return output.getvalue().replace("tarea> ", "")


def traces_of(composition: Composition, session: str | None = None) -> list[TraceRow]:
    assert composition.traces is not None
    return composition.traces.rows(session or composition.session_id, 200)


def table_text(composition: Composition) -> str:
    connection = composition.store.connection()
    return repr(connection.execute("SELECT * FROM trazas").fetchall())


# --- AC-01: every call, with its duration, tokens and result ----------------------------------


async def test_a_session_leaves_one_trace_per_call_in_order_with_duration_tokens_and_result(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World(
        {
            DEFAULT: [
                dataclasses.replace(read("notas.txt"), usage=TokenUsage(120, 30)),
                read("falta.txt", "c2"),  # no usage here
                QuotaExceeded("sin crédito"),
            ]
        }
    )
    composition = make(tmp_path, opened, world)

    shown = await run(composition, "trabaja", "/trazas")

    rows = traces_of(composition)
    assert [(row.kind, row.name) for row in rows] == [
        ("modelo", DEFAULT),
        ("herramienta", "leer_archivo"),
        ("modelo", DEFAULT),
        ("herramienta", "leer_archivo"),
        ("modelo", DEFAULT),
    ]
    assert [(row.input_tokens, row.output_tokens) for row in rows] == [(120, 30)] + [
        (None, None)
    ] * 4
    assert rows[0].result == "ok" and rows[1].result == "ok" and rows[2].result == "ok"
    assert rows[3].result not in ("ok", "") and rows[3].result.replace("_", "").isalpha()
    assert rows[4].result == "QuotaExceeded" and rows[4].size == 0
    assert all(row.duration_ms >= 0 and row.started_at.tzinfo is not None for row in rows)
    assert [row.started_at for row in rows] == sorted(row.started_at for row in rows)
    assert f"Trazas de la sesión {composition.session_id} (5 llamadas)." in shown
    assert "120/30" in shown and "sin dato" in shown and "QuotaExceeded" in shown
    table = shown.split("Trazas de la sesión")[1]
    assert "sin crédito" not in table_text(composition) + table


async def test_a_call_with_retries_is_one_trace_and_the_retry_is_still_an_event(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World({DEFAULT: [ProviderTimeout("lento"), ProviderResponse("listo")]})
    composition = make(tmp_path, opened, world, attempts=3)

    await run(composition, "trabaja")

    rows = traces_of(composition)
    assert [(row.kind, row.result) for row in rows] == [("modelo", "ok")]
    kinds = [
        json.loads(content)["reason"]
        for (content,) in composition.store.connection().execute(
            "SELECT content FROM events WHERE type = ?", (EventType.PROVIDER_ERROR.value,)
        )
    ]
    assert kinds == ["retry"]


async def test_a_call_that_switches_to_a_fallback_model_is_one_trace_with_the_model_that_answered(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World({DEFAULT: [QuotaExceeded("a")], UNO: [ProviderResponse("de respaldo")]})
    composition = make(tmp_path, opened, world, failover=("uno",))

    await run(composition, "trabaja")

    rows = traces_of(composition)
    assert [(row.kind, row.name, row.result) for row in rows] == [("modelo", UNO, "ok")]


async def test_every_call_to_the_model_leaves_a_trace_the_summary_of_the_compaction_too(
    tmp_path: Path, opened: list[Composition]
) -> None:
    filling = "relleno " * 48
    context = ContextSettings(
        window_tokens=2_400,
        threshold_percent=45,
        recent_percent=5,
        min_recent_messages=4,
        summary_tokens=100,
    )
    world = World({DEFAULT: [ProviderResponse(f"respuesta {n} {filling}") for n in range(12)]})
    composition = make(tmp_path, opened, world, context=context)

    await run(composition, *(f"tarea {n}" for n in range(1, 7)))

    provider = world.providers[DEFAULT]
    summaries = [
        messages
        for messages in provider.received
        if messages[0].content.startswith("Resume la conversación")
    ]
    assert summaries  # the compaction did call the model to summarize
    models = [row for row in traces_of(composition) if row.kind == "modelo"]
    assert len(models) == provider.call_count


# --- the rule of the secrets: metadata only ---------------------------------------------------


async def test_no_content_of_a_message_an_argument_or_a_result_reaches_the_table(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World(
        {
            DEFAULT: [
                read(f"{ARGUMENT_MARK}.txt"),
                ProviderResponse(f"{REPLY_MARK} listo"),
            ]
        }
    )
    composition = make(tmp_path, opened, world)

    shown = await run(composition, f"trabaja {USER_MARK}", "/trazas")

    rows = traces_of(composition)
    assert len(rows) == 3 and rows[1].size == len(RESULT_MARK)  # only the size of the result
    for mark in (USER_MARK, REPLY_MARK, ARGUMENT_MARK, RESULT_MARK):
        assert mark not in table_text(composition)
        assert mark not in shown.split("Trazas de la sesión")[1]
    columns = [
        row[1] for row in composition.store.connection().execute("PRAGMA table_info(trazas)")
    ]
    assert columns == [
        "id",
        "sesion_id",
        "tipo",
        "nombre",
        "inicio",
        "duracion_ms",
        "tokens_entrada",
        "tokens_salida",
        "resultado",
        "tamano",
    ]


# --- registering a trace never changes the call -----------------------------------------------


async def test_a_failing_trace_store_changes_nothing_and_warns_once(
    tmp_path: Path, opened: list[Composition]
) -> None:
    def script() -> World:
        return World(
            {DEFAULT: [read("notas.txt"), ProviderResponse("listo"), ProviderResponse("dos")]}
        )

    healthy = make(tmp_path / "a", opened, script())
    broken = make(tmp_path / "b", opened, script())
    broken.store.connection().execute("DROP TABLE trazas")

    expected = without_durations(await run(healthy, "uno", "dos"))
    obtained = without_durations(await run(broken, "uno", "dos"))

    assert obtained.count(TRACE_WARNING) == 1
    assert obtained.replace(TRACE_WARNING + "\n", "") == expected
    assert "auditoria" not in obtained and "sqlite" not in obtained.lower()


async def test_with_the_traces_on_or_off_the_conversation_is_the_same_conversation(
    tmp_path: Path, opened: list[Composition]
) -> None:
    def script() -> World:
        return World({DEFAULT: [read("notas.txt"), ProviderResponse("listo")]})

    async def conversation(
        base: Path, traces: bool
    ) -> tuple[list[Any], list[Any], tuple[Message, ...]]:
        composition = make(base, opened, script(), traces=traces)
        events: list[Any] = []
        for event_type in EventType:
            composition.bus.subscribe(event_type, events.append)
        history: list[Message] = list(composition.history_prefix)
        result = await composition.loop.run_turn(
            session_id=composition.session_id, task="trabaja", history=history
        )
        shape = [(event.type, event.payload) for event in events]
        return shape, [(m.role, m.content) for m in result.history], result.history

    on_events, on_history, _ = await conversation(tmp_path / "encendidas", True)
    off_events, off_history, _ = await conversation(tmp_path / "apagadas", False)

    assert on_history == off_history
    assert on_events == off_events


async def test_with_the_traces_off_nothing_is_stored_and_the_command_says_so(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = make(
        tmp_path, opened, World({DEFAULT: [read("notas.txt"), ProviderResponse("x")]}), traces=False
    )

    shown = await run(composition, "trabaja", "/trazas")

    assert "Las trazas están apagadas en la configuración." in shown
    assert composition.store.connection().execute("SELECT COUNT(*) FROM trazas").fetchone()[0] == 0


# --- the subagent -----------------------------------------------------------------------------


async def test_a_subagent_leaves_its_traces_under_its_session_and_the_orchestrator_the_delegation(
    tmp_path: Path, opened: list[Composition]
) -> None:
    delegate = ProviderResponse(
        tool_calls=[ToolCall("d1", "delegar", {"objetivo": "Mira el módulo."})]
    )
    answer = ProviderResponse(
        json.dumps({"resultado": "ok", "hallazgos_clave": [], "fuentes": []}),
        usage=TokenUsage(40, 10),
    )
    world = World({DEFAULT: [delegate, answer, ProviderResponse("listo")]})
    composition = make(tmp_path, opened, world, subagents=True)

    shown = await run(composition, "delega", "/trazas")

    rows = traces_of(composition)
    own = [row for row in rows if row.parent_id is None]
    child = [row for row in rows if row.parent_id is not None]
    assert sorted((row.kind, row.name) for row in own) == sorted(
        [("modelo", DEFAULT), ("modelo", DEFAULT), ("herramienta", "delegar")]
    )
    assert [(row.kind, row.input_tokens, row.output_tokens) for row in child] == [
        ("modelo", 40, 10)
    ]
    assert child[0].session_id != composition.session_id
    assert child[0].parent_id == composition.session_id
    assert requester_label(child[0].session_id) in shown
