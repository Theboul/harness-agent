"""A long simulated session with the real loop and the real SQLite store (HU-02-03 / T009).

``compose()`` builds the system; the provider is a ``FakeProvider`` with an exact script. Each line
of the session is one tool call (listing the work area, so the loop produces its real events) and
one final answer; the odd lines have an assistant message without text, only the call, which has
no event of its own. Before each line the compactor runs, as ``run_session`` does.

With this configuration the context passes the threshold before the 9th line and again before the
15th (measured, not assumed: the tests assert where the summary calls fall).
"""

from __future__ import annotations

import asyncio
import io
import json
import re
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.bootstrap import Composition
from harness_agent.config import Limits
from harness_agent.core import (
    ContextSettings,
    EventType,
    Message,
    ProviderResponse,
    Role,
    Shell,
    ShellResult,
    ToolCall,
    ToolDefinition,
    estimate_messages,
    estimate_tool_definition,
    is_summary,
    parse_task,
    summary_text,
    threshold_tokens,
)
from harness_agent.core.interfaces import ProviderError, QuotaExceeded
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config

MODEL = "openai/modelo-de-prueba"
SUMMARY_START = "Resume la conversación"
SENTINEL = "VALOR-DE-PRUEBA-123"
PAD = "relleno " * 20
FIXED_FAILURE = {
    "reason": "compaction_failed",
    "error_type": "CompactionFailed",
    "message": "No se pudo compactar el contexto; el turno continúa sin compactar.",
}
PUBLISH_WARNING = (
    "Aviso: la compactación se guardó, pero no se pudo avisar a todos los suscriptores del "
    "evento; el turno continúa con el contexto compactado."
)
Step = ProviderResponse | ProviderError


def settings(**more: object) -> ContextSettings:
    fields: dict[str, object] = {
        "window_tokens": 3_000,
        "threshold_percent": 50,
        "recent_percent": 5,
        "min_recent_messages": 4,
        "summary_tokens": 100,
    }
    fields.update(more)
    return ContextSettings(**fields)  # type: ignore[arg-type]


def line_script(n: int) -> list[Step]:
    """One tool call (no text on the odd lines) and one final answer, with a mark of its own."""
    text = "" if n % 2 else f"reviso {n} marca-R{n:03d} {PAD}"
    call = ToolCall(f"c{n}", "listar_archivos", {"path": "."})
    return [
        ProviderResponse(content=text, tool_calls=[call]),
        ProviderResponse(content=f"respuesta {n} marca-A{n:03d} {PAD}"),
    ]


def script_for(lines: int, summaries: dict[int, Step] | None = None) -> list[Step]:
    """The answers for ``lines`` lines; ``summaries[n]`` is the answer to a summary call made
    just before line ``n``."""
    script: list[Step] = []
    for n in range(1, lines + 1):
        if summaries and n in summaries:
            script.append(summaries[n])
        script.extend(line_script(n))
    return script


def summary_calls(provider: FakeProvider) -> list[int]:
    return [
        index
        for index, messages in enumerate(provider.received)
        if messages[0].role is Role.SYSTEM and messages[0].content.startswith(SUMMARY_START)
    ]


class NoShell(Shell):
    @property
    def interpreter_name(self) -> str:
        return "bash"

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        raise AssertionError("no command runs in these tests")

    def terminate_running(self) -> None:
        """Nothing runs."""


class Session:
    """A composition, its history and the output of the warnings, driven line by line."""

    def __init__(self, composition: Composition, provider: FakeProvider) -> None:
        self.composition = composition
        self.provider = provider
        self.history: list[Message] = list(composition.history_prefix)
        self.warnings = io.StringIO()
        composition.warning_sink.stream = self.warnings

    async def compact(self) -> Any:
        assert self.composition.compactor is not None
        return await self.composition.compactor.before_turn(self.history)

    async def step(self, n: int) -> Any:
        result = await self.compact()
        await self.composition.loop.run_turn(
            session_id=self.composition.session_id,
            task=f"tarea {n} marca-U{n:03d}",
            history=self.history,
        )
        return result

    async def run(self, first: int, last: int) -> None:
        for n in range(first, last + 1):
            await self.step(n)

    def rows(self, where: str = "1 = 1") -> list[tuple[Any, ...]]:
        cursor = self.composition.store.connection().execute(
            "SELECT id, session_id, seq, type, content, created_at, compacted_by FROM events "
            f"WHERE {where} ORDER BY seq"
        )
        return cursor.fetchall()

    def table(self, name: str) -> list[tuple[Any, ...]]:
        return self.composition.store.connection().execute(f"SELECT * FROM {name}").fetchall()


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def start(
    tmp_path: Path,
    opened: list[Composition],
    script: list[Step],
    *,
    context: ContextSettings | None = None,
    provider: FakeProvider | None = None,
    **options: Any,
) -> Session:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "a.txt").write_text("contenido", encoding="utf-8")
    config = replace(
        make_config(tmp_path, workspace=workspace, model=MODEL),
        limits=Limits(max_turns=500, max_output_tokens=777),
        context=context if context is not None else settings(),
    )
    chosen = provider if provider is not None else FakeProvider(script)
    composition = build(opened, config, chosen, **options)
    return Session(composition, chosen)


