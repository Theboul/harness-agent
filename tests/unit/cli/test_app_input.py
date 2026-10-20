"""Tests of the input cycle ``run_cli`` (HU-06-01 / T006).

The input and the output are in-memory streams and the function that runs a turn is a test
function that records what it receives. D9: an ordinary exception of the turn is shown in one line
(type only), ends the session and gives a non-zero exit code; any other ``BaseException`` and a
failure while writing that line go up untouched.
"""

from __future__ import annotations

import asyncio
import io
import sys
from typing import Any

import pytest

from harness_agent.cli import run_cli
from harness_agent.cli.app import EXIT_FAILURE, EXIT_OK, PROMPT
from harness_agent.core import Event, EventDeliveryError, EventType, InMemoryEventBus

SENTINEL = "VALOR-DE-PRUEBA-123"
HELP = (
    "Comandos disponibles:\n"
    "  /ayuda  Muestra esta ayuda.\n"
    "  /salir  Termina la sesión.\n"
    "Cualquier otra línea se envía al agente como una tarea nueva."
)
FAILURE_SUFFIX = "). Sugerencia: revisa el registro de eventos."
FAILURE_PREFIX = "x Error: el turno terminó con un fallo interno ("


class Turn:
    """A turn function of test: records the tasks, yields control and may fail."""

    def __init__(self, error: BaseException | None = None) -> None:
        self.tasks: list[str] = []
        self.log: list[str] = []
        self.error = error

    async def __call__(self, task: str) -> object:
        self.tasks.append(task)
        self.log.append(f"start:{task}")
        await asyncio.sleep(0)
        self.log.append(f"end:{task}")
        if self.error is not None:
            raise self.error
        return None


async def drive(
    text: str, turn: Turn | None = None, *, bus: InMemoryEventBus | None = None
) -> tuple[int, str, Turn]:
    turn = turn or Turn()
    output = io.StringIO()
    code = await run_cli(
        bus or InMemoryEventBus(), turn, input_stream=io.StringIO(text), output=output
    )
    return code, output.getvalue(), turn


class FlushSpy(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.flushes = 0

    def flush(self) -> None:
        self.flushes += 1
        super().flush()


class TestTareas:
    async def test_a_task_reaches_the_turn_once_and_unchanged(self) -> None:
        code, _output, turn = await drive("  haz   la tarea  \n")

        assert turn.tasks == ["  haz   la tarea  "]
        assert code == EXIT_OK

    async def test_windows_line_endings_are_not_part_of_the_task(self) -> None:
        _code, _output, turn = await drive("tarea uno\r\ntarea dos\r\n")

        assert turn.tasks == ["tarea uno", "tarea dos"]

    async def test_a_last_line_without_a_line_break_is_a_task(self) -> None:
        _code, _output, turn = await drive("tarea sin salto")

        assert turn.tasks == ["tarea sin salto"]

    async def test_a_line_with_leading_spaces_before_a_slash_is_a_task_not_a_command(self) -> None:
        _code, _output, turn = await drive("  /ayuda\n")

        assert turn.tasks == ["  /ayuda"]

    async def test_the_tasks_are_awaited_one_after_the_other(self) -> None:
        _code, _output, turn = await drive("uno\ndos\n")

        assert turn.log == ["start:uno", "end:uno", "start:dos", "end:dos"]

    async def test_a_very_long_task_is_not_interpreted_nor_limited(self) -> None:
        task = "a" * 100_000

        _code, _output, turn = await drive(task + "\n")

        assert turn.tasks == [task]


class TestComandos:
    @pytest.mark.parametrize("line", ["/ayuda", "/ayuda con argumentos"])
    async def test_help_writes_the_list_of_commands_and_runs_nothing(self, line: str) -> None:
        code, output, turn = await drive(line + "\n")

        assert output == PROMPT + HELP + "\n" + PROMPT + "\n"
        assert turn.tasks == []
        assert code == EXIT_OK

    async def test_exit_ends_the_cycle_and_does_not_read_the_following_lines(self) -> None:
        turn = Turn()
        source = io.StringIO("/salir\nsegunda tarea\n")
        output = io.StringIO()

        code = await run_cli(InMemoryEventBus(), turn, input_stream=source, output=output)

        assert output.getvalue() == PROMPT + "Sesión terminada.\n"
        assert turn.tasks == []
        assert source.read() == "segunda tarea\n"
        assert code == EXIT_OK

    async def test_an_unknown_command_is_reported_and_runs_nothing(self) -> None:
        code, output, turn = await drive("/sesiones uno dos\n")

        assert output == (
            PROMPT
            + "Comando desconocido: '/sesiones'. Escribe /ayuda para ver los comandos "
            + "disponibles.\n"
            + PROMPT
            + "\n"
        )
        assert turn.tasks == []
        assert code == EXIT_OK

    async def test_a_lone_slash_is_an_unknown_command(self) -> None:
        _code, output, _turn = await drive("/\n")

        assert "Comando desconocido: '/'." in output

    async def test_the_repeated_command_is_bounded_and_sanitized(self) -> None:
        _code, output, _turn = await drive("/" + "x" * 99 + "\n/a\x1b[31mb\n")

        assert f"Comando desconocido: '/{'x' * 36}...'." in output
        assert "Comando desconocido: '/a[31mb'." in output
        assert "\x1b" not in output

    @pytest.mark.parametrize("text", ["\n", "   \n", "\t\n", "\n   \n\t\n"])
    async def test_an_empty_line_is_ignored(self, text: str) -> None:
        code, output, turn = await drive(text)

        assert turn.tasks == []
        assert set(output.replace(PROMPT, "").split("\n")) == {""}
        assert code == EXIT_OK


class TestFinDeLaEntrada:
    async def test_the_end_of_the_input_ends_cleanly_with_a_line_break(self) -> None:
        code, output, turn = await drive("")

        assert output == PROMPT + "\n"
        assert turn.tasks == []
        assert code == EXIT_OK
        assert isinstance(code, int)

    async def test_the_prompt_is_written_and_flushed_before_every_read(self) -> None:
        output = FlushSpy()

        await run_cli(
            InMemoryEventBus(), Turn(), input_stream=io.StringIO("uno\ndos\n"), output=output
        )

        assert output.getvalue().count(PROMPT) == 3  # two lines read plus the end of the input
        assert output.flushes >= 3


class TestSuscripcionYValoresPorDefecto:
    async def test_the_render_is_attached_once_and_shows_the_events_of_the_turn(self) -> None:
        bus = InMemoryEventBus()

        async def turn(_task: str) -> object:
            bus.emit(Event.create("s1", EventType.TOOL_REQUESTED, {"name": "buscar"}))
            return None

        out = io.StringIO()

        await run_cli(bus, turn, input_stream=io.StringIO("haz algo\n"), output=out)

        assert out.getvalue().count("... ejecutando: buscar") == 1

    async def test_without_streams_it_uses_the_standard_ones_of_the_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        replaced_out = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.StringIO("hola\n"))
        monkeypatch.setattr(sys, "stdout", replaced_out)
        turn = Turn()

        code = await run_cli(InMemoryEventBus(), turn)

        assert turn.tasks == ["hola"]
        assert replaced_out.getvalue().startswith(PROMPT)
        assert code == EXIT_OK


