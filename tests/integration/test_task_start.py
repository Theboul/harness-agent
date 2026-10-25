"""Integration (HU-11-01 / AC-01): a task from a file or an issue becomes a session with criteria.

Real ``compose`` (loop, policy, registry, SQLite on a temporary folder); the provider is a double
and ``gh`` is a function: no network, key or console.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.tasks import load_github_issue, load_task_file
from harness_agent.bootstrap import Composition
from tests.unit.bootstrap_support import build, make_config

TASK_TEXT = (
    "# TAREA-14\n"
    "## Objetivo\nValidar el correo\n"
    "## Criterios de aceptación\n"
    "- El email es obligatorio\n  - comando: pytest tests/test_email.py\n  - espera: salida 0\n"
    "- El mensaje de error es claro\n"
)


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def start(opened: list[Composition], tmp_path: Path, task_source: str) -> Composition:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    path = tmp_path / "tarea.md"
    path.write_text(task_source, encoding="utf-8", newline="")
    task = load_task_file(path)
    return build(opened, make_config(tmp_path, workspace=workspace), task=task)


def test_a_task_file_starts_a_session_with_pending_criteria_and_a_readonly_copy(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = start(opened, tmp_path, TASK_TEXT)

    assert composition.task_store is not None
    pending = composition.task_store.get_pending(composition.session_id)
    assert [item.description for item in pending] == [
        "El email es obligatorio",
        "El mensaje de error es claro",
    ]
    stored = composition.store.get_session(composition.session_id)
    assert stored is not None and stored.goal == "Validar el correo"
    export = composition.criteria_export
    assert export is not None
    data = json.loads(export.read_text(encoding="utf-8"))
    assert len(data) == 2 and not os.access(export, os.W_OK)


def test_the_copy_follows_the_database_when_a_criterion_passes(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = start(opened, tmp_path, TASK_TEXT)
    assert composition.task_store is not None
    first = composition.task_store.get_pending(composition.session_id)[0]

    composition.task_store.mark_passes(first.id, "pytest salió con 0")

    assert [i.description for i in composition.task_store.get_pending(composition.session_id)] == [
        "El mensaje de error es claro"
    ]
    assert composition.task_store.verify_export(composition.session_id) is True


def test_an_issue_read_with_gh_starts_the_same_kind_of_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    body = TASK_TEXT.split("\n", 1)[1]
    answer = json.dumps({"title": "Validar el correo", "body": body})
    task = load_github_issue(14, runner=lambda _args: answer)
    workspace = tmp_path / "trabajo"
    workspace.mkdir()

    composition = build(opened, make_config(tmp_path, workspace=workspace), task=task)

    assert composition.task is not None and composition.task.title == "Validar el correo"
    assert composition.task_store is not None
    assert len(composition.task_store.load_criteria(composition.session_id)) == 2
