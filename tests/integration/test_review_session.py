"""Integration (HU-11-05): the review of the diff in a real ticket session.

Real ``compose`` and ``run_session`` (loop, policy chain, verifier, SQLite on a temporary folder,
the console reviewer); the provider is a double, the streams are in memory and git is a recording
double of the ``ChangeSource`` port (the real git has its own test): no network, key or console.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.tasks import load_task_file
from harness_agent.bootstrap import Composition, run_session
from harness_agent.cli import ConsoleReviewer
from harness_agent.core import (
    ChangeSet,
    ChangeSourceError,
    ChangeStatus,
    FileChange,
    ProviderResponse,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import FIXED_TIME, build, make_config

TASK_TEXT = (
    "# TAREA-14\n"
    "## Objetivo\nValidar el correo\n"
    "## Criterios de aceptación\n"
    "- El mensaje de error es claro\n"
)
OBJECTIVE_TASK = (
    "# TAREA-15\n"
    "## Objetivo\nValidar la clave\n"
    "## Criterios de aceptación\n"
    "- La clave mide 8\n"
    "  - comando: exit 0\n"
    "  - espera: codigo_salida == 0\n"
)
CHANGES = ChangeSet((FileChange("auth.py", ChangeStatus.NEW, 5, 0),), "+def validar(): ...\n")


class Source:
    def __init__(self, changes: ChangeSet = CHANGES, *, fail: bool = False) -> None:
        self.changes = changes
        self.fail = fail
        self.commits: list[str] = []

    async def snapshot(self) -> ChangeSet:
        if self.fail:
            raise ChangeSourceError("No se pudo leer el cambio del repositorio.")
        return self.changes

    async def commit(self, message: str) -> str:
        self.commits.append(message)
        return "abc1234"


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


async def session(composition: Composition, lines: io.StringIO, output: io.StringIO) -> str:
    # One stream feeds both the review prompt and the CLI, as in ``main()``.
    async with asyncio.timeout(10):
        await run_session(composition, input_stream=lines, output=output)
    return output.getvalue()


def rig(
    opened: list[Composition],
    tmp_path: Path,
    source: Source,
    typed: str,
    *answers: str,
    text: str = TASK_TEXT,
    reviewer: bool = True,
) -> tuple[Composition, FakeProvider, io.StringIO, io.StringIO]:
    stream = io.StringIO(typed)
    output = io.StringIO()
    area = tmp_path / "trabajo"
    area.mkdir(exist_ok=True)
    task_file = tmp_path / "tarea.md"
    task_file.write_text(text, encoding="utf-8", newline="")
    provider = FakeProvider([ProviderResponse(content=a) for a in answers])
    composition = build(
        opened,
        make_config(tmp_path, workspace=area),
        provider,
        task=load_task_file(task_file),
        clock=lambda: FIXED_TIME,
        changes=source,
        reviewer=ConsoleReviewer(stream, output) if reviewer else None,
    )
    return composition, provider, stream, output


async def test_the_person_confirms_the_semantic_criterion_and_approves(
    tmp_path: Path, opened: list[Composition]
) -> None:
    source = Source()
    composition, provider, stream, output = rig(
        opened, tmp_path, source, "haz\n4\n1\n/salir\n", "hecho"
    )

    shown = await session(composition, stream, output)

    assert source.commits == ["TAREA-14: Validar el correo"]
    assert "REVISIÓN DE CAMBIOS: TAREA-14" in shown and "+def validar" in shown
    assert "Commit hecho: abc1234" in shown
    assert all(item.passes for item in composition.task_store.load_criteria(composition.session_id))  # type: ignore[union-attr]


async def test_approving_without_confirming_the_criterion_commits_nothing(
    tmp_path: Path, opened: list[Composition]
) -> None:
    source = Source()
    composition, provider, stream, output = rig(
        opened, tmp_path, source, "haz\n1\n/salir\n/salir\n", "hecho"
    )

    shown = await session(composition, stream, output)

    assert source.commits == []
    assert "Hay criterios semánticos sin confirmar" in shown or "No se puede aprobar" in shown


async def test_rejecting_with_a_reason_sends_it_back_to_the_agent(
    tmp_path: Path, opened: list[Composition]
) -> None:
    source = Source()
    typed = "haz\n3\nfalta el caso vacío\n/salir\n"
    composition, provider, stream, output = rig(
        opened, tmp_path, source, typed, "hecho", "corregido"
    )

    await session(composition, stream, output)

    assert source.commits == [] and provider.call_count == 2
    last = provider.received[1][-1]
    assert last.content.startswith("[review_rejected]")
    assert "Reason: 'falta el caso vacío'" in last.content


async def test_a_session_without_reviewer_behaves_as_before(
    tmp_path: Path, opened: list[Composition]
) -> None:
    source = Source()
    composition, _, stream, output = rig(
        opened, tmp_path, source, "haz\n/salir\n", "hecho", reviewer=False
    )

    shown = await session(composition, stream, output)

    assert source.commits == [] and "REVISIÓN" not in shown


async def test_an_unreadable_repository_is_reported_and_nothing_is_committed(
    tmp_path: Path, opened: list[Composition]
) -> None:
    source = Source(fail=True)
    composition, provider, stream, output = rig(opened, tmp_path, source, "haz\n/salir\n", "hecho")

    shown = await session(composition, stream, output)

    assert "No se pudo leer el cambio del repositorio." in shown and source.commits == []


async def test_a_task_with_an_unmet_objective_criterion_opens_no_review(
    tmp_path: Path, opened: list[Composition]
) -> None:
    source = Source()
    composition, _, stream, output = rig(
        opened, tmp_path, source, "haz\n/salir\n", "hecho", text=OBJECTIVE_TASK
    )

    shown = await session(composition, stream, output)

    assert "REVISIÓN" not in shown and source.commits == []
