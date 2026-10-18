"""Test doubles: InMemorySessionStore and InMemoryMemoryStore."""

from __future__ import annotations

from datetime import datetime, timezone

from harness_agent.core.events import Event
from harness_agent.core.interfaces.storage import (
    MemoryItem,
    MemoryStore,
    SessionStore,
    SessionSummary,
)


class InMemorySessionStore(SessionStore):
    """In-memory test double for the SessionStore interface."""

    def __init__(self) -> None:
        self.events_by_session: dict[str, list[Event]] = {}
        self.sessions_meta: dict[str, SessionSummary] = {}

    def save_event(self, event: Event) -> None:
        """Append event to in-memory session log."""
        if event.session_id not in self.events_by_session:
            self.events_by_session[event.session_id] = []
            self.sessions_meta[event.session_id] = SessionSummary(
                id=event.session_id,
                status="active",
                created_at=event.timestamp,
            )
        self.events_by_session[event.session_id].append(event)

    def load_session(self, session_id: str) -> list[Event]:
        """Return all events recorded for the given session ID."""
        return list(self.events_by_session.get(session_id, []))

    def list_sessions(self) -> list[SessionSummary]:
        """Return all tracked session summaries."""
        return list(self.sessions_meta.values())


class InMemoryMemoryStore(MemoryStore):
    """In-memory test double for the MemoryStore interface."""

    def __init__(self) -> None:
        self._memories: dict[str, MemoryItem] = {}

    def save(self, key: str, content: str) -> None:
        """Save or overwrite a memory item."""
        now = datetime.now(timezone.utc)
        created_at = self._memories[key].created_at if key in self._memories else now
        self._memories[key] = MemoryItem(
            key=key,
            content=content,
            created_at=created_at,
            updated_at=now,
        )

    def search(self, token_budget: int) -> list[MemoryItem]:
        """Return all stored memories that fit within the token budget."""
        results: list[MemoryItem] = []
        accumulated_chars = 0
        max_chars = token_budget * 4  # heuristic ~4 chars per token
        for item in sorted(
            self._memories.values(),
            key=lambda m: m.updated_at or m.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        ):
            if accumulated_chars + len(item.content) <= max_chars:
                results.append(item)
                accumulated_chars += len(item.content)
        return results

    def delete(self, key: str) -> bool:
        """Delete memory item. Returns True if deleted, False otherwise."""
        if key in self._memories:
            del self._memories[key]
            return True
        return False
