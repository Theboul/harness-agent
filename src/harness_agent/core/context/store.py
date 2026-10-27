"""What the compactor needs from the place where the events are kept (HU-02-03).

A small protocol owned by ``core/context/``: the ports of ``core/interfaces/`` do not change. The
SQLite adapter implements it; see ``specs/030-automatic-context-compaction/contracts/
store_protocol.md`` for the rules it must follow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from harness_agent.core.events import Event


@dataclass(frozen=True)
class MessageEvent:
    """An event that stands for a message of the conversation.

    Attributes:
        seq: Position of the event in its session.
        kind: ``user``, ``assistant`` or ``tool``.
        covered: Whether an earlier compaction already covers it.
    """

    seq: int
    kind: str
    covered: bool


@dataclass(frozen=True)
class CompactionCommit:
    """What is saved, in one step, when a part of the history is summarised.

    Attributes:
        session_id: The session.
        protected_seq: The event of the initial request: it is never covered.
        through_seq: The last message event of the summarised part (inclusive).
        summary: The clean text, with the credentials already hidden.
        summary_id: Identifier of the new summary.
        event_id: Identifier of the ``context_compacted`` event to store.
    """

    session_id: str
    protected_seq: int
    through_seq: int
    summary: str
    summary_id: str
    event_id: str


@dataclass(frozen=True)
class CompactionReceipt:
    """What was covered: the range and the number of events, and the event that says so."""

    summary_id: str
    desde: int
    hasta: int
    eventos: int
    event: Event


class CompactionStore(Protocol):
    """The events of a session, as the compactor reads and covers them."""

    def message_events(self, session_id: str) -> list[MessageEvent]:
        """The message events of the session, in order, with whether each one is covered."""
        ...

    def commit_compaction(self, commit: CompactionCommit) -> CompactionReceipt | None:
        """Save the summary, cover the events and store ``context_compacted``, all or nothing.

        Returns ``None``, having written nothing, if there is no event left to cover.
        """
        ...
