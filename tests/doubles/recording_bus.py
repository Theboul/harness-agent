"""Test double: RecordingEventBus implementing the EventBus abstract contract."""

from __future__ import annotations

from harness_agent.core.events import Event, EventType
from harness_agent.core.interfaces.event_bus import EventBus, EventHandler


class RecordingEventBus(EventBus):
    """In-memory event bus test double that records all published events."""

    def __init__(self) -> None:
        self.emitted_events: list[Event] = []
        self._handlers: dict[EventType, list[EventHandler]] = {}

    def emit(self, event: Event) -> None:
        """Record the event and invoke all handlers registered for this type."""
        self.emitted_events.append(event)
        for handler in self._handlers.get(event.type, []):
            handler(event)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a subscriber handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
