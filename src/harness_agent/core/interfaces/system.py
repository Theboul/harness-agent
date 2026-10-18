"""Operating system, workspace containment, and task criteria interfaces for HARNESS.

Encapsulates subshell execution (RF-1.2, V-08), workspace boundary containment
to prevent directory escapes (V-17, A-01, A-02), and SQLite criteria management
as single source of truth (V-15, RF-11.1).
All methods are synchronous.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ShellResult:
    """Outcome of an operating system command execution.

    Attributes:
        exit_code: Process return code (0 indicates success).
        output: Captured standard output and standard error text.
        timed_out: True if the process exceeded its timeout limit and was killed.
    """

    exit_code: int
    output: str
    timed_out: bool = False


@dataclass(frozen=True)
class TaskCriteriaItem:
    """Individual verification criterion for an active task ticket.

    Attributes:
        id: Unique identifier of the criterion.
        description: Functional requirement statement.
        passes: Boolean verification flag (starts False, only harness may set True).
        evidence: Verification output or test evidence confirming satisfaction.
        command: Optional shell command used to verify the criterion objectively.
    """

    id: str
    description: str
    passes: bool = False
    evidence: str | None = None
    command: str | None = None


class Shell(ABC):
    """Abstract Base Class for OS subshell command execution.

    Single gateway for all external processes, git commands, and lint/test runners.
    """

    @property
    @abstractmethod
    def interpreter_name(self) -> str:
        """Name of the underlying shell ('powershell' on Windows, 'bash' on Linux)."""
        ...

    @abstractmethod
    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        """Execute a shell command with an enforced maximum timeout.

        Args:
            command: Command line string to execute.
            timeout_seconds: Maximum duration before terminating the process.

        Returns:
            ShellResult with exit code, captured output, and timeout status.
        """
        ...


class AuthorizedArea(ABC):
    """Abstract Base Class for workspace containment and path validation.

    Prevents directory escapes, symlink traversal attacks, and UNC path escapes.
    """

    @property
    @abstractmethod
    def root(self) -> Path:
        """Canonical, normalized base workspace directory."""
        ...

    @abstractmethod
    def contains(self, path: Path | str) -> bool:
        """Resolve path and verify that it strictly resides within authorized root.

        Resolves relative components ('..'), symlinks, drive letters, and casing.

        Args:
            path: Destination file or directory path to check.

        Returns:
            True if path resolves within root; False otherwise.
        """
        ...


class TaskCriteria(ABC):
    """Abstract Base Class for task criteria management in SQLite.

    SQLite is the definitive source of truth; read-only JSON is exported for tooling.
    """

    @abstractmethod
    def load_criteria(self, session_id: str) -> list[TaskCriteriaItem]:
        """Load all acceptance criteria associated with the given session."""
        ...

    @abstractmethod
    def get_pending(self, session_id: str) -> list[TaskCriteriaItem]:
        """Retrieve all criteria whose passes status is currently False."""
        ...

    @abstractmethod
    def mark_passes(self, criteria_id: str, evidence: str) -> None:
        """Mark a criterion as passed with supporting execution evidence.

        Args:
            criteria_id: Identifier of the criterion to satisfy.
            evidence: Objective proof or test output.
        """
        ...

    @abstractmethod
    def export_readonly_copy(self, session_id: str, destination: Path) -> None:
        """Export a read-only JSON copy of the criteria for inspection."""
        ...
