"""Review prompt of the terminal: shows the summary and the diff and reads the decision (HU-11-05).

``ConsoleReviewer`` implements the ``ChangeReviewer`` port for the CLI. It shows the block of
``review_view`` and reads ``1`` (approve and commit), ``2`` (show the whole diff), ``3`` (reject,
with an optional reason), ``4 N`` (confirm the semantic criterion N) or ``5 N`` (reject it, with an
optional reason). A bare ``4`` or ``5`` works when exactly one criterion is waiting. It fails
closed on its own: the end of the input, ``/salir`` or an invalid option repeated ``max_attempts``
times mean *no decision* (nothing is committed). The invalid text is never echoed and the reason is
never written back. The input is read with the same blocking ``readline`` as ``run_cli``.
"""

from __future__ import annotations

import sys
from typing import TextIO

from harness_agent.core import Choice, ReviewDecision, ReviewView, clean_reason

from .app import put_line
from .render import sanitize
from .review_view import diff_lines, review_block
from .style import Style, detect_style

DEFAULT_ATTEMPTS = 3
PROMPT = "opción> "
INVALID_OPTION = "Opción no válida: escribe 1, 2, 3, 4 N o 5 N."
NEEDS_NUMBER = "Indica el número del criterio: 4 N o 5 N."
REASON_PROMPT = "motivo (opcional, Enter para omitir)> "
EXIT_COMMAND = "/salir"
MAX_REASON_READ = 1_000


class ConsoleReviewer:
    """Asks the person in the terminal; ``input_stream``/``output`` default to the standard ones.

    Args:
        input_stream: Where the choice is read from (``sys.stdin`` when ``None``).
        output: Where the review is written (``sys.stdout`` when ``None``).
        max_attempts: Invalid answers tolerated before there is no decision (at least 1).
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
        self._shown_patch: str | None = None

    def inform(self, text: str) -> None:
        """Write one line (cleaned) for the person."""
        put_line(self._stream(), sanitize(" ".join(text.split())))

    async def choose(self, view: ReviewView) -> ReviewDecision:
        """Show the review and read the decision; ``NONE`` when there is none."""
        source, stream = self._source(), self._stream()
        style = detect_style(stream) if self._style is None else self._style
        again = self._shown_patch == view.changes.patch
        self._shown_patch = view.changes.patch
        put_line(stream, "")
        for line in review_block(view, style, with_diff=not again):
            put_line(stream, line)
        invalid = 0
        while invalid < self._max_attempts:
            put_line(stream, PROMPT, end="")
            answer = source.readline()
            if answer == "":  # end of the input
                put_line(stream, "")
                return ReviewDecision(Choice.NONE)
            text = answer.strip()
            if text == EXIT_COMMAND:
                return ReviewDecision(Choice.NONE)
            decision = self._parse(text, view, source, stream, style)
            if decision is not None:
                return decision
            invalid += 1
        return ReviewDecision(Choice.NONE)

    def _parse(
        self, text: str, view: ReviewView, source: TextIO, stream: TextIO, style: Style
    ) -> ReviewDecision | None:
        """The decision for ``text``; ``None`` to keep asking (also after showing the diff)."""
        word, _, rest = text.partition(" ")
        if word == "1" and not rest:
            return ReviewDecision(Choice.APPROVE)
        if word == "2" and not rest:
            for line in diff_lines(view.changes.patch, style):
                put_line(stream, line)
            return None
        if word == "3" and not rest:
            return ReviewDecision(Choice.REJECT, None, self._read_reason(source, stream))
        if word in ("4", "5"):
            number = self._criterion_number(rest.strip(), view)
            if number is None:
                put_line(stream, NEEDS_NUMBER if not rest.strip() else INVALID_OPTION)
                return None
            if word == "4":
                return ReviewDecision(Choice.CONFIRM, number)
            reason = self._read_reason(source, stream)
            return ReviewDecision(Choice.REJECT_CRITERION, number, reason)
        put_line(stream, INVALID_OPTION)
        return None

    @staticmethod
    def _criterion_number(text: str, view: ReviewView) -> int | None:
        waiting = view.pending_human
        if not text:
            return waiting[0] if len(waiting) == 1 else None
        if text.isascii() and text.isdigit() and len(text) <= 6:
            return int(text)
        return None

    @staticmethod
    def _read_reason(source: TextIO, stream: TextIO) -> str | None:
        """Ask why; an empty line, the end of the input or ``/salir`` mean no reason."""
        put_line(stream, REASON_PROMPT, end="")
        answer = source.readline()
        if answer == "":
            put_line(stream, "")
            return None
        if answer.strip() == EXIT_COMMAND:
            return None
        return clean_reason(answer[:MAX_REASON_READ])

    def _source(self) -> TextIO:
        return sys.stdin if self._input is None else self._input

    def _stream(self) -> TextIO:
        return sys.stdout if self._output is None else self._output
