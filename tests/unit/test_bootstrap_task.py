"""Composition root (HU-11-01 / T010): task start and protection of the harness folder.

``compose(..., task=)`` starts the task (its session is the run's session) and wraps the policy so
the agent tools never reach the sessions database or the criteria copies.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.storage import ExportError
from harness_agent.bootstrap import Composition, compose
from harness_agent.core import ProviderResponse, Role, ToolCall
from tests.doubles import FakeProvider
from tests.unit.adapters.storage.task_support import TASK
from tests.unit.bootstrap_support import build, make_config, one_turn, scripted


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def call_once(name: str, arguments: dict[str, Any]) -> FakeProvider:
    return FakeProvider(
        [
            ProviderResponse(tool_calls=[ToolCall(id="c1", name=name, arguments=arguments)]),
            ProviderResponse(content="listo"),
        ]
    )


async def tool_answer(composition: Composition) -> str:
    result = await one_turn(composition)
    return str([m for m in result.history if m.role is Role.TOOL][0].content)


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    return workspace


# --- without a task nothing changes ---------------------------------------------------------


def test_without_a_task_the_run_starts_a_plain_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = build(opened, make_config(tmp_path, workspace=make_workspace(tmp_path)))

    assert composition.task is None and composition.criteria_export is None
    assert composition.task_store is not None
    assert composition.task_store.load_criteria(composition.session_id) == []
    assert composition.store.get_session(composition.session_id) is not None
    assert not (tmp_path / "datos" / "tareas").exists()


# --- with a task ----------------------------------------------------------------------------


def test_with_a_task_its_session_is_the_session_of_the_run(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = make_config(tmp_path, workspace=make_workspace(tmp_path))

    composition = build(opened, config, task=TASK)

    assert composition.task is TASK
    stored = composition.store.get_session(composition.session_id)
    assert stored is not None and stored.goal == TASK.objective
    assert stored.model == config.model
    assert composition.task_store is not None
    assert len(composition.task_store.load_criteria(composition.session_id)) == 2
    export = composition.criteria_export
    assert export is not None and export.is_file()
    assert export == composition.task_store.export_path(composition.session_id)
    assert export.is_relative_to(tmp_path / "datos" / "tareas")
    assert not os.access(export, os.W_OK)


def test_a_failure_while_starting_the_task_leaves_nothing_open(tmp_path: Path) -> None:
    config = make_config(tmp_path, workspace=make_workspace(tmp_path))
    (tmp_path / "datos").mkdir()
    (tmp_path / "datos" / "tareas").write_text("estorbo", encoding="utf-8", newline="")

    with pytest.raises(ExportError):
        compose(config, provider_factory=lambda _config: scripted("listo"), task=TASK)

    # The database file is free again: the store was closed before the error left compose.
    (tmp_path / "datos" / "sesiones.db").unlink()


# --- protection -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("leer_archivo", {"path": "{db}"}),
        ("escribir_archivo", {"path": "{db}", "content": "x"}),
        ("listar_archivos", {"path": "{dir}"}),
        ("buscar_texto", {"path": "{dir}", "query": "x"}),
        ("leer_archivo", {"path": "{export}"}),
    ],
    ids=["leer-db", "escribir-db", "listar-carpeta", "buscar-carpeta", "leer-copia"],
)
async def test_the_file_tools_cannot_reach_the_harness_folder(
    tmp_path: Path,
    opened: list[Composition],
    name: str,
    arguments: dict[str, Any],
) -> None:
    config = make_config(tmp_path, workspace=make_workspace(tmp_path))
    harness_dir = tmp_path / "datos"
    values = {
        "db": str(harness_dir / "sesiones.db"),
        "dir": str(harness_dir),
        "export": str(harness_dir / "tareas" / "x" / "criterios.json"),
    }
    filled = {k: v.format(**values) if isinstance(v, str) else v for k, v in arguments.items()}
    composition = build(opened, config, call_once(name, filled), task=TASK)

    answer = await tool_answer(composition)

    assert answer.startswith("[permission_denied]")


async def test_the_shell_is_denied_when_the_command_names_a_protected_file(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = make_config(tmp_path, workspace=make_workspace(tmp_path))
    provider = call_once("shell", {"command": "type datos\\SESIONES.DB"})
    composition = build(opened, config, provider, task=TASK)

    assert (await tool_answer(composition)).startswith("[permission_denied]")


async def test_the_shell_with_another_command_still_goes_through_the_normal_policy(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = make_config(tmp_path, workspace=make_workspace(tmp_path))
    composition = build(opened, config, call_once("shell", {"command": "echo hola"}), task=TASK)

    assert (await tool_answer(composition)).startswith("[approval_required_unavailable]")


async def test_a_file_of_the_workspace_is_still_readable(
    tmp_path: Path, opened: list[Composition]
) -> None:
    workspace = make_workspace(tmp_path)
    (workspace / "notas.txt").write_text("hola", encoding="utf-8", newline="")
    composition = build(
        opened,
        make_config(tmp_path, workspace=workspace),
        call_once("leer_archivo", {"path": "notas.txt"}),
    )

    assert "hola" in await tool_answer(composition)


async def test_without_a_workspace_the_database_is_still_denied_not_asked(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = make_config(tmp_path, workspace=None)
    provider = call_once("leer_archivo", {"path": str(tmp_path / "datos" / "sesiones.db")})
    composition = build(opened, config, provider)

    assert (await tool_answer(composition)).startswith("[permission_denied]")


async def test_a_workspace_inside_the_harness_folder_stays_usable_but_the_data_is_not(
    tmp_path: Path, opened: list[Composition]
) -> None:
    workspace = tmp_path / "datos" / "proyecto"
    workspace.mkdir(parents=True)
    (workspace / "notas.txt").write_text("hola", encoding="utf-8", newline="")
    config = make_config(tmp_path, workspace=workspace)

    readable = build(opened, config, call_once("leer_archivo", {"path": "notas.txt"}), task=TASK)
    assert "hola" in await tool_answer(readable)
    readable.close()

    database = str(tmp_path / "datos" / "sesiones.db")
    denied = build(opened, config, call_once("leer_archivo", {"path": database}))
    assert (await tool_answer(denied)).startswith("[permission_denied]")
    denied.close()

    export = build(opened, config, call_once("listar_archivos", {"path": "../tareas"}))
    assert (await tool_answer(export)).startswith("[permission_denied]")


async def test_a_workspace_that_is_the_harness_folder_keeps_only_the_data_protected(
    tmp_path: Path, opened: list[Composition]
) -> None:
    workspace = tmp_path / "datos"
    workspace.mkdir()
    (workspace / "notas.txt").write_text("hola", encoding="utf-8", newline="")
    config = make_config(tmp_path, workspace=workspace)

    composition = build(opened, config, call_once("leer_archivo", {"path": "notas.txt"}))

    assert "hola" in await tool_answer(composition)
