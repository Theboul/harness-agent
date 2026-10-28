"""The SQLite store of the messages of a conversation (HU-03-04 / T007)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harness_agent.adapters.storage import (
    SessionStoreError,
    SqliteCompactionArchive,
    SqliteMessageStore,
    SqliteSessionStore,
)
from harness_agent.core import (
    CompactionCommit,
    Event,
    EventType,
    Message,
    MessageRecord,
    Role,
    StoredConversation,
    TokenUsage,
    ToolCall,
    ToolResult,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
CALL = ToolCall("c1", "leer_archivo", {"path": "a.txt", "lineas": [1, 2], "ver": True})


def record(position: int, message: Message, event_id: str | None = None) -> MessageRecord:
    return MessageRecord(position, message, event_id)


def conversation() -> list[MessageRecord]:
    return [
        record(1, Message(Role.USER, "hola ñandú"), "e1"),
        record(2, Message(Role.ASSISTANT, "", (CALL,), usage=TokenUsage(7, 9))),
        record(
            3,
            Message(
                Role.TOOL, "salida", tool_result=ToolResult("c1", "salida", True), is_external=True
            ),
            "e2",
        ),
        record(4, Message(Role.ASSISTANT, "listo", usage=TokenUsage(1, 2)), "e3"),
    ]


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteSessionStore]:
    opened = SqliteSessionStore(tmp_path / "sesiones.db", clock=lambda: NOW)
    yield opened
    opened.close()


@pytest.fixture
def messages(store: SqliteSessionStore) -> SqliteMessageStore:
    return SqliteMessageStore(store, clock=lambda: NOW)


@pytest.fixture
def session(store: SqliteSessionStore) -> str:
    return store.create_session(model="modelo-a").id


def count(store: SqliteSessionStore, table: str = "mensajes") -> int:
    return int(store.connection().execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def save_event(store: SqliteSessionStore, session: str, event_id: str, kind: EventType) -> None:
    store.save_event(Event.create(session, kind, {}, event_id=event_id, timestamp=NOW))


def test_what_is_appended_is_read_back_with_every_field(
    messages: SqliteMessageStore, session: str
) -> None:
    messages.append(session, conversation())

    stored = messages.load_conversation(session)

    assert isinstance(stored, StoredConversation) and stored.session_id == session
    assert [m.record for m in stored.messages] == conversation()
    assert stored.model == "modelo-a" and not stored.is_task and stored.summary is None
    assert messages.last_position(session) == 4


def test_a_batch_with_something_that_cannot_be_serialized_saves_none_of_it(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    bad = Message(Role.ASSISTANT, SENTINEL, (ToolCall("c9", "x", {"o": object()}),))

    with pytest.raises(SessionStoreError) as caught:
        messages.append(session, [*conversation()[:1], record(2, bad)])

    assert SENTINEL not in str(caught.value) and caught.value.__cause__ is None
    assert count(store) == 0 and messages.last_position(session) == 0


def test_a_batch_the_engine_refuses_leaves_the_table_as_it_was(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    messages.append(session, conversation()[:1])
    system = Message(Role.SYSTEM, SENTINEL)

    with pytest.raises(SessionStoreError) as caught:
        messages.append(session, [record(2, Message(Role.USER, "ok")), record(3, system)])

    assert SENTINEL not in str(caught.value) and caught.value.__cause__ is None
    assert count(store) == 1


def test_an_unknown_session_is_refused_with_the_fixed_error(
    store: SqliteSessionStore, messages: SqliteMessageStore
) -> None:
    with pytest.raises(SessionStoreError):
        messages.append("no-existe", conversation()[:1])

    assert count(store) == 0


def test_the_same_record_again_is_ignored_and_a_different_one_in_its_place_fails(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    messages.append(session, conversation())
    before = store.connection().execute("SELECT * FROM mensajes ORDER BY posicion").fetchall()

    messages.append(session, conversation())  # a retried batch
    messages.append(session, conversation()[1:3])
    with pytest.raises(SessionStoreError) as caught:
        messages.append(session, [record(1, Message(Role.USER, SENTINEL), "e1")])

    assert SENTINEL not in str(caught.value)
    after = store.connection().execute("SELECT * FROM mensajes ORDER BY posicion").fetchall()
    assert after == before


def test_a_conflict_in_a_later_record_does_not_save_the_earlier_new_ones(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    messages.append(session, conversation()[:1])

    with pytest.raises(SessionStoreError):
        messages.append(
            session, [record(2, Message(Role.USER, "nuevo")), record(1, Message(Role.USER, "otro"))]
        )

    assert count(store) == 1


def test_the_creation_time_is_the_one_of_the_clock(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    messages.append(session, conversation()[:1])

    stamp = store.connection().execute("SELECT creado FROM mensajes").fetchone()[0]

    assert stamp == NOW.isoformat()


def test_last_position_is_per_session(
    store: SqliteSessionStore, messages: SqliteMessageStore
) -> None:
    first = store.create_session().id
    second = store.create_session().id
    messages.append(first, conversation())

    assert messages.last_position(first) == 4 and messages.last_position(second) == 0
    assert messages.last_position("no-existe") == 0


def test_a_session_that_does_not_exist_reads_as_none(messages: SqliteMessageStore) -> None:
    assert messages.load_conversation("no-existe") is None


def test_a_session_without_messages_reads_empty(messages: SqliteMessageStore, session: str) -> None:
    stored = messages.load_conversation(session)

    assert stored is not None and stored.messages == () and stored.events_without_row == 0
    assert stored.last_event_type is None and stored.summary is None


def test_a_task_session_is_recognised_by_its_criteria_or_its_essential_context(
    store: SqliteSessionStore, messages: SqliteMessageStore
) -> None:
    with_criteria = store.create_session().id
    with_essential = store.create_session().id
    plain = store.create_session().id
    connection = store.connection()
    connection.execute(
        "INSERT INTO criterios (sesion_id, orden, descripcion, tipo) "
        "VALUES (?, 1, 'x', 'semantico')",
        (with_criteria,),
    )
    connection.execute(
        "INSERT INTO contexto_esencial (sesion_id, clave, orden, valor, origen, creado) "
        "VALUES (?, 'objetivo', 1, 'v', 'o', 't')",
        (with_essential,),
    )
    connection.commit()

    flags = [messages.load_conversation(s) for s in (with_criteria, with_essential, plain)]

    assert [f.is_task for f in flags if f is not None] == [True, True, False]


def test_events_of_a_message_with_no_row_are_counted_and_the_others_are_not(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    save_event(store, session, "e1", EventType.USER_MESSAGE)
    save_event(store, session, "e2", EventType.TOOL_FINISHED)
    save_event(store, session, "e3", EventType.ASSISTANT_MESSAGE)
    save_event(store, session, "e4", EventType.TOOL_REQUESTED)  # not a message event
    messages.append(session, conversation()[:1])  # points at e1

    stored = messages.load_conversation(session)

    assert stored is not None and stored.events_without_row == 2


def test_the_last_event_type_ignores_the_compactions(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    save_event(store, session, "e1", EventType.USER_MESSAGE)
    save_event(store, session, "e2", EventType.INTERRUPTED)
    save_event(store, session, "e3", EventType.CONTEXT_COMPACTED)

    stored = messages.load_conversation(session)

    assert stored is not None and stored.last_event_type == "interrupted"


def test_the_newest_summary_wins(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    connection = store.connection()
    for index, (hasta, text) in enumerate([(5, "tres"), (3, "uno"), (5, "cuatro")]):
        connection.execute(
            "INSERT INTO resumenes (id, sesion_id, evento_desde, evento_hasta, texto, creado) "
            "VALUES (?, ?, 1, ?, ?, 't')",
            (f"r{index}", session, hasta, text),
        )
    connection.commit()

    stored = messages.load_conversation(session)

    assert stored is not None and stored.summary == "cuatro"


def test_the_coverage_comes_from_the_marks_of_a_real_compaction(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    kinds = [
        EventType.USER_MESSAGE,
        EventType.ASSISTANT_MESSAGE,
        EventType.USER_MESSAGE,
        EventType.ASSISTANT_MESSAGE,
    ]
    for index, kind in enumerate(kinds, start=1):
        save_event(store, session, f"e{index}", kind)
    rows = [
        record(1, Message(Role.USER, "uno"), "e1"),
        record(2, Message(Role.ASSISTANT, "dos"), "e2"),
        record(3, Message(Role.ASSISTANT, "", (CALL,))),  # no event of its own
        record(4, Message(Role.USER, "tres"), "e3"),
        record(5, Message(Role.ASSISTANT, "cuatro"), "e4"),
        record(6, Message(Role.USER, "cola"), "e-que-nunca-se-guardo"),
    ]
    messages.append(session, rows)
    SqliteCompactionArchive(store, clock=lambda: NOW).commit_compaction(
        CompactionCommit(session, 1, 2, "resumen", "r1", "ev-resumen")
    )

    stored = messages.load_conversation(session)

    assert stored is not None
    assert [m.covered for m in stored.messages] == [False, True, None, False, False, None]
    assert stored.summary == "resumen" and stored.events_without_row == 0
    assert stored.last_event_type == "assistant_message"


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("llamadas", "esto no es json"),
        ("llamadas", "[1, 2]"),
        ("llamadas", '[{"id": "c1"}]'),
        ("uso", "esto no es json"),
        ("uso", '{"input_tokens": "x"}'),
    ],
)
def test_a_damaged_column_gives_the_fixed_error_without_its_content(
    store: SqliteSessionStore,
    messages: SqliteMessageStore,
    session: str,
    column: str,
    value: str,
) -> None:
    messages.append(session, conversation())
    store.connection().execute(
        f"UPDATE mensajes SET {column} = ? WHERE posicion = 2", (value + SENTINEL,)
    )
    store.connection().commit()

    with pytest.raises(SessionStoreError) as caught:
        messages.load_conversation(session)

    assert SENTINEL not in str(caught.value) and caught.value.__cause__ is None


def test_a_closed_store_gives_the_store_error(tmp_path: Path) -> None:
    closed = SqliteSessionStore(tmp_path / "otra.db")
    messages = SqliteMessageStore(closed)
    closed.close()

    for action in (
        lambda: messages.append("s", conversation()[:1]),
        lambda: messages.last_position("s"),
        lambda: messages.load_conversation("s"),
    ):
        with pytest.raises(SessionStoreError):
            action()


def test_it_uses_the_connection_of_the_session_store(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    messages.append(session, conversation()[:1])

    other = sqlite3.connect(store.connection().execute("PRAGMA database_list").fetchone()[2])
    try:
        assert other.execute("SELECT count(*) FROM mensajes").fetchone() == (1,)
    finally:
        other.close()


def test_without_a_clock_the_current_time_is_used_and_a_naive_time_is_taken_as_utc(
    store: SqliteSessionStore, session: str
) -> None:
    SqliteMessageStore(store).append(session, conversation()[:1])
    SqliteMessageStore(store, clock=lambda: datetime(2026, 1, 2, 3, 4)).append(
        session, conversation()[1:2]
    )

    stamps = [r[0] for r in store.connection().execute("SELECT creado FROM mensajes ORDER BY 1")]

    assert stamps[0] == "2026-01-02T03:04:00+00:00"
    assert datetime.fromisoformat(stamps[1]).tzinfo is not None


def test_an_engine_failure_in_any_operation_gives_the_fixed_error(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    store.connection().execute("ALTER TABLE mensajes RENAME TO otra")
    store.connection().commit()

    for action in (
        lambda: messages.append(session, conversation()[:1]),
        lambda: messages.last_position(session),
        lambda: messages.load_conversation(session),
    ):
        with pytest.raises(SessionStoreError) as caught:
            action()
        assert caught.value.__cause__ is None and "otra" not in str(caught.value)


class Proxy:
    """A connection that dies with a keyboard interrupt when it is asked to insert."""

    def __init__(self, real: sqlite3.Connection) -> None:
        self.real = real

    def execute(self, sql: str, *args: object) -> sqlite3.Cursor:
        if sql.startswith("INSERT"):
            raise KeyboardInterrupt()
        return self.real.execute(sql, *args)  # type: ignore[arg-type]

    def rollback(self) -> None:
        self.real.rollback()

    def commit(self) -> None:
        self.real.commit()


def test_an_interrupt_in_the_middle_of_a_batch_rolls_it_back_and_goes_on(
    store: SqliteSessionStore, session: str
) -> None:
    class Wrapped:
        def connection(self) -> Proxy:
            return Proxy(store.connection())

    messages = SqliteMessageStore(Wrapped())  # type: ignore[arg-type]

    with pytest.raises(KeyboardInterrupt):
        messages.append(session, conversation()[:2])

    assert count(store) == 0 and not store.connection().in_transaction


def test_reading_inside_a_transaction_that_is_already_open_does_not_close_it(
    store: SqliteSessionStore, messages: SqliteMessageStore, session: str
) -> None:
    connection = store.connection()
    connection.execute("BEGIN")

    stored = messages.load_conversation(session)

    assert stored is not None and connection.in_transaction
    connection.rollback()
