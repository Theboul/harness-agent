"""Abstract EventBus interface for HARNESS.

Sole decoupled channel from the agent core loop towards user interfaces,
logging, and observability systems (RF-1.8).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from harness_agent.core.events import Event, EventType

EventHandler = Callable[[Event], None]


class EventBus(ABC):
    """Abstract Base Class for publish-subscribe event dispatching."""

    @abstractmethod
    def emit(self, event: Event) -> None:
        """Publish an event to all registered listeners.

        Args:
            event: The immutable Event to dispatch.
        """
        ...

    @abstractmethod
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register an event handler for a specific canonical event type.

        Args:
            event_type: The EventType to listen for.
            handler: Callable invoked synchronously whenever a matching event occurs.
        """
        ...
