"""WorkspaceArea: the real authorized area for file tools (HU-01-03).

Implements the ``AuthorizedArea`` port on the local disk. Containment is decided on the real
path of what the model asked for: ``..``, absolute paths and symbolic links cannot take a path out
of the area. It fails closed: anything that cannot be checked is outside the area.
"""

from __future__ import annotations

import ntpath
import os
import re
from pathlib import Path

from harness_agent.core import AuthorizedArea

_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)
_SEPARATORS = re.compile(r"[\\/]+")


def windows_path_problem(raw: str) -> str | None:
    """Why a path is not acceptable on Windows, or ``None`` if it has no Windows-specific hazard.

    Pure text check (no disk access), so it can be exercised on any system. It flags UNC and
    device paths, alternate data streams, reserved device names and segments that end in a dot
    or a space. A different drive is decided later, when the real paths are compared.
    """
    if raw.startswith(("\\\\", "//")):
        return "ruta UNC o de dispositivo"
    _, rest = ntpath.splitdrive(raw)
    if ":" in rest:
        return "flujo alterno de datos"
    for segment in _SEPARATORS.split(rest):
        if not segment or segment in (".", ".."):
            continue
        if segment.endswith((".", " ")):
            return "segmento con punto o espacio final"
        if segment.split(".")[0].upper() in _RESERVED_NAMES:
            return "nombre de dispositivo reservado"
    return None


class WorkspaceArea(AuthorizedArea):
    """A folder on disk inside which file tools may act."""

    def __init__(self, root: str | Path, *, windows: bool | None = None) -> None:
        if not isinstance(root, (str, Path)) or not str(root).strip():
            raise ValueError("El área de trabajo debe ser una carpeta existente.")
        real = Path(os.path.realpath(root))
        if not real.is_dir():
            raise ValueError("El área de trabajo debe ser una carpeta existente.")
        self._root = real
        self._windows = os.name == "nt" if windows is None else windows
        self._root_key = self._key(str(real))

    def _key(self, path: str) -> str:
        """Form used to compare paths: case-insensitive when the Windows rules apply."""
        key = os.path.normcase(path)
        return key.lower() if self._windows else key

    @property
    def root(self) -> Path:
        """Real, absolute path of the authorized folder."""
        return self._root

    def contains(self, path: Path | str) -> bool:
        """Whether the real path of ``path`` (relative to the root if not absolute) is inside.

        Never raises: a value that cannot be resolved or compared is outside the area.
        """
        try:
            if not isinstance(path, (str, Path)):
                return False
            text = str(path)
            if not text.strip() or "\x00" in text:
                return False
            if self._windows and windows_path_problem(text) is not None:
                return False
            real = os.path.realpath(os.path.join(self._root, text))
            real_key = self._key(real)
            return os.path.commonpath([self._root_key, real_key]) == self._root_key
        except Exception:
            return False
