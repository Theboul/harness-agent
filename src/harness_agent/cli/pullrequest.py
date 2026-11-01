"""Confirmations of the Pull Request step in the terminal (HU-11-06).

``ConsolePullRequestPrompter`` implements the ``PullRequestPrompter`` port for the CLI. Each
outgoing action (push, creation) gets its own question and reads ``1`` (yes) or ``2`` (no). It fails
closed on its own: the end of the input, ``/salir`` or ``max_attempts`` invalid answers mean *no*.
Nothing is remembered between questions. The invalid text is never echoed and everything shown is
cleaned for the terminal. The input is read with the same blocking ``readline`` as ``run_cli``.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TextIO

from harness_agent.core import REMOTE, PullRequestDraft

from .app import put_line
from .render import sanitize

DEFAULT_ATTEMPTS = 3
PROMPT = "opción> "
INVALID_OPTION = "Opción no válida: escribe 1 o 2."
EXIT_COMMAND = "/salir"


class ConsolePullRequestPrompter:
    """Asks the person in the terminal; ``input_stream``/``output`` default to the standard ones.

    Args:
        input_stream: Where the answer is read from (``sys.stdin`` when ``None``).
        output: Where the question is written (``sys.stdout`` when ``None``).
        max_attempts: Invalid answers tolerated before the answer is *no* (at least 1).
    """

    def __init__(
        self,
        input_stream: TextIO | None = None,
        output: TextIO | None = None,
        *,
        max_attempts: int = DEFAULT_ATTEMPTS,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("Debe haber al menos un intento.")
        self._input = input_stream
        self._output = output
        self._max_attempts = max_attempts

    def show(self, lines: Sequence[str]) -> None:
        """Write the lines (cleaned) for the person."""
        stream = self._stream()
        for line in lines:
            put_line(stream, sanitize(line))

    async def confirm_push(self, branch: str) -> bool:
        """Ask whether ``branch`` may be pushed to the remote."""
        self.show(
            [
                "",
                "Pull Request del ticket: el commit ya está hecho.",
                f"Se subirá la rama '{branch}' al remoto '{REMOTE}' (git push).",
                "[1] subir la rama  [2] no subir",
            ]
        )
        return self._answer()

    async def confirm_create(self, draft: PullRequestDraft) -> bool:
        """Show the draft and ask whether the Pull Request may be created."""
        self.show(
            [
                "",
                f"Se creará un Pull Request desde la rama '{draft.branch}' con la CLI de GitHub.",
                f"Título: {draft.title}",
                "Descripción:",
                *draft.body.splitlines(),
                "[1] crear el Pull Request  [2] no crear",
            ]
        )
        return self._answer()

    def _answer(self) -> bool:
        source, stream = self._source(), self._stream()
        invalid = 0
        while invalid < self._max_attempts:
            put_line(stream, PROMPT, end="")
            answer = source.readline()
            if answer == "":  # end of the input
                put_line(stream, "")
                return False
            text = answer.strip()
            if text == EXIT_COMMAND or text == "2":
                return False
            if text == "1":
                return True
            put_line(stream, INVALID_OPTION)
            invalid += 1
        return False

    def _source(self) -> TextIO:
        return sys.stdin if self._input is None else self._input

    def _stream(self) -> TextIO:
        return sys.stdout if self._output is None else self._output
