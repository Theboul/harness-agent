"""Tests and lint of a sample project through the real loop and the native shell (HU-11-03 / T005).

Sp2-48. ``compose(task=...)`` builds the whole system (policy chain, registry with the output
limit, real ``shell``) with no approver, so a command runs only if the task allows it exactly.
The sample project lives in ``tmp_path``; its commands (``python -m pytest``, ``python -m ruff``)
are valid in bash and in PowerShell, so the same tests run on Linux and on Windows. The provider
is a ``FakeProvider``: no network, no keys.

* AC-01: a failing test reaches the agent with an exit code other than 0 and its failure message.
* AC-02: a very long output reaches the context cut, with the omission notice.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import interpreter_for
from harness_agent.bootstrap import Composition
from harness_agent.core import (
    Event,
    EventType,
    Message,
    ProviderResponse,
    Role,
    TaskDefinition,
    ToolCall,
    parse_task,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import SENTINEL, build, make_config

SYSTEM = platform.system()
EXECUTABLES = {"powershell": ("pwsh", "powershell"), "bash": ("bash",)}
INTERPRETER = interpreter_for(SYSTEM)

pytestmark = pytest.mark.skipif(
    not any(shutil.which(name) for name in EXECUTABLES[INTERPRETER]),
    reason=f"el intérprete de la plataforma ({INTERPRETER}) no está instalado",
)

TESTS = "python -m pytest -q -p no:cacheprovider test_ejemplo.py"
LONG_TESTS = "python -m pytest -q -p no:cacheprovider test_largo.py"
LINT = "python -m ruff check --no-cache modulo.py"
FAILURE_MESSAGE = "el-total-no-coincide"

EXAMPLE = f"""\
def suma(a, b):
    return a - b


def test_resta_que_pasa():
    assert suma(2, 2) == 0


def test_suma_falla():
    assert suma(2, 3) == 5, "{FAILURE_MESSAGE}"
"""
FIXED = EXAMPLE.replace("return a - b", "return a + b").replace("== 0", "== 4")
LONG = """\
def test_salida_larga():
    print("inicio-de-la-salida")
    print("x" * 300_000)
    print("fin-de-la-salida")
    assert False, "la-salida-larga-falla"
"""
MODULE = "import os\n\n\nVALOR = 1\n"


def task_text(tests: str) -> str:
    return f"""# TAREA-25: Corregir la suma

## Objetivo
La función suma debe sumar.

## Criterios de aceptación
- Las pruebas pasan
  - comando: {tests}
  - espera: codigo_salida == 0

## Comandos
- pruebas: {tests}
  - tiempo: 300
