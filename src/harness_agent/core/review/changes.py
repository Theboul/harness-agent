"""The change of the work tree as the repository sees it, and the port to read and commit it.

``ChangeSet`` is built from the real ``git diff`` (HU-11-05, rule 2): the summary never comes from
what the agent says it did. ``ChangeSource`` is a ``Protocol`` of the review package (like the
destinations of the progress file): the core does not run git, an adapter does.

Only the standard library and ``harness_agent.core`` are used here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ChangeStatus(str, Enum):
    """What happened to one file."""

    NEW = "nuevo"
    MODIFIED = "modificado"
    DELETED = "eliminado"
    OTHER = "otro"


@dataclass(frozen=True)
class FileChange:
    """One touched file. ``added``/``removed`` are ``None`` for a binary file."""

    path: str
    status: ChangeStatus
    added: int | None
    removed: int | None


@dataclass(frozen=True)
class ChangeSet:
    """The files touched and the patch of the change.

    Attributes:
        files: The touched files, in the order git lists them.
        patch: The unified diff (possibly cut: see ``truncated``).
        truncated: The patch is longer than the review accepts; the summary is still complete.
    """

    files: tuple[FileChange, ...] = ()
    patch: str = ""
    truncated: bool = False

    @property
    def is_empty(self) -> bool:
        return not self.files

    @property
    def total_added(self) -> int:
        return sum(change.added or 0 for change in self.files)

    @property
    def total_removed(self) -> int:
        return sum(change.removed or 0 for change in self.files)


class ChangeSourceError(Exception):
    """The change could not be read or committed. The message is fixed text, never git's own."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ChangeSource(Protocol):
    """Reads the pending change and commits it once a person approved it."""

    async def snapshot(self) -> ChangeSet:
        """The change of the work tree against ``HEAD``; raises ``ChangeSourceError``."""
        ...

    async def commit(self, message: str) -> str:
        """Commit everything that ``snapshot`` showed; return the short id of the commit."""
        ...
