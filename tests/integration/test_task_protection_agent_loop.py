"""Integration (HU-11-01 / AC-02, AC-03): the agent cannot reach the criteria; tampering is undone.

Real ``compose`` with the real loop, policy and registry. The provider asks for tool calls on the
harness folder; the answers and the published events are what the story promises.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent.bootstrap import Composition
from harness_agent.core import Event, EventType, ProviderResponse, Role, ToolCall
from tests.doubles import FakeProvider
from tests.unit.adapters.storage.task_support import TASK
from tests.unit.bootstrap_support import build, make_config, one_turn


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def provider_for(name: str, arguments: dict[str, Any]) -> FakeProvider:
    return FakeProvider(
        [
            ProviderResponse(tool_calls=[ToolCall(id="c1", name=name, arguments=arguments)]),
            ProviderResponse(content="listo"),
        ]
    )


def start(
    opened: list[Composition], tmp_path: Path, provider: FakeProvider | None = None
) -> Composition:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    return build(opened, make_config(tmp_path, workspace=workspace), provider, task=TASK)


def collect(composition: Composition, event_type: EventType) -> list[Event]:
    events: list[Event] = []
    composition.bus.subscribe(event_type, events.append)
    return events


@pytest.mark.parametrize(
    "name",
    ["leer_archivo", "escribir_archivo", "listar_archivos", "buscar_texto"],
)
async def test_every_file_tool_is_denied_on_the_harness_folder_with_its_event(
    tmp_path: Path, opened: list[Composition], name: str
) -> None:
    folder = str(tmp_path / "datos")
    arguments = {
        "leer_archivo": {"path": str(tmp_path / "datos" / "sesiones.db")},
        "escribir_archivo": {"path": str(tmp_path / "datos" / "sesiones.db"), "content": "x"},
        "listar_archivos": {"path": folder},
        "buscar_texto": {"path": folder, "query": "x"},
    }[name]
    composition = start(opened, tmp_path, provider_for(name, arguments))
    decisions = collect(composition, EventType.PERMISSION_DECIDED)
    before = (tmp_path / "datos" / "sesiones.db").stat().st_size

    result = await one_turn(composition)

    tool_messages = [m for m in result.history if m.role is Role.TOOL]
    assert tool_messages[0].content.startswith("[permission_denied]")
    assert [e.payload["decision"] for e in decisions] == ["deny"]
    assert (tmp_path / "datos" / "sesiones.db").stat().st_size == before


async def test_a_shell_command_naming_the_database_is_denied_and_launches_nothing(
    tmp_path: Path, opened: list[Composition]
) -> None:
    marker = tmp_path / "trabajo" / "lanzado.txt"
    command = f"echo x > {marker.name} && type datos/sesiones.db"
    composition = start(opened, tmp_path, provider_for("shell", {"command": command}))
    decisions = collect(composition, EventType.PERMISSION_DECIDED)

    result = await one_turn(composition)

    assert [m for m in result.history if m.role is Role.TOOL][0].content.startswith(
        "[permission_denied]"
    )
    assert [e.payload["decision"] for e in decisions] == ["deny"]
    assert not marker.exists()


async def test_a_modified_copy_is_restored_and_the_attempt_is_recorded(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = start(opened, tmp_path)
    assert composition.task_store is not None and composition.criteria_export is not None
    export = composition.criteria_export
    original = export.read_bytes()
    tampered = collect(composition, EventType.CRITERIA_TAMPERED)
    export.chmod(stat.S_IREAD | stat.S_IWRITE)
    export.write_bytes(original.replace(b"false", b"true"))

    intact = composition.task_store.verify_export(composition.session_id)

    assert intact is False
    assert export.read_bytes() == original and not os.access(export, os.W_OK)
    assert [e.payload for e in tampered] == [{"motivo": "copia_modificada"}]
    assert b"El email" not in str(tampered[0].payload).encode()
    assert composition.task_store.verify_export(composition.session_id) is True


async def test_a_deleted_copy_is_recreated_and_recorded(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = start(opened, tmp_path)
    assert composition.task_store is not None and composition.criteria_export is not None
    export = composition.criteria_export
    original = export.read_bytes()
    tampered = collect(composition, EventType.CRITERIA_TAMPERED)
    export.chmod(stat.S_IREAD | stat.S_IWRITE)
    export.unlink()

    assert composition.task_store.verify_export(composition.session_id) is False

    assert export.read_bytes() == original
    assert [e.payload for e in tampered] == [{"motivo": "copia_ausente"}]
