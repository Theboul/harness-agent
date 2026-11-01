"""Ports of the Pull Request step: the host that pushes and creates, and the person who confirms.

They are ``Protocol`` classes of this package (like ``ChangeSource`` of the review): the core does
not run git or ``gh`` and does not talk to the terminal; an adapter and the CLI do.

Only the standard library and ``harness_agent.core`` are used here.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from harness_agent.core.pullrequest.draft import PullRequestDraft


class PublishError(Exception):
    """An outgoing step failed. The message is fixed text (plus, at most, one cleaned line)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PullRequestHost(Protocol):
    """Pushes the branch and creates the Pull Request. Every method may raise ``PublishError``."""

    async def available(self) -> bool:
        """Whether the tool that creates the Pull Request (the GitHub CLI) can be run."""
        ...

    async def current_branch(self) -> str | None:
        """The checked-out branch, or ``None`` if ``HEAD`` is detached."""
        ...

    async def push(self, branch: str) -> None:
        """Push ``branch`` to the remote (outgoing: only called after a confirmation)."""
        ...

    async def create(self, draft: PullRequestDraft) -> str:
        """Create the Pull Request (outgoing: only called after a confirmation); its link."""
        ...


class PullRequestPrompter(Protocol):
    """Asks the person before each outgoing action, and tells them what happened.

    Each answer covers exactly one action: nothing is remembered. Anything but ``True`` means no.
    """

    async def confirm_push(self, branch: str) -> bool:
        """Ask whether ``branch`` may be pushed."""
        ...

    async def confirm_create(self, draft: PullRequestDraft) -> bool:
        """Show ``draft`` and ask whether the Pull Request may be created."""
        ...

    def show(self, lines: Sequence[str]) -> None:
        """Write lines for the person (the prompter cleans them for the terminal)."""
        ...
