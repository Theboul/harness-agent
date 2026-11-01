"""The block that asks the person a question with options: pure text, no input or output (HU-06-02).

The question and the options come from the model, so they are data to show: control characters
are removed, line breaks become spaces so a value never breaks the layout, and every text is
bounded. The decoration is ASCII on purpose, like the approval block.
"""

from __future__ import annotations

from collections.abc import Sequence

from .render import bounded, sanitize
from .style import PLAIN, Style

MAX_QUESTION_SHOWN = 300
MAX_OPTION_SHOWN = 120
MAX_OPTIONS_SHOWN = 20
HELP_WITH_TEXT = " Escribe el número de una opción o tu respuesta, y pulsa Enter."
HELP_NUMBER_ONLY = " Escribe el número de una opción y pulsa Enter."


def _one_line(value: object, limit: int) -> str:
    text = value if isinstance(value, str) else str(value)
    return bounded(" ".join(sanitize(text).split()), limit)


def question_block(
    text: str, options: Sequence[str], allow_free_text: bool, style: Style = PLAIN
) -> list[str]:
    """The lines of the question: the text, one numbered line per option and a line of help."""
    lines = [style.paint("? " + _one_line(text, MAX_QUESTION_SHOWN), "bold", "cyan")]
    for number, option in enumerate(options[:MAX_OPTIONS_SHOWN], start=1):
        lines.append(f"  [{number}] {_one_line(option, MAX_OPTION_SHOWN)}")
    lines.append(style.paint(HELP_WITH_TEXT if allow_free_text else HELP_NUMBER_ONLY, "dim"))
    return lines
