"""A long simulated session with the essential block, the real loop and the real SQLite store.

HU-02-06.1 / T008: AC-01, AC-02, AC-03, changes in the middle of the task, the order of the context,
the budget and the converters. ``compose(task=…)`` builds the system and ``run_session`` drives it
line by line; the provider is a test double, local to this file, that records every request and
answers from the context it receives (so a question about the objective can only be answered if the
context carries it). Nothing reaches the network.
"""

from __future__ import annotations

import asyncio
import dataclasses
import io
import re
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.converters import (
    restore_messages,
    to_anthropic_envelope,
    to_openai_envelope,
)
from harness_agent.adapters.storage import (
    SessionStoreError,
    SqliteEssentialStore,
    SqliteSessionStore,
)
from harness_agent.bootstrap import Composition, StartupError
from harness_agent.config import Limits
from harness_agent.core import (
    MARK,
    CommandKind,
    ContextSettings,
    CriterionDefinition,
    EssentialRenewer,
    EventType,
    Message,
    ProviderResponse,
    Role,
    Shell,
    ShellResult,
    TaskCommand,
    TaskDefinition,
    ToolCall,
    ToolDefinition,
    check_block,
    estimate_message,
    estimate_messages,
    is_summary,
    make_items,
    threshold_tokens,
)
from harness_agent.core.interfaces import Provider
from tests.adapters.test_converters_compaction import assert_order_kept
from tests.unit.bootstrap_support import build, make_config

MODEL = "openai/modelo-de-prueba"
SUMMARY_START = "Resume la conversación"
S_TICKET, S_OBJECTIVE, S_RULES = "TKT-SENT-01", "OBJ-SENT-02", "RUL-SENT-03"
S_CRITERION, S_INSTRUCTION = "CRI-SENT-04", "INS-SENT-05"
PAD = "relleno " * 18
LINES = 15
SETTINGS = ContextSettings(
    window_tokens=4_000,
    threshold_percent=40,
    recent_percent=5,
    min_recent_messages=4,
    summary_tokens=100,
)


class NoShell(Shell):
    @property
    def interpreter_name(self) -> str:
        return "bash"

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        raise AssertionError("no command runs in these tests")

    def terminate_running(self) -> None:
        """Nothing runs."""


class Recorder(Provider):
    """Records each request and answers from the context it was given."""

    def __init__(self) -> None:
        self.calls: list[list[Message]] = []
        self.tools: list[list[ToolDefinition] | None] = []
        self.summaries: list[str] = []
        self.answers: list[str] = []
        self.line = 0

    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        self.calls.append(list(messages))
        self.tools.append(tools)
        if tools is None and messages[0].content.startswith(SUMMARY_START):
            # A poor summary: nothing essential in it, and a stale copy of a criterion.
            text = "Resumen breve. Antes: 1. [pendiente] Criterio uno."
            self.summaries.append(text)
            return ProviderResponse(content=text)
        last = messages[-1]
        if last.role is Role.TOOL:
            return ProviderResponse(content=f"respuesta {self.line} marca-A{self.line:03d} {PAD}")
        question = last.content
        if "objetivo original" in question:
            return self._answer(r"Objetivo:\n([^\n]+)", messages)
        if "reglas" in question:
            return self._answer(r"Reglas:\n([^\n]+)", messages)
        if "ticket" in question:
            return self._answer(r"Ticket: ([^\n]+)", messages)
        self.line += 1
        text = "" if self.line % 2 else f"reviso {self.line} {PAD}"
        call = ToolCall(f"c{self.line}", "listar_archivos", {"path": "."})
        return ProviderResponse(content=text, tool_calls=[call])

    def _answer(self, pattern: str, messages: list[Message]) -> ProviderResponse:
        blocks = [m for m in messages if m.role is Role.SYSTEM and m.content.startswith(MARK)]
        found = re.search(pattern, blocks[0].content) if blocks else None
        answer = found.group(1) if found else "no lo sé"
        self.answers.append(answer)
        return ProviderResponse(content=answer)


class Lines:
    """An input that runs a hook just before reading the line it belongs to."""

    def __init__(
        self, lines: list[str], hooks: dict[int, Callable[[], None]] | None = None
    ) -> None:
        self.lines = list(lines)
        self.hooks = hooks or {}
        self.index = 0

    def readline(self) -> str:
        if self.index >= len(self.lines):
            return ""
        hook = self.hooks.get(self.index)
        if hook is not None:
            hook()
        line = self.lines[self.index]
        self.index += 1
        return line + "\n"


