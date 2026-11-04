"""SqliteMemoryStore on a real file (HU-04-01, AC-01; the port of HU-00-01 as well).

The memory has its own table and no foreign key: deleting a session, its events and its messages, or
compacting it, leaves every row of ``memorias`` as it was, byte by byte. Failures are real SQLite
errors raised by triggers, so the rollback is the engine's and not a simulation.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from harness_agent.adapters.storage import (
    SessionStoreError,
    SqliteCompactionArchive,
    SqliteMemoryStore,
    SqliteSessionStore,
)
from harness_agent.core import CompactionCommit, Event, EventType, MemoryFull, MemoryStore

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"


class Rig:
    def __init__(self, path: Path, max_entries: int = 200) -> None:
        self.path = path
        self.store = SqliteSessionStore(path)
        self.ticks = 0
        self.memory = SqliteMemoryStore(self.store, max_entries=max_entries, clock=self.clock)

    def clock(self) -> datetime:
        self.ticks += 1
        return T0 + timedelta(seconds=self.ticks)

    def raw(self, sql: str, *parameters: object) -> list[tuple[object, ...]]:
        connection = sqlite3.connect(self.path)
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def memory_rows(self) -> list[tuple[object, ...]]:
        return self.raw("SELECT * FROM memorias ORDER BY id")

    def trigger(self, sql: str) -> None:
        connection = sqlite3.connect(self.path)
        try:
            connection.execute(sql)
            connection.commit()
        finally:
            connection.close()


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    made = Rig(tmp_path / "sessions.db")
    yield made
    made.store.close()


# --- remember, replace, forget, recent ---------------------------------------------------------


def test_an_entry_is_saved_and_read_back_with_its_instants(rig: Rig) -> None:
    rig.memory.remember("estilo", "tabs de 4")

    (item,) = rig.memory.recent()

    assert (item.key, item.content) == ("estilo", "tabs de 4")
    assert item.created_at == item.updated_at == T0 + timedelta(seconds=1)
    assert item.created_at is not None and item.created_at.tzinfo is not None


def test_the_same_key_replaces_the_text_and_becomes_the_most_recent(rig: Rig) -> None:
    rig.memory.remember("a", "uno")
    rig.memory.remember("b", "dos")
    rig.memory.remember("a", "tres")

    items = rig.memory.recent()

    assert [(i.key, i.content) for i in items] == [("a", "tres"), ("b", "dos")]
    assert items[0].created_at == T0 + timedelta(seconds=1)  # created does not change
    assert items[0].updated_at == T0 + timedelta(seconds=3)
    assert len(rig.memory_rows()) == 2


def test_the_most_recent_comes_first_and_a_tie_goes_to_the_newest_row(rig: Rig) -> None:
    same = SqliteMemoryStore(rig.store, clock=lambda: T0)
    for key in ("a", "b", "c"):
        same.remember(key, key)

    assert [i.key for i in same.recent()] == ["c", "b", "a"]


def test_a_naive_clock_is_taken_as_utc(rig: Rig) -> None:
    naive = SqliteMemoryStore(rig.store, clock=lambda: datetime(2026, 11, 4, 12, 0))

    naive.remember("a", "x")

    (item,) = naive.recent()
    assert item.updated_at == datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def test_a_clock_with_another_offset_is_stored_in_utc(rig: Rig) -> None:
    zone = timezone(timedelta(hours=-5))
    other = SqliteMemoryStore(rig.store, clock=lambda: datetime(2026, 11, 4, 7, 0, tzinfo=zone))

    other.remember("a", "x")

    assert other.recent()[0].updated_at == datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def test_forget_deletes_and_says_whether_there_was_one(rig: Rig) -> None:
    rig.memory.remember("a", "uno")

    assert rig.memory.forget("a") is True
    assert rig.memory.forget("a") is False
    assert rig.memory.recent() == []


# --- the cap ------------------------------------------------------------------------------------


def test_a_new_key_over_the_cap_is_refused_and_changes_no_row(tmp_path: Path) -> None:
    rig = Rig(tmp_path / "s.db", max_entries=3)
    try:
        for key in ("a", "b", "c"):
            rig.memory.remember(key, key)
        before = rig.memory_rows()

        with pytest.raises(MemoryFull):
            rig.memory.remember("d", "nuevo")

        assert rig.memory_rows() == before
        assert not rig.store.connection().in_transaction
    finally:
        rig.store.close()


def test_replacing_with_the_memory_full_still_works_and_forgetting_frees_a_place(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path / "s.db", max_entries=2)
    try:
        rig.memory.remember("a", "uno")
        rig.memory.remember("b", "dos")

        rig.memory.remember("a", "cambiado")
        rig.memory.forget("b")
        rig.memory.remember("c", "tres")

        assert {i.key: i.content for i in rig.memory.recent()} == {"a": "cambiado", "c": "tres"}
    finally:
        rig.store.close()


# --- failures ---------------------------------------------------------------------------------


def test_a_closed_store_is_a_store_error_for_every_operation(rig: Rig) -> None:
    rig.store.close()

    for call in (
        lambda: rig.memory.remember("a", "x"),
        lambda: rig.memory.forget("a"),
        lambda: rig.memory.recent(),
    ):
        with pytest.raises(SessionStoreError):
            call()


@pytest.mark.parametrize("operation", ["INSERT", "UPDATE", "DELETE"])
def test_an_engine_error_rolls_back_and_says_nothing_of_the_engine(
    rig: Rig, operation: str
) -> None:
    rig.memory.remember("a", "uno")
    before = rig.memory_rows()
    rig.trigger(
        f"CREATE TRIGGER fail BEFORE {operation} ON memorias "
        f"BEGIN SELECT RAISE(ABORT, '{SENTINEL}'); END"
    )
    call: Callable[[], object] = {
        "INSERT": lambda: rig.memory.remember("b", "dos"),
        "UPDATE": lambda: rig.memory.remember("a", "cambiado"),
        "DELETE": lambda: rig.memory.forget("a"),
    }[operation]

    with pytest.raises(SessionStoreError) as raised:
        call()

    assert SENTINEL not in str(raised.value) and raised.value.__cause__ is None
    assert rig.memory_rows() == before
    assert not rig.store.connection().in_transaction


def test_a_read_error_is_a_fixed_store_error(rig: Rig) -> None:
    rig.memory.remember("a", "uno")
    connection = rig.store.connection()
    connection.execute("ALTER TABLE memorias RENAME TO otra")

    with pytest.raises(SessionStoreError) as raised:
        rig.memory.recent()

    assert "memorias" not in str(raised.value)


def test_a_row_with_an_unreadable_instant_fails_without_repeating_it(rig: Rig) -> None:
    rig.memory.remember("a", "uno")
    connection = sqlite3.connect(rig.path)
    connection.execute("UPDATE memorias SET actualizada = ?", (SENTINEL,))
    connection.commit()
    connection.close()

    with pytest.raises(SessionStoreError) as raised:
        rig.memory.recent()

    assert SENTINEL not in str(raised.value)


class InterruptingConnection:
    """The real connection, except that it is interrupted at the first statement with a prefix."""

    def __init__(self, real: sqlite3.Connection, prefix: str) -> None:
        self._real = real
        self._prefix = prefix

    def execute(self, sql: str, *args: object) -> sqlite3.Cursor:
        if sql.startswith(self._prefix):
            raise KeyboardInterrupt
        return self._real.execute(sql, *args)  # type: ignore[arg-type]

    def commit(self) -> None:
        self._real.commit()  # pragma: no cover - the interrupt comes first

    def rollback(self) -> None:
        self._real.rollback()


class Holder:
    def __init__(self, connection: InterruptingConnection) -> None:
        self._connection = connection

    def connection(self) -> InterruptingConnection:
        return self._connection


@pytest.mark.parametrize(
    ("prefix", "call"),
    [
        ("UPDATE", lambda store: store.remember("a", "cambiado")),
        ("INSERT", lambda store: store.remember("b", "dos")),
        ("DELETE", lambda store: store.forget("a")),
    ],
)
def test_an_interrupt_in_the_middle_of_a_write_is_not_swallowed_and_rolls_back(
    rig: Rig, prefix: str, call: object
) -> None:
    rig.memory.remember("a", "uno")
    before = rig.memory_rows()
    real = rig.store.connection()
    store = SqliteMemoryStore(Holder(InterruptingConnection(real, prefix)), clock=lambda: T0)  # type: ignore[arg-type]

    with pytest.raises(KeyboardInterrupt):
        call(store)  # type: ignore[operator]

    assert rig.memory_rows() == before and not real.in_transaction


# --- the port of HU-00-01 ---------------------------------------------------------------------


def test_the_store_is_a_memory_store_and_its_port_names_are_the_same_operations(rig: Rig) -> None:
    assert isinstance(rig.memory, MemoryStore)

    rig.memory.save("pref.uno", "claro")
    rig.memory.save("pref.dos", "oscuro")

    assert [i.key for i in rig.memory.search(token_budget=1_000)] == ["pref.dos", "pref.uno"]
    assert rig.memory.delete("pref.uno") is True
    assert rig.memory.delete("pref.uno") is False


def test_search_takes_the_most_recent_entries_that_fit_the_tokens(rig: Rig) -> None:
    rig.memory.remember("viejo", "v" * 40)  # 10 tokens
    rig.memory.remember("medio", "m" * 40)
    rig.memory.remember("nuevo", "n" * 40)

    assert [i.key for i in rig.memory.search(token_budget=25)] == ["nuevo", "medio"]
    assert [i.key for i in rig.memory.search(token_budget=10)] == ["nuevo"]
    assert rig.memory.search(token_budget=9) == []
    assert rig.memory.search(token_budget=0) == []


# --- HU-04-01 AC-01: the memory is independent of the history ---------------------------------


def seed_history(rig: Rig) -> str:
    """A session with events, messages and a summary, written with the real tables."""
    session = rig.store.create_session(model="fake/test").id
    kinds = [EventType.USER_MESSAGE, EventType.ASSISTANT_MESSAGE] * 3
    for number, kind in enumerate(kinds, start=1):
        rig.store.save_event(
            Event(
                id=f"ev-{number}",
                session_id=session,
                type=kind,
                timestamp=T0,
                payload={"n": number},
            )
        )
    connection = rig.store.connection()
    connection.execute(
        "INSERT INTO mensajes (sesion_id, posicion, rol, contenido, creado) "
        "VALUES (?, 1, 'user', 'hola', 't')",
        (session,),
    )
    connection.commit()
    return session


def test_ac01_deleting_a_session_with_all_its_history_leaves_the_memory_untouched(
    rig: Rig,
) -> None:
    rig.memory.remember("estilo", "tabs de 4")
    rig.memory.remember("idioma", "español")
    session = seed_history(rig)
    before = rig.memory_rows()
    raw_before = rig.path.read_bytes()
    assert raw_before and before

    connection = sqlite3.connect(rig.path)
    connection.execute("PRAGMA foreign_keys = ON")
    for table, column in (
        ("mensajes", "sesion_id"),
        ("resumenes", "sesion_id"),
        ("contexto_esencial", "sesion_id"),
        ("criterios", "sesion_id"),
        ("criterios_sello", "sesion_id"),
        ("events", "session_id"),
        ("sessions", "id"),
    ):
        connection.execute(f"DELETE FROM {table} WHERE {column} = ?", (session,))
    connection.commit()
    connection.close()

    assert rig.raw("SELECT COUNT(*) FROM sessions WHERE id = ?", session) == [(0,)]
    assert rig.raw("SELECT COUNT(*) FROM events") == [(0,)]
    assert rig.memory_rows() == before
    assert [i.key for i in rig.memory.recent()] == ["idioma", "estilo"]


def test_ac01_compacting_a_session_leaves_the_memory_untouched(rig: Rig) -> None:
    rig.memory.remember("estilo", "tabs de 4")
    session = rig.store.create_session().id
    for number in range(1, 7):
        kind = EventType.USER_MESSAGE if number % 2 else EventType.ASSISTANT_MESSAGE
        rig.store.save_event(
            Event(
                id=f"ev-{number}",
                session_id=session,
                type=kind,
                timestamp=T0,
                payload={"n": number},
            )
        )
    before = rig.memory_rows()

    receipt = SqliteCompactionArchive(rig.store, clock=lambda: T0).commit_compaction(
        CompactionCommit(session, 1, 4, "Se migró el módulo.", "r1", "ev-r1")
    )

    assert receipt is not None and receipt.eventos > 0
    assert rig.raw("SELECT COUNT(*) FROM resumenes") == [(1,)]
    assert rig.memory_rows() == before


def test_ac01_a_new_session_on_the_same_file_reads_what_was_saved(tmp_path: Path) -> None:
    path = tmp_path / "sessions.db"
    first = SqliteSessionStore(path)
    SqliteMemoryStore(first).remember("estilo", "tabs de 4")
    first.close()

    second = SqliteSessionStore(path)
    try:
        assert [(i.key, i.content) for i in SqliteMemoryStore(second).recent()] == [
            ("estilo", "tabs de 4")
        ]
    finally:
        second.close()
