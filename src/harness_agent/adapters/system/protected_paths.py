"""ProtectedPaths: the part of the disk the tools of the agent must not touch (HU-11-01).

It implements the ``AuthorizedArea`` port with the opposite meaning of ``WorkspaceArea``:
``contains(path)`` is ``True`` when the real path of ``path`` (relative paths start at the
workspace, like the file tools) is one of the protected files or inside a protected folder. The
protected paths are resolved at every call, so a folder created or replaced later is covered.

It fails closed: whatever cannot be judged (not text, blank, a NUL character, an unexpected error)
and every Windows-only spelling that could name a protected path in disguise (UNC and device
paths, alternate data streams, reserved names, trailing dots or spaces) counts as protected.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from harness_agent.adapters.system.workspace_area import windows_path_problem
from harness_agent.core import AuthorizedArea


class ProtectedPaths(AuthorizedArea):
    """Protected files and folders, judged on their real paths.

    Args:
        workspace: The folder relative paths start at; it must exist.
        files: Files protected exactly (not their neighbours).
        directories: Folders protected with everything inside them.
        windows: Apply the Windows rules (case-insensitive, disguised names); by default, on
            Windows only.
    """

    def __init__(
        self,
        workspace: str | Path,
        *,
        files: Iterable[Path] = (),
        directories: Iterable[Path] = (),
        windows: bool | None = None,
    ) -> None:
        if not isinstance(workspace, (str, Path)) or not str(workspace).strip():
            raise ValueError("El área de trabajo debe ser una carpeta existente.")
        real = Path(os.path.realpath(workspace))
        if not real.is_dir():
            raise ValueError("El área de trabajo debe ser una carpeta existente.")
        self._root = real
        self._files = tuple(Path(item) for item in files)
        self._directories = tuple(Path(item) for item in directories)
        self._windows = os.name == "nt" if windows is None else windows

    @property
    def root(self) -> Path:
        """Real, absolute path of the workspace that relative paths start at."""
        return self._root

    def _key(self, path: str) -> str:
        key = os.path.normcase(path)
        return key.lower() if self._windows else key

    def contains(self, path: Path | str) -> bool:
        """Whether ``path`` is protected; never raises (what cannot be judged is protected)."""
        try:
            if not isinstance(path, (str, Path)):
                return True
            text = str(path)
            if not text.strip() or "\x00" in text:
                return True
            if self._windows and windows_path_problem(text) is not None:
                return True
            real = self._key(os.path.realpath(os.path.join(self._root, text)))
            if any(real == self._key(os.path.realpath(item)) for item in self._files):
                return True
            for folder in self._directories:
                base = self._key(os.path.realpath(folder))
                if os.path.commonpath([base, real]) == base:
                    return True
            return False
        except Exception:
            return True
