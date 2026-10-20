"""Single contract test suite for the event bus (HU-01-05 / T002, T004).

The same clauses run against the test double ``RecordingEventBus`` and against the real
``InMemoryEventBus``. The clause numbers are those of ``specs/011-event-bus/contracts/
event_bus_contract.md`` (section 5), which says to whom each clause applies:

====== =========================================================== ====== ======
Clause Description                                                  Double Real
====== =========================================================== ====== ======
C-1    the subscriber of the type gets the same event, once          yes    yes
C-2    several subscribers receive in subscription order             yes    yes
C-3    only the subscribers of the exact type receive                yes    yes
C-4    a type without subscribers is not an error; ``emit`` is None  yes    yes
C-5    the same handler subscribed N times is delivered N times      yes    yes
C-6    the 17 event types are delivered                              yes    yes
C-7    a nested delivery is immediate and finishes before the next   yes    yes
C-8    event types are not mixed up in a nested delivery             yes    yes
C-9    a handler subscribed during a delivery gets later events only no     yes
C-10   a failing handler does not stop the others (error group)      no     yes
C-11   a non-ordinary exception propagates at once, with a note      no     yes
C-12   after a failure the bus keeps working                         no     yes
C-13   ``subscribe`` rejects bad types and handlers (unit tests)     no     yes
C-14   ``emit`` rejects what is not an ``Event`` (unit tests)        no     yes
C-15   no error message reproduces the payload of the event          no     yes
====== =========================================================== ====== ======

The clauses that are only for the real bus are properties of the implementation, not defects of
the double, which is not modified: ``TestClausulasComunes`` runs against both and
``TestClausulasDelBusReal`` only against the real bus.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from harness_agent.core.events import Event, EventType
from harness_agent.core.in_memory_event_bus import EventDeliveryError, InMemoryEventBus
from harness_agent.core.interfaces.event_bus import EventBus, EventHandler
from tests.doubles import RecordingEventBus


def recording_bus() -> EventBus:
    return RecordingEventBus()


def real_bus() -> EventBus:
    return InMemoryEventBus()


@pytest.fixture(params=[recording_bus, real_bus], ids=["RecordingEventBus", "InMemoryEventBus"])
def bus(request: pytest.FixtureRequest) -> EventBus:
    factory: Callable[[], EventBus] = request.param
    return factory()


def appender(target: list[str], name: str) -> EventHandler:
    """A handler that appends ``name`` to ``target`` each time it receives an event."""

    def handler(_event: Event) -> None:
        target.append(name)

    return handler


def make_event(event_type: EventType = EventType.USER_MESSAGE, **payload: object) -> Event:
    return Event.create("session-1", event_type, dict(payload))


class TestClausulasComunes:
    def test_c1_the_subscriber_of_the_type_gets_the_same_event_once(self, bus: EventBus) -> None:
        received: list[Event] = []
        bus.subscribe(EventType.USER_MESSAGE, received.append)
        event = make_event()

        bus.emit(event)

        assert len(received) == 1
        assert received[0] is event

    def test_c2_several_subscribers_receive_in_subscription_order(self, bus: EventBus) -> None:
        order: list[str] = []
        for name in ("first", "second", "third"):
            bus.subscribe(EventType.USER_MESSAGE, appender(order, name))

        bus.emit(make_event())

        assert order == ["first", "second", "third"]

    def test_c3_only_the_subscribers_of_the_exact_type_receive(self, bus: EventBus) -> None:
        users: list[Event] = []
        assistants: list[Event] = []
        bus.subscribe(EventType.USER_MESSAGE, users.append)
        bus.subscribe(EventType.ASSISTANT_MESSAGE, assistants.append)
        event = make_event(EventType.USER_MESSAGE)

        bus.emit(event)

        assert users == [event]
        assert assistants == []

    def test_c4_a_type_without_subscribers_is_not_an_error(self, bus: EventBus) -> None:
        emit: Callable[[Event], object] = bus.emit

        assert emit(make_event(EventType.LIMIT_REACHED)) is None

    def test_c5_the_same_handler_subscribed_n_times_is_delivered_n_times(
        self, bus: EventBus
    ) -> None:
        received: list[Event] = []
        for _ in range(3):
            bus.subscribe(EventType.TOOL_FINISHED, received.append)
        event = make_event(EventType.TOOL_FINISHED)

        bus.emit(event)

        assert received == [event, event, event]

    def test_c6_there_are_17_event_types(self) -> None:
        assert len(list(EventType)) == 17

    @pytest.mark.parametrize("event_type", list(EventType), ids=lambda t: t.value)
    def test_c6_every_event_type_is_delivered(self, bus: EventBus, event_type: EventType) -> None:
        received: list[Event] = []
        bus.subscribe(event_type, received.append)
        event = make_event(event_type)

        bus.emit(event)

        assert received == [event]

    def test_c7_a_nested_delivery_is_immediate_and_finishes_before_the_next_handler(
        self, bus: EventBus
    ) -> None:
        order: list[str] = []

        def outer(_event: Event) -> None:
            order.append("outer-start")
            bus.emit(make_event(EventType.ASSISTANT_MESSAGE))
            order.append("outer-end")

        bus.subscribe(EventType.USER_MESSAGE, outer)
        bus.subscribe(EventType.USER_MESSAGE, lambda _event: order.append("second"))
        bus.subscribe(EventType.ASSISTANT_MESSAGE, lambda _event: order.append("nested"))

        bus.emit(make_event(EventType.USER_MESSAGE))

        assert order == ["outer-start", "nested", "outer-end", "second"]

    def test_c8_event_types_are_not_mixed_up_in_a_nested_delivery(self, bus: EventBus) -> None:
        seen: dict[str, list[EventType]] = {"user": [], "assistant": []}

        def outer(event: Event) -> None:
            seen["user"].append(event.type)
            bus.emit(make_event(EventType.ASSISTANT_MESSAGE))

        bus.subscribe(EventType.USER_MESSAGE, outer)
        bus.subscribe(EventType.ASSISTANT_MESSAGE, lambda e: seen["assistant"].append(e.type))

        bus.emit(make_event(EventType.USER_MESSAGE))

        assert seen == {
            "user": [EventType.USER_MESSAGE],
            "assistant": [EventType.ASSISTANT_MESSAGE],
        }


SENTINEL = "VALOR-DE-PRUEBA-123"


@pytest.fixture
def real() -> InMemoryEventBus:
    return InMemoryEventBus()


def failing_and_healthy_handlers(
    bus: InMemoryEventBus, size: int, failing: set[int]
) -> tuple[list[int], dict[int, Exception]]:
    """Subscribe ``size`` handlers; the indexes in ``failing`` raise their own ``ValueError``."""
    calls: list[int] = []
    errors: dict[int, Exception] = {}

    def make(index: int) -> EventHandler:
        def handler(_event: Event) -> None:
            calls.append(index)
            if index in failing:
                raise errors[index]

        return handler

    for index in range(size):
        if index in failing:
            errors[index] = ValueError(f"fallo {index}")
        bus.subscribe(EventType.TOOL_FINISHED, make(index))
    return calls, errors


class TestClausulasDelBusReal:
    @pytest.mark.parametrize(
        ("size", "failing"),
        [(1, set()), (1, {0}), (2, set()), (3, {1}), (3, {0, 2}), (4, {0, 1, 2, 3}), (5, {4})],
    )
    def test_c10_a_failing_handler_does_not_stop_the_others_and_every_error_is_reported(
        self, real: InMemoryEventBus, size: int, failing: set[int]
    ) -> None:
        calls, errors = failing_and_healthy_handlers(real, size, failing)
        event = make_event(EventType.TOOL_FINISHED)

        if not failing:
            real.emit(event)
        else:
            with pytest.raises(EventDeliveryError) as raised:
                real.emit(event)
            expected = [errors[index] for index in sorted(failing)]
            assert len(raised.value.exceptions) == len(failing)
            for got, want in zip(raised.value.exceptions, expected, strict=True):
                assert got is want  # the original instances, in the order of delivery

        assert calls == list(range(size))  # every handler once, in order

    def test_c11_a_non_ordinary_exception_propagates_at_once_without_grouping(
        self, real: InMemoryEventBus
    ) -> None:
        calls: list[str] = []
        interruption = KeyboardInterrupt()

        def interrupt(_event: Event) -> None:
            calls.append("interrupt")
            raise interruption

        real.subscribe(EventType.TOOL_FINISHED, lambda _event: calls.append("before"))
        real.subscribe(EventType.TOOL_FINISHED, interrupt)
        real.subscribe(EventType.TOOL_FINISHED, lambda _event: calls.append("after"))

        with pytest.raises(KeyboardInterrupt) as raised:
            real.emit(make_event(EventType.TOOL_FINISHED))

        assert raised.value is interruption
        assert calls == ["before", "interrupt"]
        assert not hasattr(raised.value, "__notes__")

    @pytest.mark.parametrize("exception_type", [KeyboardInterrupt, asyncio.CancelledError])
    def test_c11_the_previous_ordinary_failures_are_noted_in_the_propagated_exception(
        self, real: InMemoryEventBus, exception_type: type[BaseException]
    ) -> None:
        def fail_value(_event: Event) -> None:
            raise ValueError(SENTINEL)

        def fail_key(_event: Event) -> None:
            raise KeyError(SENTINEL)

        def stop(_event: Event) -> None:
            raise exception_type()

        for handler in (fail_value, fail_key, stop):
            real.subscribe(EventType.TOOL_FINISHED, handler)

        with pytest.raises(exception_type) as raised:
            real.emit(make_event(EventType.TOOL_FINISHED, content=SENTINEL))

        assert raised.value.__notes__ == [
            "Antes fallaron 2 manejadores (ValueError, KeyError) al entregar el evento "
            "'tool_finished'; los manejadores restantes no lo recibieron."
        ]
        assert SENTINEL not in " ".join(raised.value.__notes__)

    def test_c11_a_single_previous_failure_is_noted_in_the_singular(
        self, real: InMemoryEventBus
    ) -> None:
        def fail(_event: Event) -> None:
            raise ValueError("fallo")

        def stop(_event: Event) -> None:
            raise KeyboardInterrupt

        real.subscribe(EventType.USER_MESSAGE, fail)
        real.subscribe(EventType.USER_MESSAGE, stop)

        with pytest.raises(KeyboardInterrupt) as raised:
            real.emit(make_event(EventType.USER_MESSAGE))

        assert raised.value.__notes__ == [
            "Antes falló 1 manejador (ValueError) al entregar el evento 'user_message'; "
            "los manejadores restantes no lo recibieron."
        ]

    def test_c12_after_a_failure_the_bus_keeps_working_and_the_subscriptions_stay(
        self, real: InMemoryEventBus
    ) -> None:
        received: list[Event] = []
        attempts = [0]

        def flaky(_event: Event) -> None:
            attempts[0] += 1
            if attempts[0] == 1:
                raise ValueError("solo la primera vez")

        real.subscribe(EventType.USER_MESSAGE, flaky)
        real.subscribe(EventType.USER_MESSAGE, received.append)
        first, second = make_event(), make_event()

        with pytest.raises(EventDeliveryError):
            real.emit(first)
        real.emit(second)  # no error: the failing handler works now

        assert received == [first, second]
        assert attempts[0] == 2
        real.subscribe(EventType.USER_MESSAGE, received.append)
        real.emit(make_event())
        assert len(received) == 4

    def test_c15_no_error_text_reproduces_the_payload_of_the_event(
        self, real: InMemoryEventBus
    ) -> None:
        def fail(_event: Event) -> None:
            raise ValueError("fallo")

        real.subscribe(EventType.TOOL_FINISHED, fail)
        real.subscribe(EventType.TOOL_FINISHED, fail)

        with pytest.raises(EventDeliveryError) as raised:
            real.emit(make_event(EventType.TOOL_FINISHED, content=SENTINEL))

        assert SENTINEL not in str(raised.value)
        assert SENTINEL not in repr(raised.value)
        assert SENTINEL not in raised.value.message
        assert not hasattr(raised.value, "__notes__")