def make_task() -> TaskDefinition:
    return TaskDefinition(
        title=f"{S_TICKET}: Validar el correo",
        objective=f"Rechazar correos sin dominio {S_OBJECTIVE}",
        context="contexto libre",
        rules=f"No tocar el esquema {S_RULES}",
        criteria=(
            CriterionDefinition(f"Criterio {S_CRITERION} uno"),
            CriterionDefinition("Criterio dos"),
        ),
        commands=(TaskCommand(CommandKind.TESTS, f"pytest-{S_INSTRUCTION}", 300),),
    )


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def start(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> tuple[Composition, Recorder]:
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: NoShell())
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    (workspace / "a.txt").write_text("contenido", encoding="utf-8")
    config = dataclasses.replace(
        make_config(tmp_path, workspace=workspace, model=MODEL),
        limits=Limits(max_turns=2_000, max_output_tokens=777),
        context=SETTINGS,
    )
    provider = Recorder()
    built = build(opened, config, provider, task=make_task(), system_name="Linux")
    # These tests count tokens against a tuned threshold and list the folder: the progress file of
    # the ticket (HU-11-08.1) would add itself to that listing, so it is left out here.
    return dataclasses.replace(built, progress=None), provider


def drive(composition: Composition, lines: list[str], hooks: Any = None) -> tuple[int, str]:
    output = io.StringIO()
    code = asyncio.run(
        bootstrap.run_session(
            composition,
            input_stream=Lines(lines, hooks),  # type: ignore[arg-type]
            output=output,
        )
    )
    return code, output.getvalue()


def tasks(count: int) -> list[str]:
    return [f"tarea {n} marca-U{n:03d}" for n in range(1, count + 1)]


def model_calls(provider: Recorder) -> list[list[Message]]:
    return [
        messages
        for messages, tools in zip(provider.calls, provider.tools, strict=True)
        if not (tools is None and messages[0].content.startswith(SUMMARY_START))
    ]


def summary_positions(provider: Recorder) -> list[int]:
    return [
        index
        for index, (messages, tools) in enumerate(zip(provider.calls, provider.tools, strict=True))
        if tools is None and messages[0].content.startswith(SUMMARY_START)
    ]


def blocks_of(messages: list[Message]) -> list[Message]:
    return [m for m in messages if m.role is Role.SYSTEM and m.content.startswith(MARK)]


# --- AC-01 and AC-02: a long session with two compactions -------------------------------------