- lint: {LINT}
"""


def child_environment() -> dict[str, str]:
    """The environment of the commands: the interpreter of the tests first on the path, without
    the variables that would make the child pytest write coverage data into the repository, and
    without bytecode files (a fix of the same size written in the same second must be seen)."""
    kept = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COV_CORE", "COVERAGE", "PYTEST_"))
    }
    path_key = next((key for key in kept if key.upper() == "PATH"), "PATH")
    kept[path_key] = os.pathsep.join([str(Path(sys.executable).parent), kept.get(path_key, "")])
    kept["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    kept["PYTHONDONTWRITEBYTECODE"] = "1"
    return kept


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    folder = tmp_path / "proyecto"
    folder.mkdir()
    (folder / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (folder / "test_ejemplo.py").write_text(EXAMPLE, encoding="utf-8")
    (folder / "test_largo.py").write_text(LONG, encoding="utf-8")
    (folder / "modulo.py").write_text(MODULE, encoding="utf-8")
    return folder


def calls(*arguments: dict[str, Any]) -> FakeProvider:
    script: list[ProviderResponse] = []
    for index, args in enumerate(arguments):
        script.append(
            ProviderResponse(tool_calls=[ToolCall(id=f"c{index}", name="shell", arguments=args)])
        )
        script.append(ProviderResponse(content="visto"))
    return FakeProvider(script)


class Run:
    """One composed system over the sample project, with the events it publishes."""

    def __init__(
        self,
        tmp_path: Path,
        opened: list[Composition],
        project: Path,
        task: TaskDefinition,
        provider: FakeProvider,
    ) -> None:
        config = make_config(tmp_path, workspace=project)
        self.composition = build(opened, config, provider, task=task, environ=child_environment())
        self.events: list[Event] = []
        for event_type in EventType:
            self.composition.bus.subscribe(event_type, self.events.append)
        self.history: list[Message] = list(self.composition.history_prefix)
        self.limit = config.limits.max_tool_output_chars

    async def turn(self) -> str:
        result = await self.composition.loop.run_turn(
            session_id=self.composition.session_id, task="revisa", history=self.history
        )
        self.history[:] = list(result.history)
        return str([m for m in result.history if m.role is Role.TOOL][-1].content)


# --- AC-01: a failing test is reported to the agent ----------------------------------------------


async def test_a_failing_test_reaches_the_agent_with_its_code_and_message(
    tmp_path: Path, opened: list[Composition], project: Path
) -> None:
    run = Run(
        tmp_path,
        opened,
        project,
        parse_task(task_text(TESTS)),
        calls({"command": TESTS, "timeout_seconds": 300}),
    )

    answer = await run.turn()

    assert answer.startswith("[codigo_de_salida=")
    assert not answer.startswith("[codigo_de_salida=0]")
    assert "test_suma_falla" in answer
    assert FAILURE_MESSAGE in answer
    assert "1 failed, 1 passed" in answer


async def test_after_the_fix_the_same_command_reports_success(
    tmp_path: Path, opened: list[Composition], project: Path
) -> None:
    run = Run(
        tmp_path,
        opened,
        project,
        parse_task(task_text(TESTS)),
        calls({"command": TESTS, "timeout_seconds": 300}, {"command": TESTS}),
    )

    first = await run.turn()
    (project / "test_ejemplo.py").write_text(FIXED, encoding="utf-8")
    second = await run.turn()

    assert first.startswith("[codigo_de_salida=")
    assert second.startswith("Código de salida: 0")
    assert "2 passed" in second


# --- AC-02: a long output is cut with the omission notice --------------------------------------


async def test_a_very_long_output_reaches_the_context_cut(
    tmp_path: Path, opened: list[Composition], project: Path
) -> None:
    run = Run(
        tmp_path,
        opened,
        project,
        parse_task(task_text(LONG_TESTS)),
        calls({"command": LONG_TESTS, "timeout_seconds": 300}),
    )

    answer = await run.turn()

    assert len(answer) <= run.limit
    assert "[salida recortada: se omitieron" in answer
    assert answer.startswith("[codigo_de_salida=")
    assert "1 failed" in answer  # the final summary of pytest is kept
    assert "test_salida_larga" in answer
    assert "x" * 300_000 not in answer


# --- the lint command -----------------------------------------------------------------------


async def test_the_lint_command_runs_without_asking_and_reports_the_problem(
    tmp_path: Path, opened: list[Composition], project: Path
) -> None:
    run = Run(tmp_path, opened, project, parse_task(task_text(TESTS)), calls({"command": LINT}))

    answer = await run.turn()

    assert answer.startswith("[codigo_de_salida=1]")
    assert "F401" in answer


# --- a variation does not run -----------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        f"{TESTS}; echo {SENTINEL} > marcador.txt",
        f"{TESTS} && echo {SENTINEL} > marcador.txt",
        f"echo {SENTINEL} > marcador.txt; {TESTS}",
    ],
)
async def test_a_variation_of_the_command_is_denied_and_nothing_runs(
    tmp_path: Path, opened: list[Composition], project: Path, command: str
) -> None:
    run = Run(
        tmp_path,
        opened,
        project,
        parse_task(task_text(TESTS)),
        calls({"command": command, "timeout_seconds": 300}),
    )

    answer = await run.turn()

    assert answer.startswith("[approval_required_unavailable]")
    assert not (project / "marcador.txt").exists()
    assert all(SENTINEL not in repr(event.payload) for event in run.events)


async def test_the_events_never_carry_the_command(
    tmp_path: Path, opened: list[Composition], project: Path
) -> None:
    run = Run(
        tmp_path,
        opened,
        project,
        parse_task(task_text(TESTS)),
        calls({"command": TESTS, "timeout_seconds": 300}),
    )

    await run.turn()

    assert run.events
    assert all(TESTS not in repr(event.payload) for event in run.events)
    assert all(FAILURE_MESSAGE not in repr(event.payload) for event in run.events)


def test_the_model_is_told_the_exact_commands(
    tmp_path: Path, opened: list[Composition], project: Path
) -> None:
    run = Run(tmp_path, opened, project, parse_task(task_text(TESTS)), calls({"command": TESTS}))

    (_, notice) = run.composition.history_prefix
    assert f"`{TESTS}` (tiempo máximo: 300 s)" in notice.content
    assert f"`{LINT}` (tiempo máximo: 300 s)" in notice.content
