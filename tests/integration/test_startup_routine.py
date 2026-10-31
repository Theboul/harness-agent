"""Integration (HU-11-08.2): the startup routine of a resumed ticket through the real system.

Real ``compose`` and ``run_session`` (policy chain, registry, native shell, SQLite on a temporary
folder, the CLI); the provider is a double and the streams are in memory: no network, no key, no
console. The commands are valid in bash and in PowerShell. Git runs only in a repository made here
with an isolated environment.
"""

from __future__ import annotations

import asyncio
import io
import platform
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.system import interpreter_for
from harness_agent.bootstrap import Composition, run_session
from harness_agent.core import ProviderResponse, Role, TaskDefinition, parse_task
from tests.doubles import FakeProvider
from tests.integration.test_git_real_repository import git_environment, run_git
from tests.unit.bootstrap_support import FIXED_TIME, build, make_config

EXECUTABLES = {"powershell": ("pwsh", "powershell"), "bash": ("bash",)}
INTERPRETER = interpreter_for(platform.system())

pytestmark = pytest.mark.skipif(
    not any(shutil.which(name) for name in EXECUTABLES[INTERPRETER]) or shutil.which("git") is None,
    reason="hace falta el intérprete de la plataforma y git",
)

PASSING = 'python -c "import sys; sys.exit(0)"'
FAILING = "python -c \"import sys; print('prueba-roja-777'); sys.exit(3)\""
SENTINEL = "VALOR-DE-PRUEBA-123"
NAME = "progreso-TAREA-14.md"
PREVIOUS = "# Progreso del ticket: TAREA-14\n- Hecho: validación del correo\n"


def task_text(tests: str | None) -> str:
    commands = "" if tests is None else f"\n## Comandos\n- pruebas: {tests}\n  - tiempo: 60\n"
    return (
        "# TAREA-14: Validar el correo\n\n## Objetivo\nValidar el correo\n\n"
        "## Criterios de aceptación\n- El mensaje de error es claro\n" + commands
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


def definition(text: str) -> TaskDefinition:
    return parse_task(text)


def start(
    opened: list[Composition],
    tmp_path: Path,
    area: Path,
    tests: str | None,
    provider: FakeProvider,
) -> Composition:
    environ = git_environment(tmp_path)
    path_key = next((key for key in environ if key.upper() == "PATH"), "PATH")
    environ[path_key] = str(Path(sys.executable).parent) + ";" + environ.get(path_key, "")
    if INTERPRETER == "bash":
        environ[path_key] = environ[path_key].replace(";", ":")
    return build(
        opened,
        make_config(tmp_path, workspace=area),
        provider,
        task=definition(task_text(tests)),
        clock=lambda: FIXED_TIME,
        environ=environ,
    )


def answers(*texts: str) -> FakeProvider:
    return FakeProvider([ProviderResponse(content=text) for text in texts])


async def session(composition: Composition, text: str) -> str:
    output = io.StringIO()
    async with asyncio.timeout(60):
        await run_session(composition, input_stream=io.StringIO(text), output=output)
    return output.getvalue()


def first_request(provider: FakeProvider, index: int = 0) -> str:
    users = [m for m in provider.received[index] if m.role is Role.USER and not m.is_external]
    return users[-1].content


def make_repository(area: Path, tmp_path: Path) -> None:
    env = git_environment(tmp_path)
    run_git(area, env, "init", "-q")
    (area / "a.txt").write_text("a", encoding="utf-8")
    run_git(area, env, "add", "a.txt")
    run_git(area, env, "commit", "-q", "-m", "feat: primer-cambio-de-prueba")


class TestAC01TheAgentReceivesProgressLogAndTest:
    async def test_progress_log_and_result_precede_the_first_request(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        make_repository(area, tmp_path)
        (area / NAME).write_text(PREVIOUS, encoding="utf-8")
        provider = answers("uno", "dos")
        composition = start(opened, tmp_path, area, PASSING, provider)
        output = await session(composition, "mi pedido\notro pedido\n")

        text = first_request(provider)
        assert "| - Hecho: validación del correo" in text
        assert "primer-cambio-de-prueba" in text
        assert "La prueba básica pasó" in text
        assert text.endswith("Petición de la persona:\nmi pedido")
        assert "Rutina de arranque: progreso leído; prueba básica: pasó." in output

    async def test_it_is_delivered_once(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        (area / NAME).write_text(PREVIOUS, encoding="utf-8")
        provider = answers("uno", "dos")
        await session(start(opened, tmp_path, area, PASSING, provider), "mi pedido\notro pedido\n")
        assert first_request(provider, 1) == "otro pedido"

    async def test_a_command_waits_for_the_first_real_request(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        (area / NAME).write_text(PREVIOUS, encoding="utf-8")
        provider = answers("uno")
        await session(start(opened, tmp_path, area, PASSING, provider), "/ayuda\nmi pedido\n")
        assert "[rutina de arranque]" in first_request(provider)

    async def test_the_old_file_is_read_before_the_new_checkpoint_replaces_it(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        (area / NAME).write_text(PREVIOUS, encoding="utf-8")
        provider = answers("uno")
        await session(start(opened, tmp_path, area, PASSING, provider), "mi pedido\n")
        assert "validación del correo" in first_request(provider)
        assert "validación del correo" not in (area / NAME).read_text(encoding="utf-8")


class TestAC02RepairBeforeAdvancing:
    async def test_a_failing_test_asks_to_repair_and_shows_its_output(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        (area / NAME).write_text(PREVIOUS, encoding="utf-8")
        provider = answers("uno")
        composition = start(opened, tmp_path, area, FAILING, provider)
        output = await session(composition, "mi pedido\n")

        text = first_request(provider)
        assert "FALLÓ (código de salida 3)" in text
        assert "Repara eso antes de avanzar" in text
        assert "prueba-roja-777" in text
        assert "prueba básica: falló." in output
        assert FAILING not in text


class TestNoRoutine:
    async def test_a_new_ticket_has_no_routine(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        provider = answers("uno")
        output = await session(start(opened, tmp_path, area, PASSING, provider), "mi pedido\n")
        assert first_request(provider) == "mi pedido"
        assert "Rutina de arranque" not in output

    async def test_a_task_without_a_basic_test_is_reported_as_not_checked(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        (area / NAME).write_text(PREVIOUS, encoding="utf-8")
        provider = answers("uno")
        await session(start(opened, tmp_path, area, None, provider), "mi pedido\n")
        text = first_request(provider)
        assert "no se pudo comprobar" in text and "Comprueba tú mismo" in text

    async def test_outside_a_repository_the_log_is_unavailable(
        self, tmp_path: Path, area: Path, opened: list[Composition]
    ) -> None:
        (area / NAME).write_text(PREVIOUS, encoding="utf-8")
        provider = answers("uno")
        await session(start(opened, tmp_path, area, PASSING, provider), "mi pedido\n")
        assert "(log de git no disponible)" in first_request(provider)
