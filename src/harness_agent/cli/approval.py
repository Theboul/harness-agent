"""Approval prompt of the terminal: shows what is asked and reads the user's choice (HU-05-03).

``ConsoleApprover`` implements the ``Approver`` port for the CLI. It shows the block of
``approval_view`` (what the agent wants to do, the highlighted command or path, the risk and the
effect; HU-06-05), then reads ``1`` (approve once), ``2`` (approve for the session) or ``3``
(reject). After ``3`` it asks for an optional reason (HU-05-04): an empty line, the end of the
input or ``/salir`` mean no reason, and the reason is never written back. It fails closed on its
own: the end of the input, or an invalid option repeated ``max_attempts`` times, is a rejection;
the invalid text is never echoed. The values of arguments whose name looks like a secret are
hidden. A broken stream raises; the approval gate of the core turns that into a denial.

The input is read with the same blocking ``readline`` that ``run_cli`` uses, from the same stream.
"""

from __future__ import annotations

import sys
from typing import Any, TextIO

from harness_agent.core import ApprovalAction, ApprovalResult, Approver, ToolCall, clean_reason

from .app import put_line
from .approval_view import approval_block
from .style import Style, detect_style

DEFAULT_ATTEMPTS = 3
PROMPT = "opción> "
INVALID_OPTION = "Opción no válida: escribe 1, 2 o 3."
REASON_PROMPT = "motivo (opcional, Enter para omitir)> "
EXIT_COMMAND = "/salir"
CHOICES = {
    "1": ApprovalAction.APPROVE_ONCE,
    "2": ApprovalAction.APPROVE_SESSION,
    "3": ApprovalAction.REJECT,
}


class ConsoleApprover(Approver):
    """Asks the user in the terminal; ``input_stream``/``output`` default to the standard ones.

    Args:
        input_stream: Where the choice is read from (``sys.stdin`` when ``None``).
        output: Where the question is written (``sys.stdout`` when ``None``).
        max_attempts: Invalid answers tolerated before the request is rejected (at least 1).
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

    async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult:
        """Show the detail and read the choice; reject on the end of the input."""
        source = sys.stdin if self._input is None else self._input
        stream = sys.stdout if self._output is None else self._output
        style = detect_style(stream) if self._style is None else self._style
        put_line(stream, "")
        for line in approval_block(call.name, details, style):
            put_line(stream, line)
        for _ in range(self._max_attempts):
            put_line(stream, PROMPT, end="")
            answer = source.readline()
            if answer == "":  # end of the input
                put_line(stream, "")
                return ApprovalResult(ApprovalAction.REJECT)
            if answer.strip() == EXIT_COMMAND:  # the user wants out: nothing is approved
                return ApprovalResult(ApprovalAction.REJECT)
            action = CHOICES.get(answer.strip())
            if action is ApprovalAction.REJECT:
                return ApprovalResult(action, self._read_reason(source, stream))
            if action is not None:
                return ApprovalResult(action)
            put_line(stream, INVALID_OPTION)
        return ApprovalResult(ApprovalAction.REJECT)

    @staticmethod
    def _read_reason(source: TextIO, stream: TextIO) -> str | None:
        """Ask why; an empty line, the end of the input or ``/salir`` mean no reason.

        The reason is cleaned here too, and it is never written back to the output.
        """
        put_line(stream, REASON_PROMPT, end="")
        answer = source.readline()
        if answer == "":
            put_line(stream, "")
            return None
        if answer.strip() == EXIT_COMMAND:
            return None
        return clean_reason(answer)
