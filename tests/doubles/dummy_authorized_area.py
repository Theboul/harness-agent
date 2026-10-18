"""Test double for the AuthorizedArea contract (lexical check; not a security implementation)."""

from __future__ import annotations

from pathlib import Path

from harness_agent.core.interfaces import AuthorizedArea


class DummyAuthorizedArea(AuthorizedArea):
    """Contract double: resolves paths and checks containment under a fixed root."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    @property
    def root(self) -> Path:
        return self._root

    def contains(self, path: Path | str) -> bool:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self._root / candidate
        return candidate.resolve().is_relative_to(self._root)
