"""Tests of the subscription of the CLI to the bus and of how it writes (HU-06-01 / T004).

The bus is the real ``InMemoryEventBus`` and the output is an in-memory stream. A failure while
writing is never swallowed: it goes up to the bus, which groups it in an ``EventDeliveryError``.
"""

from __future__ import annotations

import io
import sys
from typing import Any

import pytest

import harness_agent.cli as cli
from harness_agent.cli import app
from harness_agent.cli.app import attach_renderer
from harness_agent.cli.render import SHOWN_TYPES, render_event
from harness_agent.core import (
    Event,
    EventBus,
    EventDeliveryError,
    EventHandler,
    EventType,
    InMemoryEventBus,
)

ET = EventType


def make(event_type: EventType, **payload: Any) -> Event:
    return Event.create("session-1", event_type, dict(payload))


class SubscriptionSpy(EventBus):
    """A bus that only records what is subscribed."""

    def __init__(self) -> None:
        self.subscribed: list[EventType] = []
        self.handlers: list[EventHandler] = []

    def emit(self, event: Event) -> None:
        raise AssertionError("not used")

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        self.subscribed.append(event_type)
        self.handlers.append(handler)


class FlushSpy(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.flushes = 0

    def flush(self) -> None:
        self.flushes += 1
        super().flush()


class WriteFails(io.StringIO):
    def write(self, text: str, /) -> int:
        raise OSError("disco lleno")


class FlushFails(io.StringIO):
    def flush(self) -> None:
        raise OSError("no se pudo vaciar")


class TestSuscripcion:
    def test_it_subscribes_exactly_the_shown_types_once_each(self) -> None:
        bus = SubscriptionSpy()

        attach_renderer(bus, io.StringIO())

        assert bus.subscribed == list(SHOWN_TYPES)

    def test_only_the_shown_types_write_and_the_others_are_ignored_without_error(self) -> None:
        bus, output = InMemoryEventBus(), io.StringIO()
        attach_renderer(bus, output)

        for event_type in ET:
            bus.emit(
                make(
                    event_type,
                    name="buscar",
                    is_error=False,
                    content="hola",
                    decision="allow",
                    reason="invalid_response",
                    error_type="E",
                )
            )

        # The order is the one of the catalog; an allowed permission shows nothing.
        lines = output.getvalue().splitlines()
        assert [line.split(":")[0] for line in lines] == [
            "> hola",
            "... ejecutando",
            "v buscar",
            "x Límite",
            "x Error",
        ]
        assert len(lines) == len(SHOWN_TYPES) - 1  # the six shown types, minus the allowed one

    def test_the_lines_follow_the_order_of_emission(self) -> None:
        bus, output = InMemoryEventBus(), io.StringIO()
        attach_renderer(bus, output)

        bus.emit(make(ET.TOOL_REQUESTED, name="uno"))
        bus.emit(make(ET.TOOL_FINISHED, name="uno", is_error=False))
        bus.emit(make(ET.ASSISTANT_MESSAGE, content="listo"))

        assert output.getvalue() == "... ejecutando: uno\nv uno: correcto\n> listo\n"

    def test_every_line_ends_with_a_line_break_and_the_output_is_flushed(self) -> None:
        bus, output = InMemoryEventBus(), FlushSpy()
        attach_renderer(bus, output)

        bus.emit(make(ET.TOOL_REQUESTED, name="uno"))
        bus.emit(make(ET.TOOL_REQUESTED, name="dos"))

        assert output.getvalue() == "... ejecutando: uno\n... ejecutando: dos\n"
        assert output.flushes == 2

    def test_an_event_without_text_writes_nothing_and_does_not_flush(self) -> None:
        bus, output = InMemoryEventBus(), FlushSpy()
        attach_renderer(bus, output)

        bus.emit(make(ET.ASSISTANT_MESSAGE, content=""))

        assert output.getvalue() == ""
        assert output.flushes == 0

    def test_without_an_output_it_writes_to_the_standard_output_of_the_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        replaced = io.StringIO()
        monkeypatch.setattr(sys, "stdout", replaced)
        bus = InMemoryEventBus()

        attach_renderer(bus)
        bus.emit(make(ET.TOOL_REQUESTED, name="buscar"))

        assert replaced.getvalue() == "... ejecutando: buscar\n"

    def test_with_an_injected_output_nothing_goes_to_the_real_standard_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bus = InMemoryEventBus()
        attach_renderer(bus, io.StringIO())

        bus.emit(make(ET.TOOL_REQUESTED, name="buscar"))

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_attaching_twice_to_the_same_bus_duplicates_the_output(self) -> None:
        bus, output = InMemoryEventBus(), io.StringIO()
        attach_renderer(bus, output)
        attach_renderer(bus, output)

        bus.emit(make(ET.TOOL_REQUESTED, name="buscar"))

        assert output.getvalue() == "... ejecutando: buscar\n" * 2

    def test_the_public_api_exposes_the_render_and_the_subscription(self) -> None:
        assert cli.render_event is render_event
        assert cli.attach_renderer is app.attach_renderer
        assert set(cli.__all__) >= {"render_event", "attach_renderer"}


class TestFallosDeEscritura:
    def test_a_failing_write_reaches_the_emitter_inside_a_delivery_error(self) -> None:
        bus = InMemoryEventBus()
        attach_renderer(bus, WriteFails())

        with pytest.raises(EventDeliveryError) as raised:
            bus.emit(make(ET.TOOL_REQUESTED, name="buscar"))

        (cause,) = raised.value.exceptions
        assert isinstance(cause, OSError)
        assert str(cause) == "disco lleno"

    def test_a_closed_output_is_not_hidden(self) -> None:
        output = io.StringIO()
        output.close()
        bus = InMemoryEventBus()
        attach_renderer(bus, output)

        with pytest.raises(EventDeliveryError) as raised:
            bus.emit(make(ET.TOOL_REQUESTED, name="buscar"))

        assert isinstance(raised.value.exceptions[0], ValueError)

    def test_a_failing_flush_is_not_hidden(self) -> None:
        bus = InMemoryEventBus()
        attach_renderer(bus, FlushFails())

        with pytest.raises(EventDeliveryError) as raised:
            bus.emit(make(ET.TOOL_REQUESTED, name="buscar"))

        assert isinstance(raised.value.exceptions[0], OSError)

    def test_a_failure_does_not_stop_the_other_subscribers(self) -> None:
        bus = InMemoryEventBus()
        other: list[Event] = []
        attach_renderer(bus, WriteFails())
        bus.subscribe(ET.TOOL_REQUESTED, other.append)

        with pytest.raises(EventDeliveryError):
            bus.emit(make(ET.TOOL_REQUESTED, name="buscar"))

        assert len(other) == 1


class TestCodificacion:
    def test_a_character_the_console_cannot_show_is_replaced_not_fatal(self) -> None:
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="cp1252", newline="\n")
        bus = InMemoryEventBus()
        attach_renderer(bus, stream)

        bus.emit(make(ET.ASSISTANT_MESSAGE, content="hola \U0001f642 ñ á"))
        stream.flush()

        assert raw.getvalue().decode("cp1252") == "> hola ? ñ á\n"

    def test_the_stream_is_not_reconfigured(self) -> None:
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="\n")
        bus = InMemoryEventBus()
        attach_renderer(bus, stream)

        bus.emit(make(ET.ASSISTANT_MESSAGE, content="\U0001f642"))

        assert stream.encoding == "cp1252"
        assert stream.errors == "strict"

    def test_a_stream_without_encoding_receives_the_text_unchanged(self) -> None:
        output = io.StringIO()
        bus = InMemoryEventBus()
        attach_renderer(bus, output)

        bus.emit(make(ET.ASSISTANT_MESSAGE, content="hola \U0001f642 ñ"))

        assert output.getvalue() == "> hola \U0001f642 ñ\n"
