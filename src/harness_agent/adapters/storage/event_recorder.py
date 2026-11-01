"""Subscriber that persists every event of the bus into a session store (HU-03-02).

The recorder is the only place that connects the bus to the store: the core never knows that
events are persisted. It uses the ``EventBus`` and ``SessionStore`` ports only, so it works with
any implementation of both.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Collection
from typing import Any

from harness_agent.core import Event, EventBus, EventType, SessionStore


def attach_event_recorder(
    bus: EventBus,
    store: SessionStore,
    skip: Collection[EventType] = (),
    *,
    redact: Callable[[Any], Any] | None = None,
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
        redact: Cleans a payload (every text inside it) before it is stored (HU-10-02). The event
            the other subscribers receive is not changed: the store gets a copy.
    """
    save = store.save_event
    if redact is not None:
        clean = redact

        def save(event: Event) -> None:
            store.save_event(dataclasses.replace(event, payload=clean(event.payload)))

    for event_type in EventType:
        if event_type not in skip:
            bus.subscribe(event_type, save)