# --- AC-01: the context after one compaction ---------------------------------------------------


async def test_ac01_a_long_session_makes_one_summary_call_and_the_loop_gets_the_agreed_context(
    tmp_path: Path, opened: list[Composition]
) -> None:
    summary = ProviderResponse(content="Resumen uno de lo hecho.")
    session = start(tmp_path, opened, script_for(9, {9: summary}))
    await session.run(1, 8)
    before = list(session.history)
    assert session.provider.call_count == 16 and summary_calls(session.provider) == []

    await session.step(9)

    assert summary_calls(session.provider) == [16]  # one call, in the place of the compaction
    request = session.provider.received[16]
    assert session.provider.received_tools[16] is None  # a separate call with no tools
    assert [m.role for m in request] == [Role.SYSTEM, Role.USER]
    body = request[1].content
    assert "marca-A001" in body and "marca-A002" in body  # the old part goes in
    assert "marca-U001" not in body  # the protected request does not
    for message in session.history[:2]:  # the prefix is not in the call either
        assert message.content not in body
    marks = re.findall(r"marca-[A-Z]\d{3}", " ".join(m.content for m in before[-4:]))
    assert marks and not any(mark in body for mark in marks)  # nor do the recent messages
    context = session.provider.received[17]  # the first call of the loop for line 9
    prefix = list(session.composition.history_prefix)
    assert context[: len(prefix)] == prefix
    assert context[len(prefix)].content == "tarea 1 marca-U001"
    assert is_summary(context[len(prefix) + 1])
    assert summary_text(context[len(prefix) + 1]) == "Resumen uno de lo hecho."
    assert context[len(prefix) + 2 : len(prefix) + 6] == before[-4:]  # the recent ones, as were
    assert context[len(prefix) + 6].content == "tarea 9 marca-U009"
    assert sum(1 for m in context if is_summary(m)) == 1


async def test_below_the_threshold_nothing_is_called_or_written(
    tmp_path: Path, opened: list[Composition]
) -> None:
    session = start(tmp_path, opened, script_for(3), context=settings(window_tokens=100_000))
    await session.run(1, 3)
    rows_before = session.rows()
    resumenes_before = session.table("resumenes")

    assert await session.compact() is None

    assert summary_calls(session.provider) == []
    assert session.rows() == rows_before and session.table("resumenes") == resumenes_before == []


# --- AC-02: the stored history -----------------------------------------------------------------


async def test_ac02_nothing_is_lost_the_covered_events_are_marked_and_a_second_compaction_replaces(
    tmp_path: Path, opened: list[Composition]
) -> None:
    first = ProviderResponse(content="Resumen uno SENT-S1.")
    second = ProviderResponse(content="Resumen dos SENT-S2.")
    session = start(tmp_path, opened, script_for(15, {9: first, 15: second}))
    await session.run(1, 8)
    before = session.rows()

    await session.run(9, 9)

    after = session.rows()
    untouched = [row[:6] for row in after if row[3] != "context_compacted"]
    assert untouched[: len(before)] == [row[:6] for row in before]  # same rows, same content
    assert len(after) > len(before)
    (resumen,) = session.table("resumenes")
    summary_id, _, desde, hasta, text, _created = resumen
    assert text == "Resumen uno SENT-S1."
    covered = [row for row in after if row[6] == summary_id]
    assert [row[2] for row in covered] == list(range(desde, hasta + 1))  # one range, no hole
    assert all(row[6] is None for row in after if row not in covered)
    (compacted,) = [row for row in after if row[3] == "context_compacted"]
    assert json.loads(compacted[4]) == {"desde": desde, "hasta": hasta, "eventos": len(covered)}
    assert 1 not in [row[2] for row in covered]  # the protected request stays uncovered

    await session.run(10, 15)

    assert summary_calls(session.provider)[1] == 29  # exactly one call per compaction
    assert session.provider.received[29][1].content.startswith(
        "Resumen anterior:\nResumen uno SENT-S1."
    )
    sent = session.provider.received[30]
    assert sum(1 for m in sent if is_summary(m)) == 1
    assert [summary_text(m) for m in sent if is_summary(m)] == ["Resumen dos SENT-S2."]
    ranges = [(row[2], row[3]) for row in session.table("resumenes")]
    assert len(ranges) == 2 and ranges[0][1] < ranges[1][0]  # the ranges do not overlap
    for row in session.rows("type != 'context_compacted'"):
        assert row[:6] in [r[:6] for r in after] or row[2] > after[-1][2]


