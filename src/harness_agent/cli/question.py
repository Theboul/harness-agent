"""Question prompt of the terminal: shows the question and reads the answer (HU-06-02).

``ConsoleQuestioner`` is the console side of the ``preguntar_usuario`` tool. It shows the block of
``question_view`` and reads a line: the number of an option, or (when the question allows it) a
free text. It fails closed on its own: the end of the input, ``/salir`` or an invalid line repeated
``max_attempts`` times mean *no answer* (``None``); an option is never chosen by default. The
invalid text is never echoed. The input is read with the same blocking ``readline`` as ``run_cli``
and the approval prompt, from the same stream.

The CLI does not import the adapters: the question is read through ``QuestionLike`` (a protocol)
and the answer is the ``Reply`` of this module; the composition root converts them.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Protocol, TextIO

from .app import put_line
from .question_view import question_block
from .style import Style, detect_style

DEFAULT_ATTEMPTS = 3
PROMPT = "respuesta> "
EXIT_COMMAND = "/salir"
MAX_READ = 1_000
INVALID_WITH_TEXT = "Respuesta no válida: escribe el número de una opción o tu respuesta."
INVALID_NUMBER_ONLY = "Opción no válida: escribe el número de una opción."


class QuestionLike(Protocol):
    """What the console needs to ask: the text, the options and whether free text is accepted."""

    @property
    def text(self) -> str: ...

    @property
    def options(self) -> tuple[str, ...]: ...

    @property
    def allow_free_text(self) -> bool: ...


@dataclass(frozen=True)
class Reply:
    """The answer of the person: the number of an option (1-based) or a free text."""

    number: int | None = None
    text: str = ""


class ConsoleQuestioner:
    """Asks the person in the terminal; ``input_stream``/``output`` default to the standard ones.

    Args:
        input_stream: Where the answer is read from (``sys.stdin`` when ``None``).
        output: Where the question is written (``sys.stdout`` when ``None``).
        max_attempts: Invalid lines tolerated before there is no answer (at least 1).
        style: How the block is painted; decided from the output stream when ``None``.
    """

    def __init__(
        self,
        input_stream: TextIO | None = None,
        output: TextIO | None = None,
        *,
        max_attempts: int = DEFAULT_ATTEMPTS,
        style: Style | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("Debe haber al menos un intento.")
        self._input = input_stream
        self._output = output
        self._max_attempts = max_attempts
        self._style = style

    async def __call__(self, question: QuestionLike) -> Reply | None:
        """Show ``question`` and read the answer; ``None`` when there is none."""
        source = sys.stdin if self._input is None else self._input
        stream = sys.stdout if self._output is None else self._output
        style = detect_style(stream) if self._style is None else self._style
        options, free = question.options, question.allow_free_text
        put_line(stream, "")
        for line in question_block(question.text, options, free, style):
            put_line(stream, line)
        for _ in range(self._max_attempts):
            put_line(stream, PROMPT, end="")
            answer = source.readline()
            if answer == "":  # end of the input
                put_line(stream, "")
                return None
            text = answer.strip()
            if text == EXIT_COMMAND:
                return None
            if text.isascii() and text.isdigit() and len(text) <= 6:
                if 1 <= int(text) <= len(options):
                    return Reply(number=int(text))
            elif text and free:
                return Reply(text=text[:MAX_READ])
            put_line(stream, INVALID_WITH_TEXT if free else INVALID_NUMBER_ONLY)
        return None
