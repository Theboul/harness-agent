"""Helpers shared by the file tools: error results and real-path resolution (HU-01-03).

The authorized area is the only authority on what is inside it. A tool asks it twice before it
acts: first with the text it received (so a hostile Windows path is rejected before ``realpath``
can touch the network or the disk) and then with the real path it computed.
"""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

from harness_agent.adapters.tools._limits import MAX_RESULT_CHARS
from harness_agent.core import AuthorizedArea, ToolResult

MAX_PATH_ECHO_CHARS = 100
TRUNCATED = "\n[resultado recortado]"


def error_result(category: str, message: str) -> ToolResult:
    """A structured error for the model: ``[category] cause and suggestion``."""
    return ToolResult(call_id="", content=f"[{category}] {message}", is_error=True)


def bounded_path(raw: object) -> str:
    """The path as received, safe to show: no control characters and at most 100 characters."""
    text = "".join("?" if unicodedata.category(char) == "Cc" else char for char in str(raw))
    if len(text) <= MAX_PATH_ECHO_CHARS:
        return text
    return text[: MAX_PATH_ECHO_CHARS - 3] + "..."


def bounded_text(text: str, limit: int = MAX_RESULT_CHARS) -> str:
    """``text`` cut to ``limit`` characters, with a notice when something was left out."""
    if len(text) <= limit:
        return text
    return text[: limit - len(TRUNCATED)] + TRUNCATED


def outside_area(raw: object) -> ToolResult:
    """The error for a path that is not inside the area (or cannot be checked)."""
    return error_result(
        "fuera_del_area",
        f"La ruta '{bounded_path(raw)}' queda fuera del área de trabajo. "
        "Usa una ruta dentro del área.",
    )


def resolve_in_area(area: AuthorizedArea | None, raw: object) -> Path | ToolResult:
    """The real path of ``raw`` if the area accepts it, otherwise the error to return.

    Never raises: anything that cannot be checked is outside the area (fail closed).
    """
    if area is None:
        return error_result(
            "sin_area",
            "No hay un área de trabajo configurada, así que no se puede actuar sobre archivos. "
            "Configura 'workspace_root' en config.toml.",
        )
    try:
        if not isinstance(raw, str) or area.contains(raw) is not True:
            return outside_area(raw)
        real = Path(os.path.realpath(os.path.join(area.root, raw)))
        if area.contains(real) is not True:
            return outside_area(raw)
    except Exception:
        return outside_area(raw)
    return real
