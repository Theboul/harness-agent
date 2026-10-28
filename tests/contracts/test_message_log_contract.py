"""The contract of the message log and the resume source, run against both implementations.

The in-memory double of the tests and the SQLite adapter must behave the same way for everything
in ``specs/032-resume-session-by-id/contracts/message_log_protocol.md`` that both can express.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.storage import SqliteMessageStore, SqliteSessionStore
from harness_agent.core import (
    Event,
    EventType,
    Message,
    MessageLog,
    MessageRecord,
    ResumeSource,
    Role,
    TokenUsage,
    ToolCall,
    ToolResult,
)
from tests.unit.core.context.conversation_support import InMemoryConversationSource

SESSION = "sesion-1"
SENTINEL = "VALOR-DE-PRUEBA-123"
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
CALL = ToolCall("c1", "leer_archivo", {"path": "a.txt", "lineas": [1, 2], "ver": True})


@dataclass
class Backend:
    """One implementation with the operations the contract needs besides the protocols."""

    log: MessageLog
    source: ResumeSource
    start: Callable[[], None]
    record_event: Callable[[str, EventType], None]
    cover: Callable[[int, str], None]


def memory_backend() -> Iterator[Backend]:
    double = InMemoryConversationSource()

    def record_event(event_id: str, kind: EventType) -> None:
        double.record_event(Event.create(SESSION, kind, {}, event_id=event_id))

    def cover(through: int, summary: str) -> None:
        double.cover_through(SESSION, through, summary)

    yield Backend(double, double, lambda: None, record_event, cover)


def sqlite_backend(tmp_path: Path) -> Iterator[Backend]:
    store = SqliteSessionStore(tmp_path / "contrato.db", id_factory=lambda: SESSION)
    adapter = SqliteMessageStore(store, clock=lambda: NOW)

    def start() -> None:
        store.create_session(model="m")

    def record_event(event_id: str, kind: EventType) -> None:
        store.save_event(Event.create(SESSION, kind, {}, event_id=event_id, timestamp=NOW))

    def cover(through: int, summary: str) -> None:
        connection = store.connection()
        connection.execute(
            "UPDATE events SET compacted_by = 'r' WHERE session_id = ? AND id IN "
            "(SELECT evento_id FROM mensajes WHERE sesion_id = ? AND posicion > 1 "
            "AND posicion <= ?)",
            (SESSION, SESSION, through),
        )
        connection.execute(
            "INSERT INTO resumenes (id, sesion_id, evento_desde, evento_hasta, texto, creado) "
            "VALUES ('r', ?, 1, 1, ?, 't')",
            (SESSION, summary),
        )
        connection.commit()

    yield Backend(adapter, adapter, start, record_event, cover)
    store.close()


@pytest.fixture(params=["memory", "sqlite"])
def backend(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Backend]:
    generator = memory_backend() if request.param == "memory" else sqlite_backend(tmp_path)
    created = next(generator)
    created.start()
    yield created
    for _ in generator:
        pass


def rows() -> list[MessageRecord]:
    return [
        MessageRecord(1, Message(Role.USER, "hola ñandú"), "e1"),
        MessageRecord(2, Message(Role.ASSISTANT, "", (CALL,), usage=TokenUsage(7, 9))),
        MessageRecord(
            3,
            Message(
                Role.TOOL, "salida", tool_result=ToolResult("c1", "salida", True), is_external=True
            ),
            "e2",
        ),
        MessageRecord(4, Message(Role.ASSISTANT, "listo"), "e3"),
    ]


def read(backend: Backend) -> Any:
    stored = backend.source.load_conversation(SESSION)
    assert stored is not None
    return stored


def test_what_is_appended_is_read_back_with_every_field(backend: Backend) -> None:
    backend.log.append(SESSION, rows())

    assert [m.record for m in read(backend).messages] == rows()


def test_the_last_position_starts_at_zero_and_follows_the_batches(backend: Backend) -> None:
    assert backend.log.last_position(SESSION) == 0

    backend.log.append(SESSION, rows()[:2])
    backend.log.append(SESSION, rows()[2:])

    assert backend.log.last_position(SESSION) == 4


def test_a_batch_repeated_is_ignored(backend: Backend) -> None:
    backend.log.append(SESSION, rows())

    backend.log.append(SESSION, rows())
    backend.log.append(SESSION, rows()[1:3])

    assert [m.record for m in read(backend).messages] == rows()


def test_the_same_position_with_other_values_fails_and_saves_nothing_else(
    backend: Backend,
) -> None:
    backend.log.append(SESSION, rows()[:1])
    clash = MessageRecord(1, Message(Role.USER, SENTINEL), "e1")
    new = MessageRecord(2, Message(Role.USER, "nuevo"))

    with pytest.raises(Exception) as caught:
        backend.log.append(SESSION, [new, clash])

    assert SENTINEL not in str(caught.value)
    assert [m.record for m in read(backend).messages] == rows()[:1]


def test_an_unknown_session_reads_as_none(backend: Backend) -> None:
    assert backend.source.load_conversation("no-existe") is None


def test_the_coverage_comes_from_the_marks_of_the_events(backend: Backend) -> None:
    kinds = [EventType.USER_MESSAGE, EventType.TOOL_FINISHED, EventType.ASSISTANT_MESSAGE]
    for index, kind in enumerate(kinds, start=1):
        backend.record_event(f"e{index}", kind)
    backend.log.append(SESSION, rows())
    backend.cover(3, "resumen")

    stored = read(backend)

    # the head is not covered; the row with no event and the one after it follow their events
    assert [m.covered for m in stored.messages] == [False, None, True, False]
    assert stored.summary == "resumen"
    assert stored.events_without_row == 0 and stored.is_task is False


def test_an_event_of_a_message_that_no_row_points_at_is_counted(backend: Backend) -> None:
    backend.record_event("e1", EventType.USER_MESSAGE)
    backend.record_event("e9", EventType.ASSISTANT_MESSAGE)
    backend.log.append(SESSION, rows()[:1])

    assert read(backend).events_without_row == 1