def test_ac01_the_block_is_in_every_call_once_identical_and_in_place_across_two_compactions(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, provider = start(tmp_path, opened, monkeypatch)

    code, _ = drive(composition, [*tasks(LINES), "/salir"])

    assert code == 0
    assert len(summary_positions(provider)) == 2  # two compactions, one summary call each
    prefix = list(composition.history_prefix)
    texts = set()
    for messages in model_calls(provider):
        found = blocks_of(messages)
        assert len(found) == 1  # exactly once, in every call
        assert messages.index(found[0]) == len(prefix)  # always in the same place
        texts.add(found[0].content)
        for sentinel in (S_TICKET, S_OBJECTIVE, S_RULES, S_CRITERION):
            assert sentinel in found[0].content  # whole, never summarised away
    assert len(texts) == 1  # byte for byte the same, before and after each compaction


def test_ac02_the_instructions_stay_intact_and_once_and_the_registry_is_never_sent(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, provider = start(tmp_path, opened, monkeypatch)
    drive(composition, [*tasks(LINES), "/salir"])

    prefix = list(composition.history_prefix)
    assert len(prefix) == 3
    for messages in model_calls(provider):
        assert messages[: len(prefix)] == prefix  # the provisional messages, identical
        assert sum(1 for m in messages if S_INSTRUCTION in m.content) == 1  # once, not twice
        for instruction in prefix:
            assert sum(1 for m in messages if m.content == instruction.content) == 1
    assert S_INSTRUCTION not in blocks_of(provider.calls[0])[0].content


def test_the_order_of_the_context_is_prefix_block_request_summary_recent(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, provider = start(tmp_path, opened, monkeypatch)
    drive(composition, [*tasks(LINES), "/salir"])

    seen_summary = False
    for messages in model_calls(provider):
        block = messages.index(blocks_of(messages)[0])
        request = next(
            i for i, m in enumerate(messages) if m.role is Role.USER and not m.is_external
        )
        assert block < request == block + 1  # the request right after the block
        summaries = [i for i, m in enumerate(messages) if is_summary(m)]
        if summaries:
            seen_summary = True
            assert request < summaries[0] == request + 1 and len(summaries) == 1
    assert seen_summary


def test_the_summary_calls_never_receive_the_block_or_any_essential_value(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, provider = start(tmp_path, opened, monkeypatch)
    drive(composition, [*tasks(LINES), "/salir"])

    for position in summary_positions(provider):
        sent = " ".join(m.content for m in provider.calls[position])
        assert provider.tools[position] is None
        for sentinel in (S_TICKET, S_OBJECTIVE, S_RULES, S_CRITERION, S_INSTRUCTION, MARK):
            assert sentinel not in sent


# --- criteria from their source, and changes in the middle of the task ------------------------


def test_a_criterion_marked_between_two_requests_shows_in_the_next_block_and_beats_the_summary(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, provider = start(tmp_path, opened, monkeypatch)

    def mark_the_first_criterion() -> None:
        assert composition.task_store is not None
        first = composition.task_store.load_criteria(composition.session_id)[0]
        composition.task_store.mark_passes(first.id, "evidencia de prueba")

    drive(composition, [*tasks(LINES), "/salir"], {12: mark_the_first_criterion})

    calls = model_calls(provider)
    flags = ["1. [cumplido]" in blocks_of(m)[0].content for m in calls]
    assert flags[0] is False and flags[-1] is True
    first_done = flags.index(True)
    assert all(flags[first_done:]) and not any(flags[:first_done])  # changes once, never goes back
    assert all(len(blocks_of(m)) == 1 for m in calls)  # never two blocks while it changes
    stale_after_the_change = [
        m
        for messages in calls[first_done:]
        for m in messages
        if is_summary(m) and "1. [pendiente]" in m.content
    ]
    assert stale_after_the_change  # a summary kept an old copy of the criterion; the block wins


# --- AC-03: the objective is remembered after compacting --------------------------------------


def test_ac03_after_two_compactions_with_a_poor_summary_the_agent_still_answers_the_objective(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, provider = start(tmp_path, opened, monkeypatch)

    drive(
        composition,
        [
            *tasks(LINES),
            "¿cuál era el objetivo original?",
            "¿cuáles son las reglas?",
            "¿cuál es el ticket?",
            "/salir",
        ],
    )

    assert len(summary_positions(provider)) == 2
    assert all(S_OBJECTIVE not in text for text in provider.summaries)  # the summary lost it
    objective, rules, ticket = provider.answers
    assert S_OBJECTIVE in objective and S_RULES in rules and S_TICKET in ticket


# --- the budget (FR-014, E4 of the order contract) --------------------------------------------


def test_the_block_counts_in_the_estimate_that_decides_the_compaction() -> None:
    settings = ContextSettings(window_tokens=2_000, threshold_percent=50)
    threshold = threshold_tokens(settings, MODEL)
    items = make_items(
        ticket="TAREA-14: Validar el correo",
        objective="Rechazar correos sin dominio en el formulario de alta.",
        rules="No tocar el esquema de la base.\nMantener la API pública.",
        instructions=[("entorno", "x")],
    )
    text = check_block(items, [], settings, MODEL)
    block = Message(Role.SYSTEM, text)
    block_tokens = estimate_message(block)
    base = [Message(Role.SYSTEM, "entorno")]
    filler_tokens = threshold - estimate_messages(base) - 4 - 3  # lands just under the threshold
    history = [*base, Message(Role.USER, "x" * (filler_tokens * 4))]

    without = estimate_messages(history)
    with_block = estimate_messages([history[0], block, history[1]])

    assert without <= threshold < with_block
    assert with_block - without == block_tokens  # the difference is exactly the block


# --- the converters accept the history with the block (before and after a compaction) ---------


@pytest.mark.parametrize("provider_name", ["openai", "anthropic"])
def test_the_converters_accept_the_history_with_the_block_before_and_after_compacting(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, provider_name: str
) -> None:
    composition, provider = start(tmp_path, opened, monkeypatch)
    drive(composition, [*tasks(LINES), "/salir"])
    calls = model_calls(provider)
    first_summary = next(i for i, c in enumerate(calls) if any(is_summary(m) for m in c))
    chosen = [calls[0], calls[1], calls[first_summary - 1], calls[first_summary], calls[-1]]

    for messages in chosen:
        assert blocks_of(messages)
        if provider_name == "openai":
            envelope = to_openai_envelope(messages, None)
        else:
            envelope = to_anthropic_envelope(messages, None)

        assert restore_messages(envelope) == messages  # no error, nothing lost, nothing reordered
        assert_order_kept(envelope.payload, messages)
    assert any(is_summary(m) for m in chosen[-1]) and not any(is_summary(m) for m in chosen[0])


# --- T009: it fails closed (decision R15) -----------------------------------------------------

MISSING = "Faltan elementos del contexto esencial de la tarea; la petición no se envía."
UNREADABLE = "No se pudo leer el contexto esencial de la tarea; la petición no se envía."


def delete_rows(composition: Composition, where: str = "1 = 1") -> None:
    connection = composition.store.connection()
    connection.execute(f"DELETE FROM contexto_esencial WHERE {where}")
    connection.commit()


def test_without_a_task_the_session_gets_exactly_the_context_of_today(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: NoShell())
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    config = make_config(tmp_path, workspace=workspace, model=MODEL)
    provider = Recorder()
    composition = build(opened, config, provider, system_name="Linux")

    code, _ = drive(composition, ["tarea 1", "/salir"])

    assert code == 0 and composition.essential is None
    first = provider.calls[0]
    assert first == [*composition.history_prefix, Message(Role.USER, "tarea 1")]
    assert all(blocks_of(messages) == [] for messages in provider.calls)
    count = composition.store.connection().execute("SELECT count(*) FROM contexto_esencial")
    assert count.fetchone() == (0,)


@pytest.mark.parametrize(
    "where",
    ["1 = 1", "clave = 'objetivo'", "clave = 'criterios_ref'", "clave = 'instrucciones'"],
    ids=["all the rows", "the objective", "the reference to the criteria", "the instructions"],
)
def test_a_task_whose_elements_are_gone_never_goes_on_as_a_session_without_a_task(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    composition, provider = start(tmp_path, opened, monkeypatch)
    delete_rows(composition, where)

    code, output = drive(composition, ["tarea 1", "/salir"])

    assert code == 1  # the session ends with failure
    assert output.count(MISSING) == 1
    assert provider.calls == []  # the request never reached the model


def test_a_save_that_fails_after_the_session_was_created_leaves_no_usable_composition(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: NoShell())
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    config = make_config(tmp_path, workspace=workspace, model=MODEL)
    SqliteSessionStore(config.paths.sessions_db).close()  # the database, at the current schema
    raw = sqlite3.connect(config.paths.sessions_db)
    raw.execute(
        "CREATE TRIGGER boom BEFORE INSERT ON contexto_esencial "
        "BEGIN SELECT RAISE(ABORT, 'inyectado'); END"
    )
    raw.commit()
    raw.close()

    with pytest.raises(SessionStoreError):
        build(opened, config, Recorder(), task=make_task(), system_name="Linux")

    assert opened == []  # no composition was handed back
    check = sqlite3.connect(config.paths.sessions_db)
    try:
        assert check.execute("SELECT count(*) FROM contexto_esencial").fetchone() == (0,)
    finally:
        check.close()


def test_a_tampered_source_of_criteria_stops_the_request_before_the_model(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, provider = start(tmp_path, opened, monkeypatch)
    seen: list[EventType] = []
    for event_type in EventType:
        composition.bus.subscribe(event_type, lambda event: seen.append(event.type))
    connection = composition.store.connection()
    connection.execute("UPDATE criterios_sello SET huella = 'otra'")
    connection.commit()

    code, output = drive(composition, ["tarea 1", "/salir"])

    assert code == 1 and output.count(UNREADABLE) == 1
    assert provider.calls == []  # no old block, no criteria taken from the history
    assert seen == [EventType.CRITERIA_TAMPERED]  # the event that already existed, once; none new


def test_a_value_over_its_cap_or_a_block_that_does_not_fit_stops_the_start(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: NoShell())
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    config = make_config(tmp_path, workspace=workspace, model=MODEL)
    small = dataclasses.replace(
        config, context=ContextSettings(window_tokens=1_000, threshold_percent=45)
    )
    huge = dataclasses.replace(make_task(), objective=S_OBJECTIVE + "a" * 8_001)

    with pytest.raises(StartupError) as too_small:
        build(opened, small, Recorder(), task=make_task(), system_name="Linux")
    with pytest.raises(StartupError) as too_long:
        build(opened, config, Recorder(), task=huge, system_name="Linux")

    assert str(too_small.value) == (
        "El elemento «bloque completo» del contexto esencial supera el tope de 90 tokens."
    )
    assert str(too_long.value) == (
        "El elemento «objetivo» del contexto esencial supera el tope de 8000 caracteres."
    )
    assert S_OBJECTIVE not in str(too_long.value)
    assert not config.paths.sessions_db.exists()  # nothing was opened


def test_without_readable_criteria_the_block_has_no_criteria_section(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    composition, _ = start(tmp_path, opened, monkeypatch)

    class NoCriteria:
        def load_criteria(self, session_id: str) -> list[Any]:
            return []

    renewer = EssentialRenewer(
        SqliteEssentialStore(composition.store),
        NoCriteria(),
        SETTINGS,
        session_id=composition.session_id,
        model=lambda: MODEL,
    )
    history = list(composition.history_prefix)

    renewer.renew(history)

    block = blocks_of(history)[0].content
    assert "Objetivo:" in block and "Criterios de aceptación" not in block
    assert "Reglas:" in block and block.endswith(S_RULES)
