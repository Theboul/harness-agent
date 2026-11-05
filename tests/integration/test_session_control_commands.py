"""Acceptance checks of HU-02-04 and HU-06-04 through ``run_session`` (paper closing of both).

Real SQLite in a temporary folder, a ``FakeProvider`` and in-memory streams: no network, key or
console. The commands themselves were built by HU-06-05 and HU-03-04; these tests read each
acceptance criterion as written in its card, not as the name of the command suggests:

* HU-02-04 AC-01: ``/compactar`` compacts a context that is still below the automatic threshold,
  with the same mechanism as the automatic compaction, and says how many tokens it freed.
* HU-06-04 AC-01: ``/sesiones``, ``/reanudar <id>``, ``/nueva`` and ``/salir`` do what they say, in
  one real session.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition, forced_context_settings, run_session
from harness_agent.core import ContextSettings, Message, ProviderResponse, Role
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config

MODEL = "openai/modelo-de-prueba"
LONG = "palabra " * 150
SUMMARY_START = "Resume la conversación"
COMPACTED = re.compile(
    r"Contexto compactado: ~([\d.]+) → ~([\d.]+) tokens \(historial original conservado\)\."
)


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def make(
    root: Path,
    opened: list[Composition],
    *texts: str,
    context: ContextSettings | None = None,
) -> tuple[Composition, FakeProvider]:
    workspace = root / "trabajo"
    workspace.mkdir(parents=True, exist_ok=True)
    config = make_config(root, workspace=workspace, model=MODEL)
    if context is not None:
        config = replace(config, context=context)
    provider = FakeProvider([ProviderResponse(content=text) for text in texts])
    return build(opened, config, provider, system_name="Linux"), provider


async def drive(
    composition: Composition, source: io.StringIO | None = None, *lines: str
) -> tuple[int, str]:
    output = io.StringIO()
    stream = source or io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir")))
    code = await run_session(composition, input_stream=stream, output=output)
    return code, output.getvalue()


def requests(*marks: str) -> list[str]:
    """One long request per mark: long enough to be worth summarizing, far below the threshold."""
    return [f"{mark} {LONG}" for mark in marks]


def summary_calls(provider: FakeProvider) -> list[int]:
    return [
        index
        for index, messages in enumerate(provider.received)
        if messages[0].role is Role.SYSTEM and messages[0].content.startswith(SUMMARY_START)
    ]


def contents(messages: list[Message]) -> list[str]:
    return [m.content for m in messages if m.role is not Role.SYSTEM]


def sql(composition: Composition, query: str, *params: object) -> list[tuple[object, ...]]:
    return composition.store.connection().execute(query, params).fetchall()


def tokens(text: str) -> int:
    return int(text.replace(".", ""))


# --- HU-02-04 AC-01 ----------------------------------------------------------------------------


async def test_hu_02_04_ac01_it_compacts_below_the_threshold_and_reports_what_it_freed(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(tmp_path, opened, "r1", "r2", "r3", "r4", "RESUMEN-VIEJO")
    view = composition.model_view
    assert view is not None

    _, shown = await drive(composition, None, *requests("a", "b", "c", "d"), "/compactar")

    # four requests and not one summary call: the automatic compaction had not fired...
    assert summary_calls(provider) == [4] and provider.call_count == 5
    found = COMPACTED.search(shown)
    assert found is not None
    before, after = tokens(found.group(1)), tokens(found.group(2))
    # ...because the context was far below its threshold, and yet the command compacted it
    assert before < view.threshold_tokens
    assert after < before  # the line tells the tokens it freed: from `before` to `after`
    assert sql(composition, "SELECT count(*) FROM resumenes") == [(1,)]
    # the original history stays stored: the covered events are only marked
    marked = sql(composition, "SELECT count(*) FROM events WHERE compacted_by IS NOT NULL")
    assert marked[0][0] != 0


async def test_hu_02_04_the_manual_compaction_leaves_what_the_automatic_one_leaves(
    tmp_path: Path, opened: list[Composition]
) -> None:
    """Same history, same compaction: by hand at three requests, or by itself at the fourth."""
    texts = ("r1", "r2", "r3", "RESUMEN-VIEJO", "r4")
    manual, manual_provider = make(tmp_path / "manual", opened, *texts)
    automatic, automatic_provider = make(
        tmp_path / "automatic", opened, *texts, context=forced_context_settings(ContextSettings())
    )

    await drive(manual, None, *requests("a", "b", "c"), "/compactar", *requests("d"))
    await drive(automatic, None, *requests("a", "b", "c", "d"))

    for provider in (manual_provider, automatic_provider):
        assert summary_calls(provider) == [3] and provider.call_count == 5
    summary = [(m.role, m.content) for m in manual_provider.received[3]]
    assert summary == [(m.role, m.content) for m in automatic_provider.received[3]]
    assert contents(manual_provider.received[4]) == contents(automatic_provider.received[4])
    for query in (
        "SELECT evento_desde, evento_hasta, texto FROM resumenes",
        "SELECT type, content FROM events WHERE type = 'context_compacted'",
        "SELECT seq FROM events WHERE compacted_by IS NOT NULL ORDER BY seq",
    ):
        rows = sql(manual, query)
        assert rows and rows == sql(automatic, query)


# --- HU-06-04 AC-01 ----------------------------------------------------------------------------


async def test_hu_06_04_ac01_list_resume_new_and_exit_work_in_one_real_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past, _ = make(tmp_path, opened, "uno", "dos")
    await drive(past, None, "primera", "segunda")
    past.close()
    current, provider = make(tmp_path, opened, "tercera respuesta", "cuarta respuesta")
    source = io.StringIO(
        f"/sesiones\n/reanudar {past.session_id}\ntercera\n/nueva\ncuarta\n/sesiones\n"
        "/salir\nnunca se lee\n"
    )

    code, shown = await drive(current, source)

    first, second = shown.split("Sesiones guardadas")[1:]
    # listar: both sessions, the one of this run marked
    assert [line[:2] for line in first.splitlines() if "UTC" in line].count("* ") == 1
    assert f"* {current.session_id}" in first and f"  {past.session_id}" in first
    # reanudar <id>: that session is loaded and the next request carries its messages
    assert "Sesión reanudada: 4 mensajes." in shown
    assert contents(provider.received[0]) == ["primera", "uno", "segunda", "dos", "tercera"]
    # nueva: a clean history in another session; the one left stays listed
    new_id = shown.split("Sesión nueva: ")[1].split(".")[0]
    assert new_id not in (current.session_id, past.session_id)
    assert contents(provider.received[1]) == ["cuarta"]
    assert f"* {new_id}" in second and f"  {past.session_id}" in second
    assert len([line for line in second.splitlines() if "UTC" in line]) == 3
    # salir: the session ends with code 0 and nothing after it is read
    assert code == 0
    assert provider.call_count == 2
    assert source.read() == "nunca se lee\n"
