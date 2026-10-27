"""shell_outcome: the real ShellTool, read as a CommandOutcome (HU-11-04.1).

The labels of ``ShellTool`` are text. These tests run the real tool with a scripted ``Shell`` and
pin every label the verification reads, so a change in the tool breaks here and not silently in
the verification.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.tools import ShellTool, make_command_runner, outcome_from_result
from harness_agent.core import (
    CommandOutcome,
    CommandRunner,
    InMemoryToolRegistry,
    ShellResult,
    ToolCall,
    ToolResult,
)
from tests.doubles import DummyTool
from tests.unit.adapters.tools.test_shell_tool import FakeArea, ScriptedShell

SENTINEL = "VALOR-DE-PRUEBA-123"
CREDENTIAL = (
    "https://" + "usuario-de-prueba" + ":" + "secreto-de-prueba" + "@servidor.example/r.git"
)


def call(command: str = "ls", **extra: Any) -> ToolCall:
    return ToolCall(id="verificacion-1", name="shell", arguments={"command": command, **extra})


def runner_for(
    shell: ScriptedShell | None, area: FakeArea | None, max_chars: int | None = None
) -> CommandRunner:
    registry = InMemoryToolRegistry(max_output_chars=max_chars)
    registry.register(ShellTool(shell, area))
    return make_command_runner(registry, "shell")


@pytest.fixture
def area(tmp_path: Any) -> FakeArea:
    return FakeArea(tmp_path)


async def test_exit_zero(area: FakeArea) -> None:
    run = runner_for(ScriptedShell(ShellResult(0, "hola\n")), area)

    outcome = await run(call())

    assert (outcome.ran, outcome.exit_code, outcome.timed_out) == (True, 0, False)
    assert outcome.output.strip() == "hola"


async def test_exit_with_another_code(area: FakeArea) -> None:
    run = runner_for(ScriptedShell(ShellResult(3, "mal\n")), area)

    outcome = await run(call())

    assert (outcome.ran, outcome.exit_code, outcome.output.strip()) == (True, 3, "mal")


async def test_a_large_exit_code(area: FakeArea) -> None:
    run = runner_for(ScriptedShell(ShellResult(3221225786, "x")), area)

    assert (await run(call())).exit_code == 3221225786


async def test_a_timeout_has_no_exit_code_and_keeps_the_limit(area: FakeArea) -> None:
    shell = ScriptedShell(ShellResult(-1, "a medias", timed_out=True))
    run = runner_for(shell, area)

    outcome = await run(call(timeout_seconds=5))

    assert (outcome.ran, outcome.exit_code, outcome.timed_out) == (True, None, True)
    assert outcome.timeout_seconds == 5.0
    assert outcome.output.strip() == "a medias"


async def test_the_default_limit_applies_when_the_call_has_none(area: FakeArea) -> None:
    shell = ScriptedShell()
    run = runner_for(shell, area)

    await run(call("ls -la"))

    assert shell.calls == [("ls -la", 120.0)]


async def test_no_output_is_empty(area: FakeArea) -> None:
    run = runner_for(ScriptedShell(ShellResult(0, "")), area)

    assert (await run(call())).output == ""


async def test_the_credentials_of_urls_never_get_through(area: FakeArea) -> None:
    run = runner_for(ScriptedShell(ShellResult(1, f"clonando {CREDENTIAL}")), area)

    outcome = await run(call())

    assert "secreto-de-prueba" not in outcome.output and "usuario-de-prueba" not in outcome.output


async def test_a_long_output_comes_back_cut_by_the_registry(area: FakeArea) -> None:
    run = runner_for(ScriptedShell(ShellResult(1, "x" * 50_000)), area, max_chars=2_000)

    outcome = await run(call())

    assert len(outcome.output) <= 2_000 and "[salida recortada: se omitieron " in outcome.output


async def test_without_a_work_area_it_did_not_run() -> None:
    run = runner_for(ScriptedShell(), None)

    assert await run(call()) == CommandOutcome(ran=False)


async def test_an_interpreter_that_cannot_start_did_not_run(area: FakeArea) -> None:
    run = runner_for(ScriptedShell(OSError(SENTINEL)), area)

    outcome = await run(call())

    assert outcome == CommandOutcome(ran=False)


async def test_a_shell_that_fails_did_not_run_and_says_nothing_about_it(area: FakeArea) -> None:
    run = runner_for(ScriptedShell(RuntimeError(SENTINEL)), area)

    outcome = await run(call())

    assert outcome == CommandOutcome(ran=False) and SENTINEL not in repr(outcome)


@pytest.mark.parametrize(
    "arguments",
    [{"command": ""}, {"command": "ls", "otro": 1}, {"command": "ls", "timeout_seconds": 0}, {}],
)
async def test_arguments_that_do_not_validate_did_not_run(
    area: FakeArea, arguments: dict[str, Any]
) -> None:
    shell = ScriptedShell()
    run = runner_for(shell, area)

    outcome = await run(ToolCall(id="v", name="shell", arguments=arguments))

    assert outcome == CommandOutcome(ran=False) and shell.calls == []


async def test_a_tool_that_is_not_registered_did_not_run() -> None:
    run = make_command_runner(InMemoryToolRegistry(), "shell")

    assert await run(call()) == CommandOutcome(ran=False)


async def test_a_registry_that_validates_but_has_no_tool_did_not_run() -> None:
    class NoTool(InMemoryToolRegistry):
        def get(self, name: str) -> None:
            return None

    registry = NoTool()
    registry.register(ShellTool(ScriptedShell(), FakeArea(Path("."))))

    run = make_command_runner(registry, "shell")

    assert await run(call()) == CommandOutcome(ran=False)


async def test_cancellation_is_never_swallowed() -> None:
    class Cancelled(DummyTool):
        async def run(self, args: dict[str, Any]) -> ToolResult:
            raise asyncio.CancelledError

    registry = InMemoryToolRegistry()
    registry.register(Cancelled("shell", schema={"type": "object", "properties": {}}))
    run = make_command_runner(registry, "shell")

    with pytest.raises(asyncio.CancelledError):
        await run(ToolCall(id="v", name="shell", arguments={}))


@pytest.mark.parametrize(
    "result",
    [
        ToolResult("", "[sin_area] No hay un área.", True),
        ToolResult("", "[argumentos_invalidos] mal", True),
        ToolResult("", "[interprete_no_disponible] mal", True),
        ToolResult("", "[error_de_shell] mal", True),
        ToolResult("", "algo que no es de la herramienta", False),
        ToolResult("", "", False),
        ToolResult("", "[codigo_de_salida=abc] raro", True),
        None,
        "texto",
    ],
)
def test_anything_else_is_not_a_run(result: object) -> None:
    assert outcome_from_result(result) == CommandOutcome(ran=False)
