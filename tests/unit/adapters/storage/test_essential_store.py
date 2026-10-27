"""SqliteEssentialStore on a real file (HU-02-06.1 / T006, contracts/essential_store.md E1 to E3).

The elements are written once, when the session of the task is created, and read afterwards.
Failures are real SQLite errors raised by triggers, so the rollback is the engine's.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harness_agent.adapters.storage import (
    SessionStoreError,
    SqliteEssentialStore,
    SqliteSessionStore,
)
from harness_agent.core import (
    EssentialItem,
    TaskCriteriaItem,
    criteria_reference,
    instruction_messages,
    make_items,
    render_block,
)

T0 = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"
INSTRUCTIONS = [
    ("entorno", "Entorno: Linux y bash.  "),
    ("git", "Reglas de git.\nSin empujar."),
    ("comandos", "Comandos de la tarea."),
]


class Rig:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.store = SqliteSessionStore(path)
        self.session = self.store.create_session().id
        self.essential = SqliteEssentialStore(self.store, clock=lambda: T0)

    def items(self, session: str | None = None) -> tuple[EssentialItem, ...]:
        made = make_items(
            ticket="TAREA-14: Validar el correo",
            objective="Rechazar correos sin dominio en el formulario de alta.",
            rules="No tocar el esquema de la base.\nMantener la API pública.",
            instructions=INSTRUCTIONS,
        )
        return (*made, criteria_reference(session or self.session))

    def raw(self, sql: str, *parameters: object) -> list[tuple[object, ...]]:
        connection = sqlite3.connect(self.path)
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def snapshot(self, *tables: str) -> dict[str, list[tuple[object, ...]]]:
        return {name: self.raw(f"SELECT * FROM {name} ORDER BY 1") for name in tables}


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    opened = Rig(tmp_path / "sessions.db")
    yield opened
    opened.store.close()


# --- E1: save and read ----------------------------------------------------------------------------


def test_e1_seven_rows_are_saved_and_read_back_in_order(rig: Rig) -> None:
    rig.essential.save_items(rig.session, rig.items())

    found = rig.essential.items(rig.session)

    assert len(found) == 7
    assert [(i.key, i.order) for i in found] == [
        ("criterios_ref", 1),
        ("instrucciones", 1),
        ("instrucciones", 2),
        ("instrucciones", 3),
        ("objetivo", 1),
        ("reglas", 1),
        ("ticket", 1),
    ]
    assert sorted(found, key=lambda i: (i.key, i.order)) == sorted(
        rig.items(), key=lambda i: (i.key, i.order)
    )
    rows = rig.raw("SELECT DISTINCT creado FROM contexto_esencial")
    assert rows == [(T0.isoformat(),)]


def test_the_reference_is_stored_and_the_texts_of_the_instructions_are_exact(rig: Rig) -> None:
    rig.essential.save_items(rig.session, rig.items())

    rows = rig.raw("SELECT clave || orden, valor FROM contexto_esencial")
    values = {str(key): str(value) for key, value in rows}

    assert values["criterios_ref1"] == rig.session
    assert values["instrucciones1"] == "Entorno: Linux y bash.  "
    assert values["instrucciones2"] == "Reglas de git.\nSin empujar."


def test_a_session_without_rows_gives_an_empty_list(rig: Rig) -> None:
    other = rig.store.create_session().id

    assert rig.essential.items(other) == []
    assert rig.essential.items("no-existe") == []


def test_the_rows_of_another_session_are_not_mixed_up(rig: Rig) -> None:
    other = rig.store.create_session().id
    rig.essential.save_items(rig.session, rig.items())
    rig.essential.save_items(other, rig.items(other))

    assert {i.value for i in rig.essential.items(other) if i.key == "criterios_ref"} == {other}
    assert len(rig.essential.items(rig.session)) == len(rig.essential.items(other)) == 7


# --- write once -----------------------------------------------------------------------------------


def test_the_elements_are_written_once(rig: Rig) -> None:
    rig.essential.save_items(rig.session, rig.items())
    before = rig.snapshot("contexto_esencial")

    with pytest.raises(SessionStoreError):
        rig.essential.save_items(rig.session, rig.items())
    with pytest.raises(SessionStoreError):
        rig.essential.save_items(rig.session, (criteria_reference(rig.session),))

    assert rig.snapshot("contexto_esencial") == before and not rig.store.connection().in_transaction


def test_an_unknown_session_is_refused(rig: Rig) -> None:
    with pytest.raises(SessionStoreError):
        rig.essential.save_items("no-existe", rig.items("no-existe"))

    assert rig.raw("SELECT count(*) FROM contexto_esencial") == [(0,)]


# --- E2: rollback ---------------------------------------------------------------------------------


def test_e2_a_failure_in_the_middle_leaves_no_row(rig: Rig) -> None:
    rig.store.connection().execute(
        "CREATE TRIGGER boom BEFORE INSERT ON contexto_esencial "
        "WHEN NEW.clave = 'instrucciones' AND NEW.orden = 2 "
        "BEGIN SELECT RAISE(ABORT, 'inyectado'); END"
    )
    rig.store.connection().commit()

    with pytest.raises(SessionStoreError) as raised:
        rig.essential.save_items(rig.session, rig.items())

    assert rig.raw("SELECT count(*) FROM contexto_esencial") == [(0,)]
    assert not rig.store.connection().in_transaction
    assert "inyectado" not in str(raised.value) and rig.session not in str(raised.value)


def test_after_a_rollback_the_same_save_works(rig: Rig) -> None:
    connection = rig.store.connection()
    connection.execute(
        "CREATE TRIGGER boom BEFORE INSERT ON contexto_esencial BEGIN SELECT RAISE(ABORT, 'x'); END"
    )
    connection.commit()
    with pytest.raises(SessionStoreError):
        rig.essential.save_items(rig.session, rig.items())
    connection.execute("DROP TRIGGER boom")
    connection.commit()

    rig.essential.save_items(rig.session, rig.items())

    assert rig.raw("SELECT count(*) FROM contexto_esencial") == [(7,)]


def test_the_error_never_carries_a_value(rig: Rig) -> None:
    rig.store.connection().execute(
        "CREATE TRIGGER boom BEFORE INSERT ON contexto_esencial BEGIN SELECT RAISE(ABORT, 'x'); END"
    )
    rig.store.connection().commit()
    secret = make_items(
        ticket=None, objective="Objetivo " + SENTINEL, rules=None, instructions=[("entorno", "x")]
    )

    with pytest.raises(SessionStoreError) as raised:
        rig.essential.save_items(rig.session, secret)

    assert SENTINEL not in str(raised.value) + repr(raised.value.args)
    assert raised.value.__cause__ is None


# --- what it does not touch -----------------------------------------------------------------------


def test_it_touches_no_other_table(rig: Rig) -> None:
    tables = ("sessions", "events", "resumenes", "criterios", "criterios_sello")
    before = rig.snapshot(*tables)

    rig.essential.save_items(rig.session, rig.items())
    rig.essential.items(rig.session)

    assert rig.snapshot(*tables) == before


def test_a_closed_store_fails_with_the_store_error(rig: Rig) -> None:
    rig.store.close()

    with pytest.raises(SessionStoreError):
        rig.essential.items(rig.session)
    with pytest.raises(SessionStoreError):
        rig.essential.save_items(rig.session, rig.items())


def test_an_engine_error_while_reading_is_a_store_error(rig: Rig) -> None:
    rig.store.connection().execute("ALTER TABLE contexto_esencial RENAME TO movida")

    with pytest.raises(SessionStoreError) as raised:
        rig.essential.items(rig.session)

    assert raised.value.__cause__ is None


def test_a_row_with_a_key_this_version_does_not_know_is_a_store_error(rig: Rig) -> None:
    rig.store.connection().execute(
        "INSERT INTO contexto_esencial (sesion_id, clave, orden, valor, origen, creado) "
        "VALUES (?, 'desconocida', 1, 'valor', 'origen', 't')",
        (rig.session,),
    )
    rig.store.connection().commit()

    with pytest.raises(SessionStoreError):
        rig.essential.items(rig.session)


# --- R17: the connection of the store -------------------------------------------------------------


def test_r17_it_never_opens_a_connection_of_its_own(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: object, **kwargs: object) -> sqlite3.Connection:
        raise AssertionError("the adapter must use the connection of the store")

    monkeypatch.setattr(sqlite3, "connect", forbidden)

    rig.essential.save_items(rig.session, rig.items())

    assert len(rig.essential.items(rig.session)) == 7


def test_r17_saving_events_around_the_elements_works_on_the_same_database(rig: Rig) -> None:
    from harness_agent.core import Event, EventType

    rig.store.save_event(Event("a", rig.session, EventType.USER_MESSAGE, T0, {}))
    rig.essential.save_items(rig.session, rig.items())
    rig.store.save_event(Event("b", rig.session, EventType.ASSISTANT_MESSAGE, T0, {}))

    reader = sqlite3.connect(rig.path)
    try:
        assert reader.execute("SELECT count(*) FROM contexto_esencial").fetchone() == (7,)
        assert reader.execute("SELECT count(*) FROM events").fetchone() == (2,)
    finally:
        reader.close()
    assert not rig.store.connection().in_transaction


def test_a_naive_time_from_the_clock_is_taken_as_utc(tmp_path: Path) -> None:
    store = SqliteSessionStore(tmp_path / "naive.db")
    try:
        session = store.create_session().id
        essential = SqliteEssentialStore(store, clock=lambda: datetime(2026, 10, 27, 12, 0))
        essential.save_items(session, (criteria_reference(session),))
        found = store.connection().execute("SELECT creado FROM contexto_esencial").fetchone()
        assert found == (T0.isoformat(),)
    finally:
        store.close()


def test_the_default_clock_is_utc_now(tmp_path: Path) -> None:
    store = SqliteSessionStore(tmp_path / "default.db")
    try:
        session = store.create_session().id
        SqliteEssentialStore(store).save_items(session, (criteria_reference(session),))
        (stamp,) = store.connection().execute("SELECT creado FROM contexto_esencial").fetchone()
        moment = datetime.fromisoformat(stamp)
        assert abs((datetime.now(timezone.utc) - moment).total_seconds()) < 60
    finally:
        store.close()


# --- FR-015: rebuild from the store ---------------------------------------------------------------


def test_the_prefix_and_the_block_are_rebuilt_from_the_store_alone(rig: Rig) -> None:
    prefix = [text for _, text in INSTRUCTIONS]
    originals = rig.items()
    criteria = [TaskCriteriaItem("1", "El validador rechaza a@"), TaskCriteriaItem("2", "Pasan")]
    sent = render_block(originals, criteria)

    rig.essential.save_items(rig.session, originals)
    stored = rig.essential.items(rig.session)

    assert [m.content for m in instruction_messages(stored)] == prefix
    assert render_block(stored, criteria) == sent


def test_an_interrupt_during_the_save_rolls_back_and_goes_through(rig: Rig) -> None:
    class Interrupting:
        @property
        def key(self) -> str:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        rig.essential.save_items(rig.session, [Interrupting()])  # type: ignore[list-item]

    assert not rig.store.connection().in_transaction
    assert rig.raw("SELECT count(*) FROM contexto_esencial") == [(0,)]
