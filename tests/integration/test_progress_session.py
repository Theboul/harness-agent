"""Integration (HU-11-08.1): the progress file written while a ticket session runs.

Real ``compose`` and ``run_session`` (loop, policy, SQLite on a temporary folder, the CLI); the
provider is a double and the streams are in memory: no network, key or console.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.tasks import load_task_file
from harness_agent.bootstrap import Composition, run_session
from harness_agent.core import ProviderResponse
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import FIXED_TIME, build, make_config

SENTINEL = "VALOR-DE-PRUEBA-123"
NAME = "progreso-TAREA-14.md"
TASK_TEXT = (
    "# TAREA-14\n"
    "## Objetivo\nValidar el correo\n"
    "## Criterios de aceptación\n"
    "- El mensaje de error es claro\n"
    "- La clave mide 8\n"
)


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


@pytest.fixture
def area(tmp_path: Path) -> Path:
    folder = tmp_path / "trabajo"
    folder.mkdir()
    return folder


def start(
    opened: list[Composition], tmp_path: Path, area: Path | None, *answers: str, task: bool = True
) -> Composition:
    definition = None
    if task:
        source = tmp_path / "tarea.md"
        source.write_text(TASK_TEXT, encoding="utf-8", newline="")
        definition = load_task_file(source)
    provider = FakeProvider([ProviderResponse(content=text) for text in answers])
    return build(
        opened,
        make_config(tmp_path, workspace=area),
        provider,
        task=definition,
        clock=lambda: FIXED_TIME,
    )


async def session(composition: Composition, text: str) -> tuple[int, str]:
    output = io.StringIO()
    async with asyncio.timeout(10):
        code = await run_session(composition, input_stream=io.StringIO(text), output=output)
    return code, output.getvalue()


class TestACheckpointPerTurn:
    async def test_the_file_is_complete_after_each_turn_and_final_on_exit(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        composition = start(opened, tmp_path, area, "primera respuesta", "segunda respuesta")
        code, _ = await session(composition, "uno\ndos\n/salir\n")

        assert code == 0
        text = (area / NAME).read_text(encoding="utf-8")
        assert text.startswith("# Progreso del ticket: TAREA-14\n")
        assert "- Estado: final de la sesión tras 2 turnos\n" in text
        assert "- Criterio 1: El mensaje de error es claro (pendiente de validación humana)" in text
        assert "- Criterio 2: La clave mide 8 (pendiente de validación humana)" in text
        assert text.endswith("## Nota\nsegunda respuesta\n")

    async def test_a_checkpoint_exists_before_the_session_ends(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        composition = start(opened, tmp_path, area, "primera respuesta")

        class Cut(io.StringIO):
            """Gives one line, then looks at the file and ends the process the hard way."""

            def readline(self, size: int | None = -1) -> str:  # type: ignore[override]
                if self.tell() == 0:
                    return super().readline(-1 if size is None else size)
                text = (area / NAME).read_text(encoding="utf-8")
                assert "- Estado: punto de control tras el turno 1\n" in text
                assert text.endswith("## Nota\nprimera respuesta\n")
                raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            await run_session(composition, input_stream=Cut("uno\n"), output=io.StringIO())

        # No final write after a hard stop: the last checkpoint is what remains.
        text = (area / NAME).read_text(encoding="utf-8")
        assert "punto de control tras el turno 1" in text
        assert "final de la sesión" not in text

    async def test_exit_with_no_turn_creates_the_file(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        composition = start(opened, tmp_path, area, "no se usa")
        await session(composition, "/salir\n")
        assert "final de la sesión tras 0 turnos" in (area / NAME).read_text(encoding="utf-8")

    async def test_the_end_of_the_input_is_also_a_normal_end(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        composition = start(opened, tmp_path, area, "respuesta")
        await session(composition, "uno\n")
        assert "final de la sesión tras 1 turno\n" in (area / NAME).read_text(encoding="utf-8")


class TestWhenThereIsNothingToWrite:
    async def test_a_session_without_a_task_writes_no_progress(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        composition = start(opened, tmp_path, area, "respuesta", task=False)
        assert composition.progress is None
        await session(composition, "uno\n/salir\n")
        assert list(area.iterdir()) == []

    async def test_a_task_without_a_work_folder_writes_no_progress(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = start(opened, tmp_path, None, "respuesta")
        assert composition.progress is None
        code, _ = await session(composition, "uno\n/salir\n")
        assert code == 0


class TestAFailureNeverBreaksTheSession:
    async def test_an_unwritable_destination_is_one_warning_per_write_and_exit_zero(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        (area / NAME).mkdir()  # a folder where the file should go
        composition = start(opened, tmp_path, area, "respuesta")
        code, shown = await session(composition, "uno\n/salir\n")

        assert code == 0
        warning = (
            "No se pudo escribir el archivo de progreso; se conserva el último punto de control."
        )
        assert shown.count(warning) == 2  # the checkpoint and the final write
        assert SENTINEL not in shown and (area / NAME).is_dir()


class TestWhatTheFileNeverHolds:
    async def test_commands_and_evidence_are_not_in_the_file(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        source = tmp_path / "tarea.md"
        source.write_text(
            "# TAREA-14\n## Objetivo\nHacer\n## Criterios de aceptación\n"
            f"- Se cumple\n  - comando: echo {SENTINEL}\n  - espera: codigo_salida == 0\n",
            encoding="utf-8",
            newline="",
        )
        provider = FakeProvider([ProviderResponse(content="listo")] * 3)
        composition = build(
            opened,
            make_config(tmp_path, workspace=area),
            provider,
            task=load_task_file(source),
            clock=lambda: FIXED_TIME,
        )
        await session(composition, "uno\n/salir\n")
        text = (area / NAME).read_text(encoding="utf-8")
        assert SENTINEL not in text and "echo " not in text


class TestATamperedCriteriaSource:
    async def test_nothing_is_written_and_the_session_still_ends(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        composition = start(opened, tmp_path, area, "respuesta")
        connection = composition.store.connection()
        connection.execute("UPDATE criterios_sello SET huella = 'otra'")
        connection.commit()

        code, shown = await session(composition, "/salir\n")

        assert code == 0
        warning = (
            "No se pudo escribir el archivo de progreso; se conserva el último punto de control."
        )
        assert shown.count(warning) == 1
        assert not (area / NAME).exists()
