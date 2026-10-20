"""Unit tests of the real in-memory event bus (HU-01-05 / T002 and T004).

The shared clauses live in ``tests/contracts/test_event_bus_contract.py``; this module holds what
is specific to ``InMemoryEventBus``: the copy of the handlers when a delivery starts (C-9), the
strict validation of ``subscribe`` and ``emit`` (C-13, C-14), the export from ``harness_agent.core``
and a smoke test of the cost of a delivery.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

import harness_agent.core as core
from harness_agent.core import in_memory_event_bus
from harness_agent.core.events import Event, EventType
from harness_agent.core.in_memory_event_bus import EventDeliveryError, InMemoryEventBus
from harness_agent.core.interfaces.event_bus import EventBus

SENTINEL = "VALOR-DE-PRUEBA-123"


def make_event(event_type: EventType = EventType.USER_MESSAGE, **payload: object) -> Event:
    return Event.create("session-1", event_type, dict(payload))


class TestInterfazYExportacion:
    def test_the_bus_implements_the_port(self) -> None:
        assert issubclass(InMemoryEventBus, EventBus)
        assert isinstance(InMemoryEventBus(), EventBus)

    def test_the_bus_is_exported_from_core(self) -> None:
        assert core.InMemoryEventBus is in_memory_event_bus.InMemoryEventBus
        assert core.__all__.count("InMemoryEventBus") == 1

    def test_the_delivery_error_is_exported_from_core(self) -> None:
        assert core.EventDeliveryError is in_memory_event_bus.EventDeliveryError
        assert core.__all__.count("EventDeliveryError") == 1

    def test_a_new_bus_has_no_subscribers_and_two_buses_are_independent(self) -> None:
        first, second = InMemoryEventBus(), InMemoryEventBus()
        received: list[Event] = []
        first.subscribe(EventType.USER_MESSAGE, received.append)

        second.emit(make_event())

        assert received == []

    def test_a_value_returned_by_a_handler_is_ignored(self) -> None:
        bus = InMemoryEventBus()
        calls: list[Event] = []

        def handler(event: Event) -> Any:
            calls.append(event)
            return 5

        bus.subscribe(EventType.USER_MESSAGE, handler)
        bus.emit(make_event())

        assert len(calls) == 1


class TestCopiaDeManejadores:
    def test_c9_a_handler_subscribed_during_a_delivery_gets_only_later_events(self) -> None:
        bus = InMemoryEventBus()
        late: list[Event] = []

        def first(_event: Event) -> None:
            bus.subscribe(EventType.USER_MESSAGE, late.append)

        bus.subscribe(EventType.USER_MESSAGE, first)
        first_event, second_event = make_event(), make_event()

        bus.emit(first_event)
        assert late == []

        bus.emit(second_event)
        assert late == [second_event]

    def test_a_handler_that_subscribes_itself_does_not_loop_forever(self) -> None:
        bus = InMemoryEventBus()
        calls: list[int] = []

        def handler(_event: Event) -> None:
            calls.append(len(calls))
            bus.subscribe(EventType.USER_MESSAGE, handler)

        bus.subscribe(EventType.USER_MESSAGE, handler)

        bus.emit(make_event())
        bus.emit(make_event())

        assert calls == [0, 1, 2]


class TestValidacionDeSubscribe:
    @pytest.mark.parametrize(
        ("bad_type", "name"),
        [("user_message", "str"), (None, "NoneType"), (5, "int"), (object(), "object")],
    )
    def test_c13_a_type_that_is_not_an_event_type_is_rejected(
        self, bad_type: Any, name: str
    ) -> None:
        bus = InMemoryEventBus()

        with pytest.raises(TypeError) as raised:
            bus.subscribe(bad_type, lambda _event: None)

        assert str(raised.value) == (
            f"El tipo de evento debe ser un EventType del catálogo, no '{name}'."
        )

    @pytest.mark.parametrize(
        ("bad_handler", "name"), [(None, "NoneType"), (5, "int"), (SENTINEL, "str")]
    )
    def test_c13_a_handler_that_is_not_callable_is_rejected(
        self, bad_handler: Any, name: str
    ) -> None:
        bus = InMemoryEventBus()

        with pytest.raises(TypeError) as raised:
            bus.subscribe(EventType.USER_MESSAGE, bad_handler)

        assert str(raised.value) == f"El manejador debe ser invocable, no '{name}'."
        assert SENTINEL not in str(raised.value)

    def test_c13_the_type_is_checked_before_the_handler(self) -> None:
        bus = InMemoryEventBus()

        with pytest.raises(TypeError, match="tipo de evento"):
            bus.subscribe("user_message", None)  # type: ignore[arg-type]

    def test_c13_a_rejected_subscription_registers_nothing(self) -> None:
        bus = InMemoryEventBus()
        bad_handler: Any = SENTINEL

        with pytest.raises(TypeError):
            bus.subscribe(EventType.USER_MESSAGE, bad_handler)
        with pytest.raises(TypeError):
            bus.subscribe("user_message", lambda _event: None)  # type: ignore[arg-type]

        bus.emit(make_event())  # a registered non-callable would raise here


class TestValidacionDeEmit:
    @pytest.mark.parametrize(
        ("bad_event", "name"),
        [
            ({"type": "user_message", "payload": SENTINEL}, "dict"),
            (SENTINEL, "str"),
            (None, "NoneType"),
        ],
    )
    def test_c14_what_is_not_an_event_is_rejected(self, bad_event: Any, name: str) -> None:
        bus = InMemoryEventBus()

        with pytest.raises(TypeError) as raised:
            bus.emit(bad_event)

        assert str(raised.value) == f"Solo se pueden emitir objetos Event, no '{name}'."
        assert SENTINEL not in str(raised.value)

    def test_c14_nothing_is_delivered_when_the_event_is_rejected(self) -> None:
        bus = InMemoryEventBus()
        received: list[Event] = []
        bus.subscribe(EventType.USER_MESSAGE, received.append)

        with pytest.raises(TypeError):
            bus.emit({"type": EventType.USER_MESSAGE})  # type: ignore[arg-type]

        assert received == []


def raiser(error: BaseException) -> Any:
    def handler(_event: Event) -> None:
        raise error

    return handler


class TestEventDeliveryError:
    def test_it_is_an_exception_group_and_an_ordinary_exception(self) -> None:
        assert issubclass(EventDeliveryError, ExceptionGroup)
        assert issubclass(EventDeliveryError, Exception)

    def test_the_message_of_one_failure_is_in_the_singular(self) -> None:
        bus = InMemoryEventBus()
        bus.subscribe(EventType.USER_MESSAGE, raiser(ValueError("fallo")))

        with pytest.raises(EventDeliveryError) as raised:
            bus.emit(make_event())

        assert raised.value.message == "Falló 1 manejador al entregar el evento 'user_message'."

    def test_the_message_of_several_failures_is_in_the_plural(self) -> None:
        bus = InMemoryEventBus()
        for _ in range(2):
            bus.subscribe(EventType.TOOL_FINISHED, raiser(ValueError("fallo")))

        with pytest.raises(EventDeliveryError) as raised:
            bus.emit(make_event(EventType.TOOL_FINISHED))

        assert raised.value.message == (
            "Fallaron 2 manejadores al entregar el evento 'tool_finished'."
        )

    def test_split_and_subgroup_keep_the_type_and_the_message(self) -> None:
        bus = InMemoryEventBus()
        bus.subscribe(EventType.USER_MESSAGE, raiser(ValueError("uno")))
        bus.subscribe(EventType.USER_MESSAGE, raiser(KeyError("dos")))

        with pytest.raises(EventDeliveryError) as raised:
            bus.emit(make_event())

        parts: tuple[object, object] = raised.value.split(ValueError)
        matching, rest = parts
        assert isinstance(matching, EventDeliveryError)
        assert isinstance(rest, EventDeliveryError)
        assert matching.message == rest.message == raised.value.message
        assert [type(e) for e in matching.exceptions] == [ValueError]
        subgroup: object = raised.value.subgroup(KeyError)
        assert isinstance(subgroup, EventDeliveryError)

    def test_except_star_catches_the_original_exceptions(self) -> None:
        bus = InMemoryEventBus()
        bus.subscribe(EventType.USER_MESSAGE, raiser(ValueError("uno")))
        bus.subscribe(EventType.USER_MESSAGE, raiser(KeyError("dos")))
        caught: list[str] = []

        try:
            bus.emit(make_event())
        except* ValueError as group:
            caught.append(f"value:{len(group.exceptions)}")
        except* KeyError as group:
            caught.append(f"key:{len(group.exceptions)}")

        assert caught == ["value:1", "key:1"]

    def test_a_failure_in_a_nested_delivery_counts_as_a_failure_of_the_handler_that_emitted(
        self,
    ) -> None:
        bus = InMemoryEventBus()
        bus.subscribe(EventType.TOOL_FINISHED, raiser(ValueError("interno")))
        bus.subscribe(
            EventType.USER_MESSAGE, lambda _event: bus.emit(make_event(EventType.TOOL_FINISHED))
        )

        with pytest.raises(EventDeliveryError) as raised:
            bus.emit(make_event())

        (outer,) = raised.value.exceptions
        assert isinstance(outer, EventDeliveryError)
        assert outer.message == "Falló 1 manejador al entregar el evento 'tool_finished'."
        assert raised.value.message == "Falló 1 manejador al entregar el evento 'user_message'."

    def test_a_handler_that_catches_the_nested_failure_does_not_fail(self) -> None:
        bus = InMemoryEventBus()
        bus.subscribe(EventType.TOOL_FINISHED, raiser(ValueError("interno")))

        def outer(_event: Event) -> None:
            with pytest.raises(EventDeliveryError):
                bus.emit(make_event(EventType.TOOL_FINISHED))

        bus.subscribe(EventType.USER_MESSAGE, outer)

        bus.emit(make_event())  # no error


class TestRendimiento:
    def test_smoke_a_delivery_to_ten_subscribers_costs_less_than_a_millisecond(self) -> None:
        bus = InMemoryEventBus()
        counter = [0]

        def handler(_event: Event) -> None:
            counter[0] += 1

        for _ in range(10):
            bus.subscribe(EventType.USER_MESSAGE, handler)
        event = make_event()
        bus.emit(event)  # warm-up
        emissions = 1000

        start = time.perf_counter()
        for _ in range(emissions):
            bus.emit(event)
        average = (time.perf_counter() - start) / emissions

        assert counter[0] == 10 * (emissions + 1)
        assert average < 0.001
