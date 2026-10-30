"""A command may be asynchronous: the CLI waits for its text (HU-06-05 / T003, research R4)."""

from __future__ import annotations

import asyncio
import io

import pytest

from harness_agent.cli import run_cli
from harness_agent.core import InMemoryEventBus


async def run(
    lines: str, *, commands: object = None, argument_commands: object = None
) -> tuple[int, str]:
    async def turn(task: str) -> object:
        return None

    output = io.StringIO()
    code = await run_cli(
        InMemoryEventBus(),
        turn,
        input_stream=io.StringIO(lines),
        output=output,
        commands=commands,  # type: ignore[arg-type]
        argument_commands=argument_commands,  # type: ignore[arg-type]
    )
    return code, output.getvalue()


async def test_an_async_command_without_arguments_is_awaited() -> None:
    async def compact() -> str:
        await asyncio.sleep(0)
        return "compactado"

    _, shown = await run("/compactar\n/salir\n", commands={"/compactar": ("Compacta.", compact)})

    assert "compactado\n" in shown
    assert "coroutine" not in shown


async def test_an_async_command_with_an_argument_is_awaited() -> None:
    async def resume(argument: str) -> str:
        await asyncio.sleep(0)
        return f"reanudado {argument}"

    _, shown = await run(
        "/reanudar abc\n/salir\n", argument_commands={"/reanudar": ("Reanuda.", resume)}
    )

    assert "reanudado abc\n" in shown


async def test_a_sync_command_still_works() -> None:
    _, shown = await run("/criterios\n/salir\n", commands={"/criterios": ("Estado.", lambda: "ok")})

    assert "ok\n" in shown


async def test_an_async_command_that_fails_is_not_swallowed() -> None:
    async def broken() -> str:
        raise RuntimeError("fallo")

    with pytest.raises(RuntimeError):
        await run("/compactar\n", commands={"/compactar": ("Compacta.", broken)})
