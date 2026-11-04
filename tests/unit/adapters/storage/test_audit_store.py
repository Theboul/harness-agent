"""SqliteAuditStore on a real file (HU-05-05).

The audit has its own table and no foreign key; the rows come back in order with the parent of
their session, a decision is completed when its question is answered, and a failure of the engine
rises as a fixed ``SessionStoreError`` (the audit fails closed: nothing here swallows it).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from harness_agent.adapters.storage import SessionStoreError, SqliteAuditStore, SqliteSessionStore
from harness_agent.core import AuditEntry, AuditLog, AuditRow

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"


def entry(session: str = "s1", call: str = "c1", **overrides: object) -> AuditEntry:
    values: dict[str, object] = {
        "session_id": session,
        "call_id": call,
        "tool": "escribir_archivo",
        "arguments": '{"path": "a.txt"}',
        "decision": "ask",
        "resolution": "pendiente",
        "reason": None,
        "origin": "agente",
        "decided_at": T0,
    }
    return AuditEntry(**{**values, **overrides})  # type: ignore[arg-type]


class Rig:
    def __init__(self, path: Path) -> None:
        self.store = SqliteSessionStore(path)
        self.audit = SqliteAuditStore(self.store)

    def session(self, parent: str | None = None) -> str:
        return self.store.create_session(model="fake/test", parent_id=parent).id

    def raw(self, sql: str, *parameters: object) -> list[tuple[object, ...]]:
        connection = self.store.connection()
        found = connection.execute(sql, parameters).fetchall()
        connection.commit()
        return [tuple(row) for row in found]


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    made = Rig(tmp_path / "sessions.db")
    try:
        yield made
    finally:
        made.store.close()


def test_the_store_is_an_audit_log(rig: Rig) -> None:
    log: AuditLog = rig.audit

    assert log.count("nada") == 0


def test_a_decision_comes_back_as_it_was_written(rig: Rig) -> None:
    session = rig.session()
    rig.audit.record_decision(entry(session, reason="policy_error"))

    assert rig.audit.rows(session, 10) == [
        AuditRow(
            session_id=session,
            parent_id=None,
            call_id="c1",
            tool="escribir_archivo",
            arguments='{"path": "a.txt"}',
            decision="ask",
            resolution="pendiente",
            reason="policy_error",
            action=None,
            source=None,
            origin="agente",
            decided_at=T0,
            resolved_at=None,
        )
    ]


def test_the_instants_are_stored_in_utc_and_a_naive_one_is_taken_as_utc(rig: Rig) -> None:
    session = rig.session()
    local = datetime(2026, 11, 4, 9, 0, tzinfo=timezone(timedelta(hours=-3)))
    rig.audit.record_decision(entry(session, "a", decided_at=local))
    rig.audit.record_decision(entry(session, "b", decided_at=datetime(2026, 11, 4, 12, 0)))

    stored = rig.raw("SELECT decidida FROM auditoria ORDER BY id")
    assert stored == [("2026-11-04T12:00:00+00:00",), ("2026-11-04T12:00:00+00:00",)]


def test_a_resolution_completes_the_latest_row_of_that_session_and_call(rig: Rig) -> None:
    session, other = rig.session(), rig.session()
    rig.audit.record_decision(entry(session, "verificacion-1"))
    rig.audit.record_decision(entry(session, "verificacion-1", arguments='{"command": "dos"}'))
    rig.audit.record_decision(entry(other, "verificacion-1"))

    rig.audit.record_resolution(
        session, "verificacion-1", "aprobada", "approve_once", "user", T0 + timedelta(seconds=5)
    )

    rows = rig.audit.rows(session, 10)
    assert [row.resolution for row in rows] == ["pendiente", "aprobada"]
    assert (rows[1].action, rows[1].source) == ("approve_once", "user")
    assert rows[1].resolved_at == T0 + timedelta(seconds=5)
    assert rig.audit.rows(other, 10)[0].resolution == "pendiente"


def test_a_resolution_without_a_row_changes_nothing_and_does_not_fail(rig: Rig) -> None:
    session = rig.session()
    rig.audit.record_decision(entry(session))

    rig.audit.record_resolution(session, "otra", "aprobada", None, None, T0)

    assert rig.audit.rows(session, 10)[0].resolution == "pendiente"


def test_the_rows_are_the_latest_ones_oldest_first_and_the_count_has_no_limit(rig: Rig) -> None:
    session = rig.session()
    for index in range(5):
        rig.audit.record_decision(entry(session, f"c{index}"))

    assert [row.call_id for row in rig.audit.rows(session, 3)] == ["c2", "c3", "c4"]
    assert rig.audit.count(session) == 5
    assert rig.audit.rows(session, 0) == [] and rig.audit.rows(session, -4) == []


def test_the_rows_include_the_direct_children_with_their_parent_and_nothing_else(rig: Rig) -> None:
    parent = rig.session()
    child = rig.session(parent)
    grandchild = rig.session(child)
    stranger = rig.session()
    rig.audit.record_decision(entry(parent, "p"))
    rig.audit.record_decision(entry(child, "h"))
    rig.audit.record_decision(entry(grandchild, "n"))
    rig.audit.record_decision(entry(stranger, "x"))

    rows = rig.audit.rows(parent, 10)

    assert [(row.call_id, row.parent_id) for row in rows] == [("p", None), ("h", parent)]
    assert rig.audit.count(parent) == 2
    assert [row.call_id for row in rig.audit.rows(child, 10)] == ["h", "n"]


def test_rows_of_a_session_that_is_not_in_the_sessions_table_are_still_found(rig: Rig) -> None:
    rig.audit.record_decision(entry("fantasma", "c1"))

    rows = rig.audit.rows("fantasma", 10)

    assert [(row.call_id, row.parent_id) for row in rows] == [("c1", None)]


def test_a_failure_of_the_engine_is_a_fixed_error_that_names_nothing(rig: Rig) -> None:
    rig.raw("DROP TABLE auditoria")

    for call in (
        lambda: rig.audit.record_decision(entry(SENTINEL)),
        lambda: rig.audit.record_resolution(SENTINEL, "c", "aprobada", None, None, T0),
        lambda: rig.audit.rows(SENTINEL, 5),
        lambda: rig.audit.count(SENTINEL),
    ):
        with pytest.raises(SessionStoreError) as raised:
            call()
        message = str(raised.value)
        assert message == "Error del almacén de la auditoría."
        assert SENTINEL not in message and "auditoria" not in message


def test_a_row_with_an_unreadable_instant_is_a_fixed_error(rig: Rig) -> None:
    session = rig.session()
    rig.audit.record_decision(entry(session))
    rig.raw("UPDATE auditoria SET decidida = 'no es una hora'")

    with pytest.raises(SessionStoreError) as raised:
        rig.audit.rows(session, 5)

    assert str(raised.value) == "Un registro de la auditoría está dañado y no se puede leer."


def test_a_closed_store_is_a_store_error(rig: Rig) -> None:
    rig.store.close()

    with pytest.raises(SessionStoreError):
        rig.audit.record_decision(entry())
    with pytest.raises(SessionStoreError):
        rig.audit.rows("s1", 5)


def test_a_write_that_the_engine_refuses_leaves_no_partial_row(rig: Rig) -> None:
    session = rig.session()
    rig.raw("CREATE TRIGGER refuse BEFORE INSERT ON auditoria BEGIN SELECT RAISE(ABORT, 'no'); END")

    with pytest.raises(SessionStoreError):
        rig.audit.record_decision(entry(session))

    assert rig.audit.count(session) == 0
    assert sqlite3.sqlite_version  # the engine is real: the refusal above came from a trigger
