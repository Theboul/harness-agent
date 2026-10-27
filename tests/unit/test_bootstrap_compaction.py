"""compose() and run_session() wire the automatic compaction (HU-02-03 / T008, R11, R12).

The provider is a ``FakeProvider`` with an exact script: the answers of the agent and, where a
compaction is expected, the answer to the summary call in its place. The database is a temporary
file; nothing reaches the network.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition, run_session
from harness_agent.core import (
    ContextCompactor,
    ContextSettings,
    Event,
    EventType,
    Message,
    ProviderError,
    ProviderResponse,
    QuotaExceeded,
    Role,
    is_summary,
    summary_text,
    threshold_tokens,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config

MODEL = "openai/modelo-de-prueba"
SUMMARY_PROMPT_START = "Resume la conversación"
FILLING = "relleno " * 48  # about 100 estimated tokens per reply


def reply(n: int) -> ProviderResponse:
    return ProviderResponse(content=f"respuesta {n} {FILLING}")


def summary(text: str = "Resumen de lo anterior.") -> ProviderResponse:
    return ProviderResponse(content=text)


def settings(percent: int = 45, **more: object) -> ContextSettings:
    fields: dict[str, object] = {
        "window_tokens": 2_400,
        "threshold_percent": percent,
        "recent_percent": 5,
        "min_recent_messages": 4,
        "summary_tokens": 100,
    }
    fields.update(more)
    return ContextSettings(**fields)  # type: ignore[arg-type]


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def make(
    tmp_path: Path,
    opened: list[Composition],
    script: list[ProviderResponse],
    context: ContextSettings,
) -> tuple[Composition, FakeProvider]:
    provider = FakeProvider(script)
    config = replace(make_config(tmp_path, workspace=None, model=MODEL), context=context)
    return build(opened, config, provider), provider


async def run(composition: Composition, lines: int) -> str:
    text = "".join(f"tarea {n}\n" for n in range(1, lines + 1)) + "/salir\n"
    output = io.StringIO()
    code = await run_session(composition, input_stream=io.StringIO(text), output=output)
    assert code == 0
    return output.getvalue()


def summary_calls(provider: FakeProvider) -> list[int]:
    """The positions of the calls that were a summary request."""
    return [
        index
        for index, messages in enumerate(provider.received)
        if messages[0].role is Role.SYSTEM and messages[0].content.startswith(SUMMARY_PROMPT_START)
    ]


def summaries_in(messages: list[Message]) -> list[Message]:
    return [message for message in messages if is_summary(message)]


# --- the composition ------------------------------------------------------------------------------


def test_compose_hands_over_a_compactor(tmp_path: Path, opened: list[Composition]) -> None:
    composition, _ = make(tmp_path, opened, [reply(1)], ContextSettings())

    assert isinstance(composition.compactor, ContextCompactor)


async def test_below_the_threshold_a_request_makes_no_summary_call(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(tmp_path, opened, [reply(1), reply(2)], ContextSettings())

    await run(composition, 2)

    assert provider.call_count == 2 and summary_calls(provider) == []


# --- a long session -------------------------------------------------------------------------------


async def test_a_big_context_is_compacted_before_the_call_of_the_loop(
    tmp_path: Path, opened: list[Composition]
) -> None:
    script = [reply(n) for n in range(1, 5)] + [summary("Resumen del trabajo."), reply(5)]
    composition, provider = make(tmp_path, opened, script, settings())

    output = await run(composition, 5)

    assert summary_calls(provider) == [4]
    assert provider.received_tools[4] is None  # the summary call has no tools
    assert provider.received_tools[5] is not None
    sent = provider.received[5]
    roles = [m.role for m in sent]
    assert roles[0] is Role.SYSTEM  # the prefix of the session
    assert sent[1].content == "tarea 1"  # the protected request
    found = summaries_in(sent)
    assert len(found) == 1 and summary_text(found[0]) == "Resumen del trabajo."
    assert sent.index(found[0]) == 2
    contents = " ".join(m.content for m in sent)
    for old in ("respuesta 1 ", "tarea 2", "respuesta 2 "):
        assert old not in contents  # the old part is gone from the view...
    for recent in ("tarea 3", "respuesta 3 ", "tarea 4", "respuesta 4 ", "tarea 5"):
        assert recent in contents  # ...and the recent messages are whole
    assert "sigue por encima del umbral" not in output  # compacted below the threshold


async def test_the_compacted_view_persists_between_the_lines_of_the_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    script = [reply(n) for n in range(1, 5)] + [summary("uno"), reply(5), reply(6)]
    script += [summary("dos"), reply(7)]
    composition, provider = make(tmp_path, opened, script, settings())

    await run(composition, 7)

    assert summary_calls(provider) == [4, 7]
    assert provider.received[7][1].content.startswith("Resumen anterior:\nuno")
    last = provider.received[8]
    found = summaries_in(last)
    assert len(found) == 1 and summary_text(found[0]) == "dos"  # one summary, the last one
    assert "respuesta 1 " not in " ".join(m.content for m in last)


async def test_the_summary_and_the_covered_events_are_stored_once(
    tmp_path: Path, opened: list[Composition]
) -> None:
    script = [reply(n) for n in range(1, 5)] + [summary("Resumen del trabajo."), reply(5)]
    composition, _ = make(tmp_path, opened, script, settings())

    await run(composition, 5)

    stored = composition.store.load_session(composition.session_id)
    assert [e.type for e in stored].count(EventType.CONTEXT_COMPACTED) == 1
    connection = composition.store.connection()
    assert connection.execute("SELECT count(*), min(texto) FROM resumenes").fetchone() == (
        1,
        "Resumen del trabajo.",
    )
    covered = connection.execute("SELECT count(*) FROM events WHERE compacted_by IS NOT NULL")
    assert covered.fetchone()[0] >= 1


def test_the_recorder_skips_the_event_that_the_archive_already_stored(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = make(tmp_path, opened, [reply(1)], settings())
    event = Event.create(composition.session_id, EventType.CONTEXT_COMPACTED, {"desde": 1})

    composition.bus.emit(event)  # what the compactor does after the commit

    stored = composition.store.load_session(composition.session_id)
    assert EventType.CONTEXT_COMPACTED not in [e.type for e in stored]


async def test_a_context_still_too_big_after_compacting_warns_in_the_output_of_the_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    script = [reply(1), reply(2), reply(3), summary(), reply(4)]
    composition, provider = make(tmp_path, opened, script, settings(percent=38))

    output = await run(composition, 4)

    assert "Aviso: el contexto sigue por encima del umbral tras compactar" in output
    assert output.count("Aviso: el contexto sigue por encima del umbral") == 1
    assert provider.call_count == 5  # no retry: one summary call only


# --- the model of the configuration ---------------------------------------------------------------


async def test_the_window_of_the_model_in_use_decides_the_threshold(
    tmp_path: Path, opened: list[Composition]
) -> None:
    big = settings(windows=((MODEL, 1_000_000),))
    composition, provider = make(tmp_path, opened, [reply(n) for n in range(1, 6)], big)

    await run(composition, 5)

    assert summary_calls(provider) == [] and provider.call_count == 5
    assert threshold_tokens(big, MODEL) == 450_000


async def test_the_default_window_applies_to_a_model_that_is_not_listed(
    tmp_path: Path, opened: list[Composition]
) -> None:
    other = settings(windows=(("otro/modelo", 1_000_000),))
    script = [reply(n) for n in range(1, 5)] + [summary(), reply(5)]
    composition, provider = make(tmp_path, opened, script, other)

    await run(composition, 5)

    assert summary_calls(provider) == [4]


async def test_a_failed_compaction_is_reported_with_the_fixed_event_and_the_session_goes_on(
    tmp_path: Path, opened: list[Composition]
) -> None:
    script: list[ProviderResponse | ProviderError] = [reply(n) for n in range(1, 5)]
    script += [QuotaExceeded("VALOR-DE-PRUEBA-123"), reply(5)]
    composition, provider = make(tmp_path, opened, script, settings())  # type: ignore[arg-type]
    seen: list[Event] = []
    composition.bus.subscribe(EventType.PROVIDER_ERROR, seen.append)

    output = await run(composition, 5)

    assert [e.payload for e in seen] == [
        {
            "reason": "compaction_failed",
            "error_type": "CompactionFailed",
            "message": "No se pudo compactar el contexto; el turno continúa sin compactar.",
        }
    ]
    assert provider.call_count == 6  # the fifth line was still answered
    assert summaries_in(provider.received[5]) == []  # nothing was compacted
    assert "VALOR-DE-PRUEBA-123" not in output
    stored = composition.store.load_session(composition.session_id)
    assert [e.type for e in stored].count(EventType.PROVIDER_ERROR) == 1
    assert EventType.CONTEXT_COMPACTED not in [e.type for e in stored]


async def test_a_composition_without_a_compactor_still_runs(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(tmp_path, opened, [reply(1)], settings())

    code = await run_session(
        replace(composition, compactor=None),
        input_stream=io.StringIO("tarea 1\n/salir\n"),
        output=io.StringIO(),
    )

    assert code == 0 and provider.call_count == 1
