"""A session cut at any point of a turn resumes into a valid history (HU-03-04 / T010b).

The cuts are the states a dead process leaves in the file: ``seed_session`` writes the messages
and the events of a conversation up to one point with the real stores. A composition built on the
same file resumes it and sends a request; the model double answers from what it receives.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.bootstrap import Composition
from harness_agent.core import (
    SYNTHETIC_RESULT_TEXT,
    Message,
    ProviderResponse,
    Role,
    ToolCall,
    ToolDefinition,
    ToolResult,
    check_structure,
)
from harness_agent.core.loop import AgentLoop
from tests.integration.test_resume_agent_loop import (
    Smart,
    database,
    live,
    process,
)
from tests.unit.resume_support import extend_session, seed_session


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


C1 = ToolCall("k1", "leer_archivo", {"path": "a.txt"})
C2 = ToolCall("k2", "leer_archivo", {"path": "b.txt"})
TURN = [
    Message(Role.USER, "haz"),
    Message(Role.ASSISTANT, "", (C1, C2)),
    Message(Role.TOOL, "uno", tool_result=ToolResult("k1", "uno")),
    Message(Role.TOOL, "dos", tool_result=ToolResult("k2", "dos")),
    Message(Role.ASSISTANT, "listo"),
]
CUTS = {
    "after the request": (1, None, 0),
    "after the answer that asks for the tools": (2, None, 2),
    "between two results": (3, None, 1),
    "after the last result": (4, None, 0),
    "after the final answer": (5, None, 0),
    "between a message and its event": (3, 3, 1),
    "right after the request, event lost": (1, 1, 0),
}


def closures(path: Path, session: str) -> list[str]:
    store = SqliteSessionStore(path)
    try:
        cursor = store.connection().execute(
            "SELECT content FROM events WHERE session_id = ? AND type = 'tool_finished' "
            "ORDER BY seq",
            (session,),
        )
        found = [json.loads(content) for (content,) in cursor]
    finally:
        store.close()
    return [e["call_id"] for e in found if e.get("category") == "tool_interrupted"]


def closing_rows(path: Path, session: str) -> list[str]:
    store = SqliteSessionStore(path)
    try:
        cursor = store.connection().execute(
            "SELECT resultado_id FROM mensajes WHERE sesion_id = ? AND contenido = ? "
            "ORDER BY posicion",
            (session, SYNTHETIC_RESULT_TEXT),
        )
        return [call_id for (call_id,) in cursor]
    finally:
        store.close()


@pytest.mark.parametrize("name", list(CUTS))
async def test_at_every_point_of_a_turn_the_history_the_model_gets_is_valid(
    tmp_path: Path, opened: list[Composition], name: str
) -> None:
    kept, unsaved_from, dangling = CUTS[name]
    cut = seed_session(database(tmp_path), TURN[:kept], unsaved_events_from=unsaved_from)
    current = process(tmp_path, opened, prefix="b")

    code = await current.run(f"/reanudar {cut}", "sigue")

    assert code == 0, current.output
    sent = current.provider.received[0]
    assert check_structure(sent) is None  # no call without a result, no result without a call
    AgentLoop._check_history(sent[:-1])  # noqa: SLF001 - the validation the loop really applies
    assert [m for m in sent if m in TURN[:kept]] == TURN[:kept]  # what was saved comes back
    assert len(closures(database(tmp_path), cut)) == dangling
    assert len(closing_rows(database(tmp_path), cut)) == dangling
    notice = [line for line in current.output.splitlines() if "reanudada" in line]
    assert len(notice) == 1
    assert ("se cerr" in notice[0]) is bool(dangling)


async def test_a_real_cancellation_leaves_a_session_that_says_it_was_interrupted(
    tmp_path: Path, opened: list[Composition]
) -> None:
    class Hanging(Smart):
        async def complete(
            self, messages: list[Message], tools: list[ToolDefinition] | None = None
        ) -> ProviderResponse:
            if messages[-1].role is Role.TOOL:
                await asyncio.Event().wait()  # the model never answers
            return await super().complete(messages, tools)

    first = process(tmp_path, opened, provider=Hanging())
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(first.run("tarea 1"), timeout=1.0)
    first.composition.close()

    second = process(tmp_path, opened, prefix="b")
    await second.run(f"/reanudar {first.session_id}", "sigue")

    notice = [line for line in second.output.splitlines() if "reanudada" in line]
    assert "Se había interrumpido." in notice[0]
    assert check_structure(second.provider.received[0]) is None


async def test_resuming_twice_with_no_request_in_between_writes_nothing_and_closes_nothing(
    tmp_path: Path, opened: list[Composition]
) -> None:
    cut = seed_session(database(tmp_path), TURN[:2])
    path = database(tmp_path)
    for prefix in ("b", "c"):
        lived = process(tmp_path, opened, prefix=prefix)
        connection = lived.composition.store.connection()
        before = connection.execute("SELECT count(*) FROM events").fetchone()[0]
        rows_before = connection.execute("SELECT count(*) FROM mensajes").fetchone()[0]

        await lived.run(f"/reanudar {cut}")

        assert connection.execute("SELECT count(*) FROM events").fetchone()[0] == before
        assert connection.execute("SELECT count(*) FROM mensajes").fetchone()[0] == rows_before
    assert closures(path, cut) == []


async def test_resuming_asking_and_resuming_again_closes_each_call_once(
    tmp_path: Path, opened: list[Composition]
) -> None:
    path = database(tmp_path)
    cut = seed_session(path, TURN[:2])
    first = process(tmp_path, opened, prefix="b")
    await first.run(f"/reanudar {cut}", "sigue")
    assert sorted(closures(path, cut)) == ["k1", "k2"]

    second = process(tmp_path, opened, prefix="c")
    await second.run(f"/reanudar {cut}")
    third = process(tmp_path, opened, prefix="d")
    await third.run(f"/reanudar {cut}", "y más")

    assert sorted(closures(path, cut)) == ["k1", "k2"]  # nothing was closed twice
    assert sorted(closing_rows(path, cut)) == ["k1", "k2"]


async def test_two_cuts_in_the_same_session_are_each_closed_once(
    tmp_path: Path, opened: list[Composition]
) -> None:
    path = database(tmp_path)
    cut = seed_session(path, TURN[:2])
    first = process(tmp_path, opened, prefix="b")
    await first.run(f"/reanudar {cut}", "sigue")
    second_cut = ToolCall("k9", "leer_archivo", {"path": "c.txt"})
    store = SqliteSessionStore(path)
    try:
        last = (
            store.connection()
            .execute("SELECT max(posicion) FROM mensajes WHERE sesion_id = ?", (cut,))
            .fetchone()[0]
        )
    finally:
        store.close()
    extend_session(
        path,
        cut,
        [Message(Role.USER, "otra"), Message(Role.ASSISTANT, "", (second_cut,))],
        start=last + 1,
    )

    second = process(tmp_path, opened, prefix="c")
    await second.run(f"/reanudar {cut}", "continúa")

    assert sorted(closures(path, cut)) == ["k1", "k2", "k9"]
    assert sorted(closing_rows(path, cut)) == ["k1", "k2", "k9"]


async def test_the_compaction_after_a_closure_works_on_a_long_cut_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    first = process(tmp_path, opened)
    await live(first, 15, summaries=2)
    first.composition.close()
    path = database(tmp_path)
    store = SqliteSessionStore(path)
    try:
        last = (
            store.connection()
            .execute("SELECT max(posicion) FROM mensajes WHERE sesion_id = ?", (first.session_id,))
            .fetchone()[0]
        )
    finally:
        store.close()
    extend_session(
        path,
        first.session_id,
        [Message(Role.USER, "corte"), Message(Role.ASSISTANT, "", (C1,))],
        start=last + 1,
    )

    second = process(tmp_path, opened, prefix="b")
    await live(second, 12, resume=first.session_id)

    assert second.provider.summaries >= 1
    assert closures(path, first.session_id) == ["k1"]
    kinds = [
        kind
        for (kind,) in second.composition.store.connection().execute(
            "SELECT type FROM events WHERE session_id = ?", (first.session_id,)
        )
    ]
    assert "provider_error" not in kinds and "context_compacted" in kinds
