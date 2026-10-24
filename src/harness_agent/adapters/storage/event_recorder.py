"""Subscriber that persists every event of the bus into a session store (HU-03-02).

The recorder is the only place that connects the bus to the store: the core never knows that
events are persisted. It uses the ``EventBus`` and ``SessionStore`` ports only, so it works with
any implementation of both.
"""

from __future__ import annotations

from harness_agent.core import EventBus, EventType, SessionStore


def attach_event_recorder(bus: EventBus, store: SessionStore) -> None:
    """Subscribe ``store.save_event`` to every event type of ``bus``.

    Delivery is synchronous, so an event is saved before ``emit`` returns. A failure of the
    store reaches the emitter through the bus (``EventDeliveryError`` on the in-memory bus).
    The session of each event must already exist in the store.

    Args:
        bus: Bus whose events are recorded.
        store: Store that persists them.
    """
    for event_type in EventType:
        bus.subscribe(event_type, store.save_event)
