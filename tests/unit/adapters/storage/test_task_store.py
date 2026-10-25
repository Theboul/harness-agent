"""SqliteTaskStore: starting a task, reading criteria, marking them (HU-11-01 / T005)."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.storage import (
    CriteriaNotFound,
    ExportError,
    SessionStoreError,
    SqliteSessionStore,
    SqliteTaskStore,
    StartedTask,
)
from harness_agent.adapters.storage.criteria_export import (
    canonical_export,
    fingerprint,
    write_readonly,
)
from harness_agent.core import CriterionDefinition, TaskCriteria, TaskDefinition
from tests.unit.adapters.storage.task_support import (
    NOW,
    SENTINEL,
    TASK,
    RecordingBus,
    open_session_store,
    raw,
    sequential_ids,
)

WRITE_READONLY = "harness_agent.adapters.storage.task_store.write_readonly"


@pytest.fixture
def session_store(tmp_path: Path) -> Iterator[SqliteSessionStore]:
    store = open_session_store(tmp_path)
    yield store
    store.close()


@pytest.fixture
def exports(tmp_path: Path) -> Path:
    return tmp_path / "db" / "tareas"


@pytest.fixture
def tasks(session_store: SqliteSessionStore, exports: Path) -> SqliteTaskStore:
    return SqliteTaskStore(
        session_store, exports_dir=exports, bus=RecordingBus(), clock=lambda: NOW
    )


def count(store: SqliteSessionStore, table: str) -> int:
    return int(raw(store).execute(f"SELECT count(*) FROM {table}").fetchone()[0])


def test_it_implements_the_port(tasks: SqliteTaskStore) -> None:
    assert isinstance(tasks, TaskCriteria)


def test_start_task_creates_the_session_the_rows_the_seal_and_the_copy(
    tasks: SqliteTaskStore, session_store: SqliteSessionStore, exports: Path
) -> None:
    started = tasks.start_task(TASK, model="fake/test")

    assert isinstance(started, StartedTask)
    session = session_store.get_session(started.session_id)
    assert session is not None
    assert (session.status, session.goal, session.model) == ("active", TASK.objective, "fake/test")
    rows = (
        raw(session_store)
        .execute(
            "SELECT orden, descripcion, tipo, comando, condicion, passes, evidencia, "
            "confirmado_por FROM criterios WHERE sesion_id = ? ORDER BY orden",
            (started.session_id,),
        )
        .fetchall()
    )
    assert rows == [
        (
            1,
            "El email es obligatorio",
            "objetivo",
            "pytest tests/test_email.py",
            "salida 0",
            0,
            None,
            None,
        ),
        (2, "El mensaje de error es claro", "semantico", None, None, 0, None, None),
    ]
    assert started.export_path == exports / started.session_id / "criterios.json"
    data = started.export_path.read_bytes()
    assert not os.access(started.export_path, os.W_OK)
    seal = (
        raw(session_store)
        .execute("SELECT huella FROM criterios_sello WHERE sesion_id = ?", (started.session_id,))
        .fetchone()
    )
    assert seal == (fingerprint(data),)
    assert tasks.export_path(started.session_id) == started.export_path


def test_each_task_gets_its_own_session_and_criteria(tasks: SqliteTaskStore) -> None:
    first = tasks.start_task(TASK)
    second = tasks.start_task(TASK)

    assert first.session_id != second.session_id
    assert len(tasks.load_criteria(first.session_id)) == 2
    assert {i.id for i in tasks.load_criteria(first.session_id)}.isdisjoint(
        {i.id for i in tasks.load_criteria(second.session_id)}
    )


def test_load_criteria_returns_port_items_in_order(tasks: SqliteTaskStore) -> None:
    started = tasks.start_task(TASK)

    items = tasks.load_criteria(started.session_id)

    assert [i.description for i in items] == [
        "El email es obligatorio",
        "El mensaje de error es claro",
    ]
    assert [i.command for i in items] == ["pytest tests/test_email.py", None]
    assert all(isinstance(i.id, str) and i.id.isdigit() for i in items)
    assert all(i.passes is False and i.evidence is None for i in items)


def test_unknown_session_has_no_criteria(tasks: SqliteTaskStore) -> None:
    assert tasks.load_criteria("nope") == []
    assert tasks.get_pending("nope") == []


def test_mark_passes_changes_only_that_criterion_and_refreshes_the_copy(
    tasks: SqliteTaskStore,
) -> None:
    started = tasks.start_task(TASK)
    first, second = tasks.load_criteria(started.session_id)

    tasks.mark_passes(first.id, "pytest salió con 0")

    after_first, after_second = tasks.load_criteria(started.session_id)
    assert (after_first.passes, after_first.evidence) == (True, "pytest salió con 0")
    assert (after_second.passes, after_second.evidence) == (False, None)
    assert after_first.description == first.description and after_second.id == second.id
    assert [i.id for i in tasks.get_pending(started.session_id)] == [second.id]
    assert tasks.verify_export(started.session_id) is True  # the copy follows the database
    assert b"pytest sali" in started.export_path.read_bytes()


@pytest.mark.parametrize("bad", ["", "abc", "-1", "1.5", "0", "999999", "9" * 40, " 1", "1 "])
def test_mark_passes_with_an_invalid_or_unknown_id_is_rejected(
    tasks: SqliteTaskStore, bad: str
) -> None:
    started = tasks.start_task(TASK)
    before = started.export_path.read_bytes()

    with pytest.raises(CriteriaNotFound):
        tasks.mark_passes(bad, "evidencia")

    assert started.export_path.read_bytes() == before


@pytest.mark.parametrize("evidence", ["", "   ", "\n"])
def test_mark_passes_requires_evidence(tasks: SqliteTaskStore, evidence: str) -> None:
    started = tasks.start_task(TASK)
    item = tasks.load_criteria(started.session_id)[0]

    with pytest.raises(ValueError):
        tasks.mark_passes(item.id, evidence)

    assert tasks.load_criteria(started.session_id)[0].passes is False


def test_a_failing_copy_leaves_no_trace_of_the_task(
    tasks: SqliteTaskStore,
    session_store: SqliteSessionStore,
    exports: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_destination: Path, _data: bytes) -> None:
        raise ExportError("sin detalle")

    monkeypatch.setattr(WRITE_READONLY, broken)

    with pytest.raises(ExportError):
        tasks.start_task(TASK)

    assert (count(session_store, "sessions"), count(session_store, "criterios")) == (0, 0)
    assert count(session_store, "criterios_sello") == 0
    assert not exports.exists() or not any(exports.rglob("*.json"))


class FailingCommit:
    """Connection proxy whose commit fails, as a full disk would."""

    def __init__(self, inner: sqlite3.Connection) -> None:
        self._inner = inner

    def commit(self) -> None:
        raise sqlite3.OperationalError("disk full")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class FakeSessionStore(SqliteSessionStore):
    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.fail_commit = True

    def connection(self) -> sqlite3.Connection:
        real = super().connection()
        return FailingCommit(real) if self.fail_commit else real  # type: ignore[return-value]


def test_a_failing_commit_removes_the_copy_and_leaves_nothing(tmp_path: Path) -> None:
    store = FakeSessionStore(tmp_path / "db" / "sessions.db")
    exports = tmp_path / "db" / "tareas"
    tasks = SqliteTaskStore(store, exports_dir=exports)
    try:
        with pytest.raises(SessionStoreError):
            tasks.start_task(TASK)
        store.fail_commit = False
        assert count(store, "sessions") == 0 and count(store, "criterios") == 0
        assert not any(exports.rglob("*.json"))
    finally:
        store.close()


def test_a_failing_commit_keeps_the_previous_copy_of_a_mark_untouched(tmp_path: Path) -> None:
    store = FakeSessionStore(tmp_path / "db" / "sessions.db")
    store.fail_commit = False
    tasks = SqliteTaskStore(store, exports_dir=tmp_path / "db" / "tareas")
    try:
        started = tasks.start_task(TASK)
        item = tasks.load_criteria(started.session_id)[0]
        store.fail_commit = True
        with pytest.raises(SessionStoreError):
            tasks.mark_passes(item.id, "evidencia")
        store.fail_commit = False
        assert tasks.load_criteria(started.session_id)[0].passes is False
    finally:
        store.close()


def test_an_unsafe_session_identifier_is_refused_before_anything_is_created(
    session_store: SqliteSessionStore, exports: Path
) -> None:
    tasks = SqliteTaskStore(session_store, exports_dir=exports, id_factory=lambda: "../evil")

    with pytest.raises(SessionStoreError):
        tasks.start_task(TASK)

    assert count(session_store, "sessions") == 0


def test_export_path_rejects_unsafe_identifiers(tasks: SqliteTaskStore) -> None:
    for bad in ["", "..", "a/b", "a\\b", "x" * 80]:
        with pytest.raises(CriteriaNotFound):
            tasks.export_path(bad)
        with pytest.raises(CriteriaNotFound):
            tasks.verify_export(bad)


def test_export_readonly_copy_writes_the_canonical_json_where_asked(
    tasks: SqliteTaskStore, tmp_path: Path
) -> None:
    started = tasks.start_task(TASK)
    destination = tmp_path / "otra" / "copia.json"

    tasks.export_readonly_copy(started.session_id, destination)

    assert destination.read_bytes() == started.export_path.read_bytes()
    assert not os.access(destination, os.W_OK)


def test_a_closed_store_fails_with_a_store_error(
    tasks: SqliteTaskStore, session_store: SqliteSessionStore
) -> None:
    started = tasks.start_task(TASK)
    session_store.close()

    for call in (
        lambda: tasks.start_task(TASK),
        lambda: tasks.load_criteria(started.session_id),
        lambda: tasks.mark_passes("1", "e"),
        lambda: tasks.verify_export(started.session_id),
    ):
        with pytest.raises(SessionStoreError):
            call()


def test_engine_errors_are_translated_without_details(
    tasks: SqliteTaskStore, session_store: SqliteSessionStore
) -> None:
    started = tasks.start_task(TASK)
    raw(session_store).execute("DROP TABLE criterios_sello")

    with pytest.raises(SessionStoreError) as caught:
        tasks.load_criteria(started.session_id)

    assert "criterios_sello" not in str(caught.value) and SENTINEL not in str(caught.value)


def test_start_task_uses_injected_identifiers_and_clock(
    session_store: SqliteSessionStore, exports: Path
) -> None:
    tasks = SqliteTaskStore(
        session_store, exports_dir=exports, clock=lambda: NOW, id_factory=sequential_ids("s")
    )

    started = tasks.start_task(TASK)

    assert started.session_id == "s-1"
    session = session_store.get_session("s-1")
    assert session is not None and session.created_at == NOW


def test_a_task_with_only_semantic_criteria_is_stored(tasks: SqliteTaskStore) -> None:
    task = TaskDefinition(None, "o", "", "", (CriterionDefinition("a"), CriterionDefinition("b")))

    started = tasks.start_task(task)

    assert [i.command for i in tasks.load_criteria(started.session_id)] == [None, None]
    assert canonical_export([]) != started.export_path.read_bytes()


def test_a_missing_criteria_table_is_a_store_error(
    tasks: SqliteTaskStore, session_store: SqliteSessionStore
) -> None:
    started = tasks.start_task(TASK)
    raw(session_store).execute("DROP TABLE criterios")

    with pytest.raises(SessionStoreError):
        tasks.load_criteria(started.session_id)


def test_a_failed_mark_still_fails_cleanly_when_the_copy_cannot_be_put_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FakeSessionStore(tmp_path / "db" / "sessions.db")
    store.fail_commit = False
    tasks = SqliteTaskStore(store, exports_dir=tmp_path / "db" / "tareas")
    try:
        started = tasks.start_task(TASK)
        item = tasks.load_criteria(started.session_id)[0]
        store.fail_commit = True
        calls: list[int] = []

        def second_write_fails(destination: Path, data: bytes) -> None:
            calls.append(1)
            if len(calls) > 1:
                raise ExportError("sin detalle")
            write_readonly(destination, data)

        monkeypatch.setattr(WRITE_READONLY, second_write_fails)

        with pytest.raises(SessionStoreError):
            tasks.mark_passes(item.id, "evidencia")

        assert len(calls) == 2
    finally:
        store.close()
