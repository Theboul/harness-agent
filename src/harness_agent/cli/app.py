"""The terminal side of HARNESS: subscription to the bus and the input cycle (HU-06-01).

The CLI only shows what the core published: it does not decide permissions, validate or run tools.
It talks to the core through the ``EventBus`` port and a function that runs one turn, both
injected. Output and input are injectable streams (the standard ones by default).

``run_cli`` returns the exit code of the session: ``EXIT_OK`` when it ends cleanly (``/salir`` or
the end of the input) and ``EXIT_FAILURE`` when the turn function raised an ordinary exception
(D9): then one line with the type of the error is shown and the session ends. Anything that is not
an ``Exception`` (cancellation, keyboard interrupt) and a failure while writing that line go up.
"""

from __future__ import annotations

import sys
from collections.abc import Awaitable, Callable
from typing import TextIO

from harness_agent.core import Event, EventBus

from .render import (
    MAX_COMMAND_CHARS,
    SHOWN_TYPES,
    bounded,
    render_event,
    sanitize,
    turn_failure_line,
)

PROMPT = "tarea> "
EXIT_OK = 0
EXIT_FAILURE = 1
HELP_TEXT = (
    "Comandos disponibles:\n"
    "  /ayuda  Muestra esta ayuda.\n"
    "  /salir  Termina la sesión.\n"
    "Cualquier otra línea se envía al agente como una tarea nueva."
)
EXIT_TEXT = "Sesión terminada."

TurnRunner = Callable[[str], Awaitable[object]]


def _put(stream: TextIO, text: str) -> None:
    """Write ``text`` as it is and flush, replacing what the stream cannot encode.

    The stream is not reconfigured: the text is adapted to its declared encoding. A failure of
    ``write`` or ``flush`` is not caught here.
    """
    encoding = getattr(stream, "encoding", None)
    if encoding:
        text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    stream.write(text)
    stream.flush()


def _write_line(stream: TextIO, text: str) -> None:
    _put(stream, text + "\n")


def put_line(stream: TextIO, text: str, *, end: str = "\n") -> None:
    """Write ``text`` plus ``end`` as the CLI does (shared with the approval prompt)."""
    _put(stream, text + end)


def attach_renderer(bus: EventBus, output: TextIO | None = None) -> None:
    """Subscribe the CLI to the bus: every shown event type writes its line on ``output``.

    ``output`` is ``sys.stdout`` at the moment of the call when it is not given. The bus has no
    unsubscribe: attaching twice to the same bus duplicates the output.
    """
    stream = sys.stdout if output is None else output

    def show(event: Event) -> None:
        text = render_event(event)
        if text is not None:
            _write_line(stream, text)

    for event_type in SHOWN_TYPES:
        bus.subscribe(event_type, show)


def _without_line_break(line: str) -> str:
    if line.endswith("\r\n"):
        return line[:-2]
    return line[:-1] if line.endswith("\n") else line


def _unknown_command(command: str) -> str:
    shown = bounded(sanitize(command), MAX_COMMAND_CHARS)
    return f"Comando desconocido: '{shown}'. Escribe /ayuda para ver los comandos disponibles."


async def run_cli(
    bus: EventBus,
    run_turn: TurnRunner,
    *,
    input_stream: TextIO | None = None,
    output: TextIO | None = None,
) -> int:
    """Read lines and run them: a task goes to ``run_turn``, ``/ayuda`` and ``/salir`` are commands.

    The render is attached to ``bus`` once, at the start. A line is a task unless it starts with
    ``/`` in the first column; the task is passed unchanged. Returns the exit code (see module).
    """
    source = sys.stdin if input_stream is None else input_stream
    stream = sys.stdout if output is None else output
    attach_renderer(bus, stream)
    while True:
        _put(stream, PROMPT)
        line = source.readline()
        if line == "":  # end of the input
            _put(stream, "\n")
            return EXIT_OK
        text = _without_line_break(line)
        if not text.strip():
            continue
        if text.startswith("/"):
            command = text.split()[0]
            if command == "/salir":
                _write_line(stream, EXIT_TEXT)
                return EXIT_OK
            _write_line(stream, HELP_TEXT if command == "/ayuda" else _unknown_command(command))
            continue
        try:
            await run_turn(text)
        except Exception as error:
            _write_line(stream, turn_failure_line(type(error).__name__))
            return EXIT_FAILURE
