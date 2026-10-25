"""Tamper detection: fingerprint of the copy, restoration, seal and integrity (HU-11-01 / T006)."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.storage import (
    CriteriaIntegrityError,
    ExportError,
    SqliteSessionStore,
    SqliteTaskStore,
    StartedTask,
)
from harness_agent.core import EventType
from tests.unit.adapters.storage.task_support import (
    NOW,
    SENTINEL,
    TASK,
    RecordingBus,
    open_session_store,
    raw,
    sequential_ids,
)


@pytest.fixture
def session_store(tmp_path: Path) -> Iterator[SqliteSessionStore]:
    store = open_session_store(tmp_path)
    yield store
    store.close()


@pytest.fixture
def bus() -> RecordingBus:
    return RecordingBus()


@pytest.fixture
def tasks(session_store: SqliteSessionStore, tmp_path: Path, bus: RecordingBus) -> SqliteTaskStore:
    return SqliteTaskStore(
        session_store,
        exports_dir=tmp_path / "db" / "tareas",
        bus=bus,
        clock=lambda: NOW,
        id_factory=sequential_ids("e"),
    )


@pytest.fixture
def started(tasks: SqliteTaskStore) -> StartedTask:
    return tasks.start_task(TASK)


def writable(path: Path) -> None:
    path.chmod(0o644)


def test_an_intact_copy_verifies_without_events(
    tasks: SqliteTaskStore, started: StartedTask, bus: RecordingBus
) -> None:
    before = started.export_path.read_bytes()

    assert tasks.verify_export(started.session_id) is True

    assert bus.events == [] and started.export_path.read_bytes() == before


def test_a_modified_copy_is_restored_and_reported(
    tasks: SqliteTaskStore, started: StartedTask, bus: RecordingBus
) -> None:
    original = started.export_path.read_bytes()
    writable(started.export_path)
    started.export_path.write_bytes(original.replace(b'"passes": false', b'"passes": true'))

    assert tasks.verify_export(started.session_id) is False

    assert started.export_path.read_bytes() == original
    assert not os.access(started.export_path, os.W_OK)
    assert bus.motives() == ["copia_modificada"]
    event = bus.events[0]
    assert event.type is EventType.CRITERIA_TAMPERED
    assert (event.id, event.session_id, event.timestamp) == ("e-2", started.session_id, NOW)
    assert event.payload == {"motivo": "copia_modificada"}  # never content or paths
    assert tasks.verify_export(started.session_id) is True and len(bus.events) == 1


def test_a_deleted_copy_is_restored_and_reported(
    tasks: SqliteTaskStore, started: StartedTask, bus: RecordingBus
) -> None:
    original = started.export_path.read_bytes()
    writable(started.export_path)
    started.export_path.unlink()

    assert tasks.verify_export(started.session_id) is False

    assert started.export_path.read_bytes() == original
    assert bus.motives() == ["copia_ausente"]


def test_a_copy_replaced_by_a_folder_is_restored_and_reported(
    tasks: SqliteTaskStore, started: StartedTask, bus: RecordingBus
) -> None:
    original = started.export_path.read_bytes()
    writable(started.export_path)
    started.export_path.unlink()
    started.export_path.mkdir()

    assert tasks.verify_export(started.session_id) is False

    assert started.export_path.is_file() and started.export_path.read_bytes() == original
    assert bus.motives() == ["copia_no_regular"]


def test_a_copy_replaced_by_a_link_is_restored_and_reported(
    tasks: SqliteTaskStore, started: StartedTask, bus: RecordingBus
) -> None:
    original = started.export_path.read_bytes()
    elsewhere = started.export_path.parent / "elsewhere.json"
    elsewhere.write_bytes(original)
    writable(started.export_path)
    started.export_path.unlink()
    try:
        started.export_path.symlink_to(elsewhere)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available")

    assert tasks.verify_export(started.session_id) is False

    assert not started.export_path.is_symlink()
    assert bus.motives() == ["copia_no_regular"]


def test_a_copy_that_cannot_be_restored_fails_closed_but_is_still_reported(
    tasks: SqliteTaskStore, started: StartedTask, bus: RecordingBus
) -> None:
    writable(started.export_path)
    started.export_path.unlink()
    folder = started.export_path.parent
    folder.rmdir()
    folder.write_text("a file where the folder should be")

    with pytest.raises(ExportError):
        tasks.verify_export(started.session_id)

    assert bus.motives() == ["copia_ausente"]


def test_without_a_bus_a_tampered_copy_is_still_restored(
    session_store: SqliteSessionStore, tmp_path: Path
) -> None:
    tasks = SqliteTaskStore(session_store, exports_dir=tmp_path / "db" / "tareas")
    started = tasks.start_task(TASK)
    writable(started.export_path)
    started.export_path.unlink()

    assert tasks.verify_export(started.session_id) is False
    assert started.export_path.is_file()


def tamper_description(store: SqliteSessionStore) -> None:
    raw(store).execute("UPDATE criterios SET descripcion = 'cambiada' WHERE orden = 1")
    raw(store).commit()


def delete_seal(store: SqliteSessionStore) -> None:
    raw(store).execute("DELETE FROM criterios_sello")
    raw(store).commit()


def delete_rows(store: SqliteSessionStore) -> None:
    raw(store).execute("DELETE FROM criterios WHERE orden = 2")
    raw(store).commit()


def force_passes(store: SqliteSessionStore) -> None:
    raw(store).execute("UPDATE criterios SET passes = 1, evidencia = 'inventada'")
    raw(store).commit()


def invalid_rows(store: SqliteSessionStore) -> None:
    """Rows that break the rules of the table, written with the checks switched off."""
    conn = raw(store)
    conn.execute("PRAGMA ignore_check_constraints = ON")
    conn.execute("UPDATE criterios SET tipo = 'otro' WHERE orden = 1")
    conn.commit()
    conn.execute("PRAGMA ignore_check_constraints = OFF")


def break_semantic(store: SqliteSessionStore) -> None:
    conn = raw(store)
    conn.execute("PRAGMA ignore_check_constraints = ON")
    conn.execute("UPDATE criterios SET comando = 'rm -rf' WHERE orden = 2")
    conn.commit()
    conn.execute("PRAGMA ignore_check_constraints = OFF")


def break_objective(store: SqliteSessionStore) -> None:
    conn = raw(store)
    conn.execute("PRAGMA ignore_check_constraints = ON")
    conn.execute("UPDATE criterios SET condicion = NULL WHERE orden = 1")
    conn.commit()
    conn.execute("PRAGMA ignore_check_constraints = OFF")


def break_order(store: SqliteSessionStore) -> None:
    conn = raw(store)
    conn.execute("PRAGMA ignore_check_constraints = ON")
    conn.execute("UPDATE criterios SET orden = 5 WHERE orden = 2")
    conn.commit()
    conn.execute("PRAGMA ignore_check_constraints = OFF")


def break_passes_without_evidence(store: SqliteSessionStore) -> None:
    conn = raw(store)
    conn.execute("PRAGMA ignore_check_constraints = ON")
    conn.execute("UPDATE criterios SET passes = 1, evidencia = NULL WHERE orden = 1")
    conn.commit()
    conn.execute("PRAGMA ignore_check_constraints = OFF")


def break_passes_value(store: SqliteSessionStore) -> None:
    conn = raw(store)
    conn.execute("PRAGMA ignore_check_constraints = ON")
    conn.execute("UPDATE criterios SET passes = 7 WHERE orden = 1")
    conn.commit()
    conn.execute("PRAGMA ignore_check_constraints = OFF")


def blank_description(store: SqliteSessionStore) -> None:
    conn = raw(store)
    conn.execute("PRAGMA ignore_check_constraints = ON")
    conn.execute("UPDATE criterios SET descripcion = '  ' WHERE orden = 1")
    conn.commit()
    conn.execute("PRAGMA ignore_check_constraints = OFF")


def non_text_evidence(store: SqliteSessionStore) -> None:
    conn = raw(store)
    conn.execute("PRAGMA ignore_check_constraints = ON")
    conn.execute("UPDATE criterios SET evidencia = x'00ff' WHERE orden = 1")
    conn.commit()
    conn.execute("PRAGMA ignore_check_constraints = OFF")


TAMPERINGS: list[Callable[[SqliteSessionStore], None]] = [
    tamper_description,
    delete_seal,
    delete_rows,
    force_passes,
    invalid_rows,
    break_semantic,
    break_objective,
    break_order,
    break_passes_without_evidence,
    break_passes_value,
    blank_description,
    non_text_evidence,
]


@pytest.mark.parametrize("tamper", TAMPERINGS, ids=lambda f: f.__name__)
def test_any_sign_of_alteration_in_the_database_fails_closed_everywhere(
    tamper: Callable[[SqliteSessionStore], None],
    tasks: SqliteTaskStore,
    session_store: SqliteSessionStore,
    started: StartedTask,
    bus: RecordingBus,
) -> None:
    item_id = tasks.load_criteria(started.session_id)[0].id
    tamper(session_store)
    operations: list[Callable[[], object]] = [
        lambda: tasks.load_criteria(started.session_id),
        lambda: tasks.get_pending(started.session_id),
        lambda: tasks.verify_export(started.session_id),
        lambda: tasks.mark_passes(item_id, "evidencia"),
        lambda: tasks.export_readonly_copy(started.session_id, started.export_path.parent / "x"),
    ]

    for operation in operations:
        with pytest.raises(CriteriaIntegrityError) as caught:
            operation()
        assert SENTINEL not in str(caught.value)

    assert bus.motives() == ["base_alterada"] * len(operations)
    assert all(e.type is EventType.CRITERIA_TAMPERED for e in bus.events)
    assert not (started.export_path.parent / "x").exists()


def test_a_session_without_a_task_has_no_integrity_problem(
    tasks: SqliteTaskStore, session_store: SqliteSessionStore, bus: RecordingBus
) -> None:
    plain = session_store.create_session(model="m")

    assert tasks.load_criteria(plain.id) == []
    assert bus.events == []
