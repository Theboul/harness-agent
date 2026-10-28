"""A command that takes the text after its name: the only change in the CLI (HU-03-04 / T008)."""

from __future__ import annotations

import inspect
import io

import pytest

from harness_agent.cli import run_cli
from harness_agent.cli.app import HELP_TEXT
from harness_agent.core import InMemoryEventBus


async def run(
    lines: str,
    *,
    argument_commands: object = None,
    commands: object = None,
    turns: list[str] | None = None,
) -> tuple[int, str]:
    output = io.StringIO()

    async def run_turn(task: str) -> object:
        if turns is not None:
            turns.append(task)
        return None

    options: dict[str, object] = {}
    if argument_commands is not None:
        options["argument_commands"] = argument_commands
    if commands is not None:
        options["commands"] = commands
    code = await run_cli(
        InMemoryEventBus(),
        run_turn,
        input_stream=io.StringIO(lines),
        output=output,
        **options,  # type: ignore[arg-type]
    )
    return code, output.getvalue()


async def test_the_command_receives_the_text_after_its_name_without_outer_spaces() -> None:
    received: list[str] = []

    def reanudar(argument: str) -> str:
        received.append(argument)
        return f"listo ({len(argument)})"

    _, shown = await run(
        "/reanudar   abc-123  \n/salir\n",
        argument_commands={"/reanudar": ("Reanuda una sesión.", reanudar)},
    )

    assert received == ["abc-123"] and "listo (7)" in shown


async def test_the_command_without_an_argument_receives_an_empty_text() -> None:
    received: list[str] = []

    def reanudar(argument: str) -> str:
        received.append(argument)
        return "uso"

    _, shown = await run(
        "/reanudar\n/salir\n",
        argument_commands={"/reanudar": ("Reanuda.", reanudar)},
    )

    assert received == [""] and "uso" in shown


async def test_it_is_a_command_and_never_a_task() -> None:
    turns: list[str] = []

    await run(
        "/reanudar x\nuna tarea\n/salir\n",
        argument_commands={"/reanudar": ("Reanuda.", lambda argument: "hecho")},
        turns=turns,
    )

    assert turns == ["una tarea"]


async def test_it_is_listed_in_the_help_after_the_other_extra_commands() -> None:
    _, shown = await run(
        "/ayuda\n/salir\n",
        argument_commands={"/reanudar": ("Reanuda una sesión guardada.", lambda a: "")},
        commands={"/criterios": ("Muestra el estado.", lambda: "")},
    )

    lines = shown.splitlines()
    criteria = lines.index("  /criterios  Muestra el estado.")
    resume = lines.index("  /reanudar  Reanuda una sesión guardada.")
    assert criteria + 1 == resume
    assert lines[resume + 1] == HELP_TEXT.splitlines()[-1]


async def test_both_kinds_of_commands_work_together() -> None:
    _, shown = await run(
        "/criterios\n/reanudar x\n/salir\n",
        argument_commands={"/reanudar": ("Reanuda.", lambda a: f"reanudado {a}")},
        commands={"/criterios": ("Estado.", lambda: "criterios al día")},
    )

    assert "criterios al día" in shown and "reanudado x" in shown


async def test_without_argument_commands_everything_is_as_before() -> None:
    _, shown = await run("/ayuda\n/reanudar x\n/salir\n")

    assert HELP_TEXT in shown
    assert "Comando desconocido: '/reanudar'." in shown
    assert "/reanudar  " not in shown


async def test_a_function_that_raises_is_not_caught_just_like_the_other_commands() -> None:
    def broken(argument: str) -> str:
        raise RuntimeError("fallo")

    with pytest.raises(RuntimeError):
        await run("/reanudar x\n", argument_commands={"/reanudar": ("Reanuda.", broken)})


def test_the_only_new_parameter_of_run_cli_is_argument_commands() -> None:
    parameters = list(inspect.signature(run_cli).parameters)

    assert parameters == [
        "bus",
        "run_turn",
        "input_stream",
        "output",
        "commands",
        "argument_commands",
    ]
