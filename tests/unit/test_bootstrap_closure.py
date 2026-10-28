"""The first request after a cut closes the calls without a result, once, and leaves the session
that was abandoned alone (HU-03-04 / T009c; research R21 and R24).

The sessions are left in a real file as a cut process would leave them (``seed_session``); the
compositions that resume them are built on the same file.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from harness_agent.bootstrap import Composition
from harness_agent.core import (
    SYNTHETIC_RESULT_TEXT,
    ContextSettings,
    Event,
    EventBus,
    EventType,
    Message,
    Role,
    ToolCall,
    ToolResult,
)
from tests.unit.bootstrap_support import SENTINEL
from tests.unit.resume_support import (
    drive,
    dump_all,
    dump_session,
    extend_session,
    make,
    seed_session,
)

C1 = ToolCall("c1", "leer_archivo", {"path": "a.txt"})
C2 = ToolCall("c2", "leer_archivo", {"path": "b.txt"})
C3 = ToolCall("c3", "leer_archivo", {"path": "c.txt"})
FILLING = "relleno " * 48  # about 100 estimated tokens per message


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def user(text: str) -> Message:
    return Message(Role.USER, text)


def asks(*calls: ToolCall) -> Message:
    return Message(Role.ASSISTANT, "", calls)


def answers(call: ToolCall, text: str = "ok") -> Message:
    return Message(Role.TOOL, text, tool_result=ToolResult(call.id, text))


def database(tmp_path: Path) -> Path:
    return tmp_path / "datos" / "sesiones.db"


def interruptions(composition: Composition, session: str) -> list[tuple[str, int]]:
    """``(call_id, is_error)`` of every closing event of the session, in order."""
    cursor = composition.store.connection().execute(
        "SELECT content FROM events WHERE session_id = ? AND type = 'tool_finished' ORDER BY seq",
        (session,),
    )
    found = []
    for (content,) in cursor:
        payload = json.loads(content)
        if payload.get("category") == "tool_interrupted":
            found.append((payload["call_id"], int(payload["is_error"])))
    return found


def message_rows(composition: Composition, session: str) -> list[tuple[int, str, str, Any]]:
    cursor = composition.store.connection().execute(
        "SELECT posicion, rol, contenido, evento_id FROM mensajes WHERE sesion_id = ? "
        "ORDER BY posicion",
        (session,),
    )
    return list(cursor)


async def test_resuming_after_a_cut_writes_nothing_until_the_first_request(
    tmp_path: Path, opened: list[Composition]
) -> None:
    cut = seed_session(database(tmp_path), [user("haz"), asks(C1, C2)])
    first, _ = make(tmp_path, opened)
    before = dump_all(first)

    await drive(first, f"/reanudar {cut}")

    assert dump_all(first) == before
    second, _ = make(tmp_path, opened)
    before = dump_all(second)
    await drive(second, f"/reanudar {cut}")
    assert dump_all(second) == before
    assert interruptions(second, cut) == []


async def test_the_first_request_closes_each_call_once_with_a_real_event_and_a_real_message(
    tmp_path: Path, opened: list[Composition]
) -> None:
    cut = seed_session(database(tmp_path), [user("haz"), asks(C1, C2), answers(C1)])
    current, provider = make(tmp_path, opened, "listo")

    await drive(current, f"/reanudar {cut}", "sigue")

    assert interruptions(current, cut) == [("c2", 1)]
    rows = message_rows(current, cut)
    assert [(p, r) for p, r, _, _ in rows] == [
        (1, "user"),
        (2, "assistant"),
        (3, "tool"),
        (4, "tool"),
        (5, "user"),
        (6, "assistant"),
    ]
    assert rows[3][2] == SYNTHETIC_RESULT_TEXT and rows[3][3] is not None
    assert [m.content for m in provider.received[0] if m.role is Role.TOOL] == [
        "ok",
        SYNTHETIC_RESULT_TEXT,
    ]
    seqs = [
        s
        for (s,) in current.store.connection().execute(
            "SELECT seq FROM events WHERE session_id = ? ORDER BY seq", (cut,)
        )
    ]
    assert seqs == list(range(1, len(seqs) + 1))


async def test_resuming_again_after_the_closure_does_not_close_it_twice(
    tmp_path: Path, opened: list[Composition]
) -> None:
    cut = seed_session(database(tmp_path), [user("haz"), asks(C1)])
    first, _ = make(tmp_path, opened, "listo")
    await drive(first, f"/reanudar {cut}", "sigue")
    second, _ = make(tmp_path, opened, "otra vez")
    before = dump_session(second.store.connection(), cut)

    await drive(second, f"/reanudar {cut}")
    assert dump_session(second.store.connection(), cut) == before

    await drive(second, f"/reanudar {cut}", "y más")
    assert interruptions(second, cut) == [("c1", 1)]
    assert sum(1 for *_, text, _ in message_rows(second, cut) if text == SYNTHETIC_RESULT_TEXT) == 1


async def test_two_cuts_in_a_row_are_closed_once_each(
    tmp_path: Path, opened: list[Composition]
) -> None:
    db = database(tmp_path)
    cut = seed_session(db, [user("haz"), asks(C1)])
    first, _ = make(tmp_path, opened, "listo")
    await drive(first, f"/reanudar {cut}", "sigue")
    last = first.messages.last_position(cut) if first.messages else 0
    extend_session(db, cut, [user("otra"), asks(C2)], start=last + 1)
    second, _ = make(tmp_path, opened, "ya")

    await drive(second, f"/reanudar {cut}", "continúa")

    assert interruptions(second, cut) == [("c1", 1), ("c2", 1)]
    third, _ = make(tmp_path, opened)
    await drive(third, f"/reanudar {cut}")
    assert interruptions(third, cut) == [("c1", 1), ("c2", 1)]


async def test_a_failure_in_the_middle_of_the_closures_leaves_the_rest_for_the_next_resume(
    tmp_path: Path, opened: list[Composition]
) -> None:
    cut = seed_session(database(tmp_path), [user("haz"), asks(C1, C2)])
    current, _ = make(tmp_path, opened, "listo")

    class Flaky:
        """Drops the closure of the second call before anybody sees it, as a failure would."""

        def __init__(self, real: EventBus) -> None:
            self.real = real

        def subscribe(self, event_type: EventType, handler: Any) -> None:
            self.real.subscribe(event_type, handler)

        def emit(self, event: Event) -> None:
            if event.payload.get("category") == "tool_interrupted" and (
                event.payload.get("call_id") == "c2"
            ):
                raise RuntimeError(SENTINEL)
            self.real.emit(event)

    flaky = replace(current, bus=Flaky(current.bus))  # type: ignore[arg-type]
    code, shown = await drive(flaky, f"/reanudar {cut}", "sigue")

    assert code == 1 and SENTINEL not in shown
    assert interruptions(current, cut) == [("c1", 1)]
    again, _ = make(tmp_path, opened, "listo")
    code_again, shown_again = await drive(again, f"/reanudar {cut}", "sigue")
    assert code_again == 0, shown_again
    assert interruptions(again, cut) == [("c1", 1), ("c2", 1)], shown_again


async def test_nothing_writes_in_the_session_that_was_left(
    tmp_path: Path, opened: list[Composition]
) -> None:
    db = database(tmp_path)
    left = seed_session(db, [user("vieja"), asks(C3)])
    resumed = seed_session(db, [user("haz"), asks(C1)])
    current, _ = make(tmp_path, opened, "listo")
    connection = current.store.connection()
    before = dump_session(connection, left)

    await drive(current, f"/reanudar {resumed}", "sigue")
    current.bus.emit(Event.create(left, EventType.USER_MESSAGE, {"content": "ajeno"}))

    after = dump_session(connection, left)
    assert after["mensajes"] == before["mensajes"] and after["resumenes"] == before["resumenes"]
    assert len(after["events"]) == len(before["events"]) + 1  # only the event published by hand
    assert interruptions(current, left) == []
    assert interruptions(current, resumed) == [("c1", 1)]
    assert current.capture is not None and current.capture.session_id == resumed
    assert current.essential is None


async def test_after_a_closure_the_compaction_of_the_resumed_session_works_and_is_its_own(
    tmp_path: Path, opened: list[Composition]
) -> None:
    db = database(tmp_path)
    long_story: list[Message] = []
    for n in range(6):
        reply = Message(Role.ASSISTANT, f"respuesta {n} {FILLING}")
        long_story += [user(f"pedido {n} {FILLING}"), reply]
    left = seed_session(db, [user("vieja")])
    resumed = seed_session(db, [*long_story, user("haz"), asks(C1)])
    settings = ContextSettings(
        window_tokens=2_400,
        threshold_percent=45,
        recent_percent=5,
        min_recent_messages=4,
        summary_tokens=100,
    )
    current, provider = make(tmp_path, opened, "Resumen de lo anterior.", "listo", context=settings)

    await drive(current, f"/reanudar {resumed}", "sigue")

    connection = current.store.connection()
    summaries = connection.execute("SELECT sesion_id FROM resumenes").fetchall()
    assert summaries == [(resumed,)]
    cursor = connection.execute("SELECT type FROM events WHERE session_id = ?", (resumed,))
    types = [kind for (kind,) in cursor]
    assert "context_compacted" in types and "provider_error" not in types
    assert dump_session(connection, left)["resumenes"] == []
    assert interruptions(current, resumed) == [("c1", 1)]
    assert len(provider.received) == 2  # the summary call and the request
