"""Abstract ContextManager interface for HARNESS.

Controls context window assembly (stable prefix, memories, summary, recent events)
and token compaction triggers without altering SQLite event history (RF-2.1, RF-2.3, V-04).
All methods are synchronous.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from harness_agent.core.entities import Message


@dataclass(frozen=True)
class CompactResult:
    """Summary of a context window compaction execution.

    Attributes:
        session_id: The session whose context was compacted.
        events_compacted: Count of historical events summarized and archived.
        summary: Resulting textual summary representing the compacted window.
    """

    session_id: str
    events_compacted: int
    summary: str


class ContextManager(ABC):
    """Abstract Base Class for agent context assembly and history compaction."""

    @abstractmethod
    def assemble(self, session_id: str, model_id: str) -> list[Message]:
        """Assemble the complete context window for the upcoming model turn.

        Builds the message list containing: stable prefix (system instructions,
        tool declarations, essential context) + memories + active summary + recent events.

        Args:
            session_id: Active session identifier.
            model_id: Target model identifier to align token thresholds.

        Returns:
            Ordered list of Message instances to feed into Provider.complete.
        """
        ...

    @abstractmethod
    def compact(self, session_id: str) -> CompactResult:
        """Trigger compaction of older events into an updated summary.

        Preserves essential context keys and keeps SQLite event history intact.

        Args:
            session_id: Active session identifier.

        Returns:
            CompactResult describing the compaction output.
        """
        ...
