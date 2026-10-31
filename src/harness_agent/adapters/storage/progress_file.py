"""Atomic write of the progress file of a ticket in the work folder (HU-11-08.1).

The text goes to a temporary file of the same folder, is flushed to disk and then renamed over the
destination, so a reader (or a process killed at any point) sees the previous complete file or the
new complete one, never half of it. A symbolic link at the destination is replaced, not written
through. Messages are fixed Spanish texts: they never reproduce paths, names or the cause.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

from harness_agent.adapters.storage.errors import ProgressWriteError

_NAME = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*\.md")
MAX_NAME_CHARS = 100

_Replace = Callable[[str | Path, str | Path], None]


def _check_name(name: str) -> None:
    if len(name) > MAX_NAME_CHARS or _NAME.fullmatch(name) is None:
        raise ProgressWriteError("El nombre del archivo de progreso no es válido.")


class ProgressFile:
    """The ``ProgressSink`` of the core over a folder: ``write`` is atomic, ``read`` is plain.

    Args:
        root: The folder of the ticket's repository where the file lives; it must exist.
        replace: Renames the temporary file over the destination; ``os.replace`` unless a test
            injects a failing one.
    """

    def __init__(self, root: Path, *, replace: _Replace = os.replace) -> None:
        self._root = root
        self._replace = replace

    def write(self, name: str, text: str) -> None:
        """Leave ``text`` in ``<root>/<name>`` whole, or the previous content if anything fails.

        Raises:
            ProgressWriteError: The name is not a plain ``.md`` file name or the file could not be
                written; the previous content, if any, is untouched and no temporary is left.
        """
        _check_name(name)
        destination = self._root / name
        temporary = self._root / f".{name}.tmp"
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            self._replace(temporary, destination)
        except OSError:
            self._discard(temporary)
            raise ProgressWriteError("No se pudo escribir el archivo de progreso.") from None
        except BaseException:
            self._discard(temporary)
            raise

    def read(self, name: str) -> str | None:
        """The text of ``<root>/<name>``, or ``None`` if it does not exist.

        Raises:
            ProgressWriteError: The name is not valid or the file could not be read.
        """
        _check_name(name)
        try:
            with (self._root / name).open(encoding="utf-8", errors="replace") as handle:
                return handle.read()
        except FileNotFoundError:
            return None
        except OSError:
            raise ProgressWriteError("No se pudo leer el archivo de progreso.") from None

    @staticmethod
    def _discard(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