# --- failures: nothing partial, the turn goes on -----------------------------------------------


def failing_steps() -> dict[str, Step]:
    return {
        "provider": QuotaExceeded(SENTINEL),
        "empty": ProviderResponse(content=""),
        "huge": ProviderResponse(content="x" * 50_000 + SENTINEL),
    }


@pytest.mark.parametrize("name", ["provider", "empty", "huge", "store"])
async def test_a_failed_compaction_leaves_nothing_partial_and_the_turn_goes_on(
    tmp_path: Path, opened: list[Composition], name: str
) -> None:
    step = failing_steps().get(name, ProviderResponse(content="Resumen válido " + SENTINEL))
    session = start(tmp_path, opened, script_for(9, {9: step}))
    await session.run(1, 8)
    rows_before = session.rows()
    view_before = list(session.history)
    if name == "store":
        session.composition.store.connection().execute(
            "CREATE TRIGGER boom BEFORE INSERT ON resumenes "
            "BEGIN SELECT RAISE(ABORT, 'inyectado'); END"
        )
        session.composition.store.connection().commit()
    errors: list[Any] = []
    session.composition.bus.subscribe(EventType.PROVIDER_ERROR, errors.append)

    assert await session.compact() is None  # fails and says so, without raising

    assert session.history == view_before  # the view did not change
    assert session.table("resumenes") == []
    assert [row for row in session.rows() if row[6] is not None] == []
    assert [e.payload for e in errors] == [FIXED_FAILURE]
    new_rows = session.rows()[len(rows_before) :]
    assert [row[3] for row in new_rows] == ["provider_error"]
    assert SENTINEL not in repr(new_rows) + session.warnings.getvalue() + repr(errors[0].payload)
    await session.composition.loop.run_turn(  # the turn goes on, without compacting
        session_id=session.composition.session_id, task="tarea 9", history=session.history
    )
    assert session.provider.call_count == 19  # 16 + the summary call + the two of line 9


class CancellingProvider(FakeProvider):
    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        if messages[0].content.startswith(SUMMARY_START):
            raise asyncio.CancelledError
        return await super().complete(messages, tools)


async def test_a_cancellation_during_the_summary_call_propagates_and_leaves_nothing(
    tmp_path: Path, opened: list[Composition]
) -> None:
    provider = CancellingProvider(script_for(9))
    session = start(tmp_path, opened, [], provider=provider)
    await session.run(1, 8)
    rows_before = session.rows()
    view_before = list(session.history)

    with pytest.raises(asyncio.CancelledError):
        await session.compact()

    assert session.rows() == rows_before and session.history == view_before
    assert session.table("resumenes") == []


# --- R16: no skip on purpose -------------------------------------------------------------------


async def test_r16_a_second_save_of_the_event_is_not_a_failed_compaction(
    tmp_path: Path, opened: list[Composition]
) -> None:
    summary = ProviderResponse(content="Resumen uno.")
    session = start(tmp_path, opened, script_for(9, {9: summary}))
    store = session.composition.store
    session.composition.bus.subscribe(EventType.CONTEXT_COMPACTED, store.save_event)  # no skip
    await session.run(1, 8)

    result = await session.compact()

    assert result is not None
    assert [r[3] for r in session.rows()].count("context_compacted") == 1  # exactly one row
    assert sum(1 for m in session.history if is_summary(m)) == 1  # the view is compacted
    assert PUBLISH_WARNING in session.warnings.getvalue()
    assert [r for r in session.rows() if r[3] == "provider_error"] == []
    await session.composition.loop.run_turn(
        session_id=session.composition.session_id, task="tarea 9", history=session.history
    )  # the turn goes on


