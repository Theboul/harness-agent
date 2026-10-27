"""Subscriber that persists every event of the bus into a session store (HU-03-02).

The recorder is the only place that connects the bus to the store: the core never knows that
events are persisted. It uses the ``EventBus`` and ``SessionStore`` ports only, so it works with
any implementation of both.
"""

from __future__ import annotations

from collections.abc import Collection

from harness_agent.core import EventBus, EventType, SessionStore


def attach_event_recorder(
    bus: EventBus, store: SessionStore, skip: Collection[EventType] = ()
) -> None:
    """Subscribe ``store.save_event`` to every event type of ``bus`` except those in ``skip``.

    Delivery is synchronous, so an event is saved before ``emit`` returns. A failure of the
    store reaches the emitter through the bus (``EventDeliveryError`` on the in-memory bus).
    The session of each event must already exist in the store.

    Args:
        bus: Bus whose events are recorded.
        store: Store that persists them.
        skip: Types that are not recorded because something else already stores them (the
            compaction archive writes ``context_compacted`` in its own transaction, HU-02-03).
    """
    for event_type in EventType:
        if event_type not in skip:
            bus.subscribe(event_type, store.save_event)