class TestFalloDelTurno:
    """D9: the ordinary exceptions of the turn are shown in one line and end the session."""

    async def test_an_ordinary_failure_shows_one_line_with_the_type_only(self) -> None:
        turn = Turn(RuntimeError(f"detalle interno {SENTINEL}"))

        code, output, _ = await drive("tarea\nsegunda\n", turn)

        assert output == (
            PROMPT + FAILURE_PREFIX + "RuntimeError" + FAILURE_SUFFIX + "\n"
        )  # no further prompt: the session ended
        assert output.count("fallo interno") == 1
        assert SENTINEL not in output
        assert "Traceback" not in output
        assert code == EXIT_FAILURE
        assert code != 0

    async def test_the_session_ends_and_the_following_lines_are_not_read(self) -> None:
        turn = Turn(ValueError("x"))
        source = io.StringIO("tarea\nsegunda\n")

        code = await run_cli(InMemoryEventBus(), turn, input_stream=source, output=io.StringIO())

        assert turn.tasks == ["tarea"]
        assert source.read() == "segunda\n"
        assert code == EXIT_FAILURE

    async def test_a_delivery_error_is_an_ordinary_failure_too(self) -> None:
        turn = Turn(EventDeliveryError("mensaje", [OSError(SENTINEL)]))

        code, output, _ = await drive("tarea\n", turn)

        assert FAILURE_PREFIX + "EventDeliveryError" + FAILURE_SUFFIX in output
        assert SENTINEL not in output
        assert code == EXIT_FAILURE

    async def test_a_long_type_name_is_bounded_to_64_characters(self) -> None:
        error_type = type("T" * 100, (Exception,), {})

        _code, output, _ = await drive("tarea\n", Turn(error_type()))

        assert FAILURE_PREFIX + "T" * 61 + "..." + FAILURE_SUFFIX in output

    async def test_a_type_name_with_control_characters_is_sanitized(self) -> None:
        error_type = type("A\x1bB", (Exception,), {})

        _code, output, _ = await drive("tarea\n", Turn(error_type()))

        assert FAILURE_PREFIX + "AB" + FAILURE_SUFFIX in output
        assert "\x1b" not in output

    @pytest.mark.parametrize(
        "error", [KeyboardInterrupt(), asyncio.CancelledError(), SystemExit(3)], ids=repr
    )
    async def test_the_exceptions_that_are_not_ordinary_go_up_untouched(
        self, error: BaseException
    ) -> None:
        output = io.StringIO()

        with pytest.raises(type(error)) as raised:
            await run_cli(
                InMemoryEventBus(),
                Turn(error),
                input_stream=io.StringIO("tarea\n"),
                output=output,
            )

        assert raised.value is error
        assert "fallo interno" not in output.getvalue()

    async def test_a_failure_while_writing_the_failure_line_goes_up(self) -> None:
        class FailsOnTheFailureLine(io.StringIO):
            def write(self, text: str, /) -> int:
                if "fallo interno" in text:
                    raise OSError("salida rota")
                return super().write(text)

        original = RuntimeError("original")

        with pytest.raises(OSError, match="salida rota") as raised:
            await run_cli(
                InMemoryEventBus(),
                Turn(original),
                input_stream=io.StringIO("tarea\n"),
                output=FailsOnTheFailureLine(),
            )

        assert raised.value.__context__ is original

    async def test_a_broken_output_fails_at_the_first_write_and_nothing_is_hidden(self) -> None:
        class Broken(io.StringIO):
            def write(self, text: str, /) -> int:
                raise OSError("salida rota")

        with pytest.raises(OSError, match="salida rota"):
            await run_cli(InMemoryEventBus(), Turn(), input_stream=io.StringIO(""), output=Broken())


def test_the_exit_codes_are_the_documented_ones() -> None:
    values: dict[str, Any] = {"ok": EXIT_OK, "failure": EXIT_FAILURE}

    assert values == {"ok": 0, "failure": 1}
    assert PROMPT == "tarea> "
