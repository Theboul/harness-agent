"""In-memory implementation of the ``EventBus`` port (HU-01-05).

The bus is the only channel from the core towards the interfaces (RF-1.8): the core emits typed
events and never prints; a terminal, a web interface or the session store subscribe as handlers.
It only needs the standard library, so it lives in the core (as ``InMemoryToolRegistry`` does).

Behaviour (the full contract is ``specs/011-event-bus/contracts/event_bus_contract.md``):

* Delivery is synchronous: ``emit`` calls every handler of the exact type of the event, in the
  order in which they were subscribed, before returning. Every handler receives the same
  immutable ``Event``. A type without subscribers is not an error.
* The same handler may be subscribed several times: it is called once per subscription.
* The handlers of a type are fixed when an emission starts: a handler subscribed while an event is
  being delivered only receives later events.
* A handler may emit another event while it receives one. That nested delivery is immediate and
  synchronous (there is no queue): it finishes before the next handler of the outer emission runs.
* A handler that raises an ordinary exception does not stop the delivery: the remaining handlers
  still receive the event and, at the end, ``emit`` raises an ``EventDeliveryError`` with every
  exception, in delivery order. Errors are never swallowed. An exception that is not an
  ``Exception`` (cancellation, keyboard interrupt) propagates at once, without grouping, and the
  ordinary failures that already happened are noted in it with ``add_note``.
* ``subscribe`` and ``emit`` validate their arguments strictly and raise ``TypeError`` with a
  message in Spanish; the bus has no way to unsubscribe (the port has none).
* The bus is meant for the single-threaded loop of the agent: it is not safe between threads.
"""

from __future__ import annotations

from collections.abc import Sequence

from harness_agent.core.events import Event, EventType
from harness_agent.core.interfaces.event_bus import EventBus, EventHandler


class EventDeliveryError(ExceptionGroup[Exception]):
    """Every ordinary exception raised by the handlers of one emission, in delivery order.

    Raised by ``emit`` after the event reached all the handlers. The message never reproduces the
    payload of the event (it can hold sensitive data): only the event type and the number of
    failures. It is an ``Exception``, so the loop and the session store treat it as a failure of
    the emission (Q4); ``derive`` keeps the type and the message in ``split`` and ``subgroup``.
    """

    # typeshed types ``derive`` as an overload for any exception type; this group only holds
    # ordinary exceptions, so the override is narrower on purpose.
    def derive(self, excs: Sequence[Exception], /) -> EventDeliveryError:  # type: ignore[override]
        return EventDeliveryError(self.message, excs)


def _delivery_message(count: int, event_type: EventType) -> str:
    if count == 1:
        return f"Falló 1 manejador al entregar el evento '{event_type.value}'."
    return f"Fallaron {count} manejadores al entregar el evento '{event_type.value}'."


def _previous_failures_note(failures: Sequence[Exception], event_type: EventType) -> str:
    """The note of a propagated non-ordinary exception: types and number, never the event."""
    names = ", ".join(type(failure).__name__ for failure in failures)
    if len(failures) == 1:
        subject = "Antes falló 1 manejador"
    else:
        subject = f"Antes fallaron {len(failures)} manejadores"
    return (
        f"{subject} ({names}) al entregar el evento '{event_type.value}'; "
        "los manejadores restantes no lo recibieron."
    )


class InMemoryEventBus(EventBus):
    """Synchronous publish-subscribe bus that keeps its subscriptions in memory."""

    def __init__(self) -> None:
        # One immutable tuple per type: a subscription replaces the tuple, so the tuple read at
        # the start of an emission never changes while the event is being delivered.
        self._handlers: dict[EventType, tuple[EventHandler, ...]] = {}

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register ``handler`` for ``event_type``; one more delivery per call, even if repeated."""
        if not isinstance(event_type, EventType):
            raise TypeError(
                "El tipo de evento debe ser un EventType del catálogo, "
                f"no '{type(event_type).__name__}'."
            )
        if not callable(handler):
            raise TypeError(f"El manejador debe ser invocable, no '{type(handler).__name__}'.")
        self._handlers[event_type] = (*self._handlers.get(event_type, ()), handler)

    def emit(self, event: Event) -> None:
        """Deliver ``event`` to the handlers of its type, in subscription order."""
        if not isinstance(event, Event):
            raise TypeError(f"Solo se pueden emitir objetos Event, no '{type(event).__name__}'.")
        failures: list[Exception] = []
        for handler in self._handlers.get(event.type, ()):
            try:
                handler(event)
            except Exception as error:
                failures.append(error)
            except BaseException as error:
                # Cancellation or keyboard interrupt: propagate at once, without grouping. The
                # ordinary failures that already happened are noted (types and number only).
                if failures:
                    error.add_note(_previous_failures_note(failures, event.type))
                raise
        if failures:
            raise EventDeliveryError(_delivery_message(len(failures), event.type), failures)
