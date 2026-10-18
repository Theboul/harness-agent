"""Abstract storage interfaces for session history and persistent memory in HARNESS.

Guarantees transactional event-by-event persistence in SQLite (RF-3.1, RF-3.2, V-03)
and long-term memory across sessions decoupled from context window compaction (RF-4.1, V-05).
All methods are synchronous.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from harness_agent.core.events import Event


@dataclass(frozen=True)
class SessionSummary:
    """Summary metadata for an existing agent session.

    Attributes:
        id: Unique session identifier.
        status: Current lifecycle state (e.g. 'active', 'completed', 'interrupted').
        created_at: UTC timestamp when the session was initialized.
        model: Optional model identifier configured for the session.
        goal: Optional primary goal or task statement for the session.
    """

    id: str
    status: str
    created_at: datetime
    model: str | None = None
    goal: str | None = None


@dataclass(frozen=True)
class MemoryItem:
    """Persistent memory entry retained across session boundaries.

    Attributes:
        key: Unique topic key or identifier.
        content: Textual knowledge or preference content.
        created_at: Creation timestamp.
        updated_at: Last amendment timestamp.
    """

    key: str
    content: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SessionStore(ABC):
    """Abstract Base Class for SQLite session history persistence.

    All writes are atomic and persist each event immediately as it occurs.
    """

    @abstractmethod
    def save_event(self, event: Event) -> None:
        """Persist a single event atomically to SQLite storage.

        Args:
            event: The Event instance to append to the session log.
        """
        ...

    @abstractmethod
    def load_session(self, session_id: str) -> list[Event]:
        """Load the ordered sequence of events associated with a session.

        Args:
            session_id: Unique identifier of the session to retrieve.

        Returns:
            Chronologically ordered list of Event instances.
        """
        ...

    @abstractmethod
    def list_sessions(self) -> list[SessionSummary]:
        """List metadata summaries for all recorded sessions."""
        ...


class MemoryStore(ABC):
    """Abstract Base Class for persistent agent memory storage."""

    @abstractmethod
    def save(self, key: str, content: str) -> None:
        """Save or update a memory record by key.

        Args:
            key: Stable unique identifier for the memory topic.
            content: Information to persist.
        """
        ...

    @abstractmethod
    def search(self, token_budget: int) -> list[MemoryItem]:
        """Query relevant memories fitting within the specified token budget.

        Args:
            token_budget: Maximum tokens allocated for retrieved memories.

        Returns:
            List of prioritized MemoryItem instances.
        """
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a memory record by key. Returns True if deleted, False otherwise."""
        ...