# --- no leak -----------------------------------------------------------------------------------


async def test_nothing_sensitive_reaches_events_warnings_or_the_stored_summary(
    tmp_path: Path, opened: list[Composition]
) -> None:
    url = "https://" + "usuario" + ":" + SENTINEL + "@servidor.example/repo.git"
    summary = ProviderResponse(content="Se migró. Ver " + url + " " + SENTINEL + "-RESUMEN")
    session = start(tmp_path, opened, script_for(9, {9: summary}))
    await session.run(1, 9)

    wire = [row for row in session.rows() if row[3] in ("context_compacted", "provider_error")]
    assert wire and SENTINEL not in repr(wire) + session.warnings.getvalue()
    stored = session.table("resumenes")[0][4]
    assert SENTINEL + "-RESUMEN" in stored  # the summary text is kept as the model wrote it...
    assert "<secreto oculto>@servidor.example" in stored  # ...with the credential hidden
    assert SENTINEL + "@" not in stored and "usuario" not in stored
    in_context = " ".join(m.content for m in session.history)
    assert "usuario" not in in_context


# --- what is protected -------------------------------------------------------------------------

TASK_TEXT = (
    "## Objetivo\nProbar la compactación.\n\n"
    "## Criterios de aceptación\n"
    "- Pasa la comprobación unica-xyz\n  - comando: check-ok\n  - espera: codigo_salida == 0\n"
    "- Se ve bien criterio-semantico-xyz\n"
)


async def test_the_criteria_are_not_touched_and_never_reach_the_summary_call(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: NoShell())
    task = parse_task(TASK_TEXT)
    summary = ProviderResponse(content="Resumen uno.")
    session = start(tmp_path, opened, script_for(9, {9: summary}), task=task, system_name="Linux")
    criteria = session.table("criterios")
    seal = session.table("criterios_sello")
    assert criteria and seal
    await session.run(1, 9)

    assert session.table("criterios") == criteria and session.table("criterios_sello") == seal
    (call,) = summary_calls(session.provider)
    request = " ".join(m.content for m in session.provider.received[call])
    assert "unica-xyz" not in request and "criterio-semantico-xyz" not in request
    context = session.provider.received[call + 1]
    prefix = list(session.composition.history_prefix)
    assert context[: len(prefix)] == prefix  # environment notice and the rest, identical
    assert context[len(prefix)].content == "tarea 1 marca-U001"


# --- the window of the model -------------------------------------------------------------------


async def test_the_same_history_compacts_with_a_small_window_and_not_with_a_big_one(
    tmp_path: Path, opened: list[Composition]
) -> None:
    small = start(tmp_path / "a", opened, script_for(9, {9: ProviderResponse(content="r")}))
    big_context = settings(windows=((MODEL, 1_000_000),))
    big = start(tmp_path / "b", opened, script_for(9), context=big_context)

    await small.run(1, 9)
    await big.run(1, 9)

    assert len(summary_calls(small.provider)) == 1
    assert summary_calls(big.provider) == []


async def test_a_context_still_above_the_threshold_after_compacting_warns_and_does_not_retry(
    tmp_path: Path, opened: list[Composition]
) -> None:
    tiny = settings(threshold_percent=10)  # the prefix and the tools alone pass it
    script = script_for(2) + [ProviderResponse(content="r")]
    session = start(tmp_path, opened, script, context=tiny)
    await session.run(1, 2)
    assert summary_calls(session.provider) == []

    result = await session.compact()

    assert result is not None
    assert summary_calls(session.provider) == [4]  # one summary call, and no second one
    assert session.provider.call_count == 5
    assert "Aviso: el contexto sigue por encima del umbral tras compactar" in (
        session.warnings.getvalue()
    )


def test_the_numbers_of_the_scenario_are_the_measured_ones(
    tmp_path: Path, opened: list[Composition]
) -> None:
    session = start(tmp_path, opened, script_for(1))
    registry = session.composition.loop._registry
    tools = sum(
        estimate_tool_definition(ToolDefinition(t.name, t.description, t.schema))
        for t in registry.list()
    )
    base = estimate_messages(list(session.composition.history_prefix)) + tools

    assert threshold_tokens(settings(), MODEL) == 1_500
    assert 700 < base < 900  # the prefix and the tools alone are far below the threshold
