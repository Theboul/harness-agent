"""Color of the terminal: when it is used and how a piece of text is painted (HU-06-05).

Color is only a help for the eye: the plain text carries all the information, so a painted text
without its codes is exactly the plain one. It is on only when the output is a terminal,
``NO_COLOR`` is not set, the terminal is not ``dumb`` and, on Windows, there is a sign that the
console understands ANSI codes (the classic console does not and would show them as garbage).

This is the only module of the CLI that knows ANSI codes or reads the environment. The stream, the
environment and the platform are injectable.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

ESCAPE = "\x1b"
RESET = ESCAPE + "[0m"
CODES: Mapping[str, str] = {
    "bold": "1",
    "dim": "2",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "cyan": "36",
}
# Signs that a Windows console understands ANSI codes (Windows Terminal, ANSICON, ConEmu, VS Code).
_WINDOWS_ANSI_VARIABLES = ("WT_SESSION", "ANSICON", "TERM_PROGRAM")


@dataclass(frozen=True)
class Style:
    """Whether to paint, and the way to paint a text."""

    enabled: bool = False

    def paint(self, text: str, *names: str) -> str:
        """``text`` wrapped in the codes of ``names``; unchanged when color is off or unknown."""
        if not self.enabled or not text:
            return text
        codes = [CODES[name] for name in names if name in CODES]
        if not codes:
            return text
        return f"{ESCAPE}[{';'.join(codes)}m{text}{RESET}"


PLAIN = Style(enabled=False)


def _is_terminal(stream: Any) -> bool:
    check = getattr(stream, "isatty", None)
    if check is None:
        return False
    try:
        return bool(check())
    except (ValueError, OSError):
        return False


def _windows_understands_ansi(environ: Mapping[str, str]) -> bool:
    if environ.get("ConEmuANSI", "").upper() == "ON":
        return True
    return any(environ.get(name) for name in _WINDOWS_ANSI_VARIABLES)


def detect_style(
    stream: Any, environ: Mapping[str, str] | None = None, platform: str | None = None
) -> Style:
    """The style for ``stream``: painted only on a terminal that is known to understand it.

    Args:
        stream: The output stream (anything with ``isatty``).
        environ: Environment variables; ``os.environ`` when ``None``.
        platform: ``sys.platform`` value; the real one when ``None``.
    """
    variables = os.environ if environ is None else environ
    system = sys.platform if platform is None else platform
    if not _is_terminal(stream):
        return PLAIN
    if variables.get("NO_COLOR"):
        return PLAIN
    if variables.get("TERM") == "dumb":
        return PLAIN
    if system == "win32" and not _windows_understands_ansi(variables):
        return PLAIN
    return Style(enabled=True)
