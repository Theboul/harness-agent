"""Where the stderr of an MCP server goes (HU-08-01 / FR-006): a file, never the terminal.

This is the only module of the package that touches a file, and it only opens it for writing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TextIO


def open_stderr_log(path: Path | None) -> TextIO:
    """Open ``path`` for writing (replacing its content); the null device if there is no path or
    it cannot be opened (a folder, no permission, a read-only disk).

    The caller closes the stream when the server is gone.
    """
    if path is not None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return open(path, "w", encoding="utf-8")
        except OSError:
            pass
    return open(os.devnull, "w", encoding="utf-8")
