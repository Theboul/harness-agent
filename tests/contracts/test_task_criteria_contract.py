"""Contract of the ``TaskCriteria`` port, run against the real SQLite implementation (HU-11-01).

There is no test double of this port; the battery states what the port promises so any later
implementation can be added to ``IMPLEMENTATIONS``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.storage import SqliteSessionStore, SqliteTaskStore
from harness_agent.core import TaskCriteria, TaskCriteriaItem
from tests.unit.adapters.storage.task_support import TASK

Factory = Callable[[Path], tuple[TaskCriteria, str]]


def sqlite_factory(tmp_path: Path) -> tuple[TaskCriteria, str]:
    store = SqliteSessionStore(tmp_path / "sessions.db")
    tasks = SqliteTaskStore(store, exports_dir=tmp_path / "tareas")
    return tasks, tasks.start_task(TASK).session_id


IMPLEMENTATIONS = [pytest.param(sqlite_factory, id="sqlite")]


@pytest.fixture(params=IMPLEMENTATIONS)
def port(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[tuple[TaskCriteria, str]]:
    yield request.param(tmp_path)


def test_load_criteria_returns_the_items_of_the_session(port: tuple[TaskCriteria, str]) -> None:
    criteria, session_id = port
    items = criteria.load_criteria(session_id)
    assert len(items) == 2 and all(isinstance(i, TaskCriteriaItem) for i in items)
    assert all(i.passes is False for i in items)
    assert criteria.load_criteria("unknown") == []


def test_get_pending_shrinks_as_criteria_pass(port: tuple[TaskCriteria, str]) -> None:
    criteria, session_id = port
    first, second = criteria.load_criteria(session_id)
    assert criteria.get_pending(session_id) == [first, second]

    criteria.mark_passes(first.id, "evidencia")

    assert [i.id for i in criteria.get_pending(session_id)] == [second.id]
    assert criteria.load_criteria(session_id)[0].evidence == "evidencia"


def test_export_readonly_copy_is_json_with_the_criteria(
    port: tuple[TaskCriteria, str], tmp_path: Path
) -> None:
    criteria, session_id = port
    destination = tmp_path / "out" / "copy.json"

    criteria.export_readonly_copy(session_id, destination)

    data = json.loads(destination.read_text(encoding="utf-8"))
    assert [entry["descripcion"] for entry in data] == [
        "El email es obligatorio",
        "El mensaje de error es claro",
    ]
    assert all(entry["passes"] is False for entry in data)
