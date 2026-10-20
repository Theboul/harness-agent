"""Sp1-25 of HU-01-05: the bus with a logging subscriber, only in tests (T006).

A second "interface" connects to the bus just by subscribing: here, a handler that writes one
``logging`` line per event (type, session and event id; never the payload, which can hold
sensitive data). The core does not know it exists and prints nothing. There is no production
subscriber: this handler lives only in this test module (FR-017).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from harness_agent.core.events import Event, EventType
from harness_agent.core.in_memory_event_bus import InMemoryEventBus
from harness_agent.core.interfaces.provider import ProviderResponse
from tests.core.support import call, make_rig, response
from tests.doubles import RecordingTool

LOGGER_NAME = "harness.events"
SENTINEL = "VALOR-DE-PRUEBA-123"
SRC = Path(__file__).resolve().parents[2] / "src"
logger = logging.getLogger(LOGGER_NAME)


def log_event(event: Event) -> None:
    """The logging subscriber: one INFO line per event, without the payload."""
    logger.info("evento %s sesion=%s id=%s", event.type.value, event.session_id, event.id)


def subscribe_logger_to_every_type(bus: InMemoryEventBus) -> None:
    for event_type in EventType:
        bus.subscribe(event_type, log_event)


def logged_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME]


class TestSuscriptorDeRegistro:
    async def test_a_complete_turn_leaves_one_log_entry_per_event_in_order(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        bus = InMemoryEventBus()
        received: list[Event] = []
        subscribe_logger_to_every_type(bus)
        for event_type in EventType:
            bus.subscribe(event_type, received.append)
        script: list[ProviderResponse | BaseException] = [
            response(call("c1", "step_1", n=1)),
            ProviderResponse(content="all done"),
        ]
        rig = make_rig(script, [RecordingTool("step_1", content="r1")], bus=bus)

        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            await rig.run("start")

        messages = logged_messages(caplog)
        assert len(received) == 5
        assert len(messages) == len(received)
        for message, event in zip(messages, received, strict=True):
            assert message == f"evento {event.type.value} sesion={event.session_id} id={event.id}"

    def test_one_event_of_each_of_the_17_types_gives_17_entries(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        bus = InMemoryEventBus()
        subscribe_logger_to_every_type(bus)

        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            for event_type in EventType:
                bus.emit(Event.create("session-1", event_type))

        messages = logged_messages(caplog)
        assert len(messages) == 17
        assert [m.split()[1] for m in messages] == [t.value for t in EventType]

    def test_the_payload_of_the_event_is_never_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        bus = InMemoryEventBus()
        subscribe_logger_to_every_type(bus)

        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            bus.emit(Event.create("session-1", EventType.TOOL_FINISHED, {"content": SENTINEL}))

        assert len(logged_messages(caplog)) == 1
        assert SENTINEL not in caplog.text

    async def test_the_logging_subscriber_and_another_subscriber_both_receive_every_event(
        self, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bus = InMemoryEventBus()
        other: list[Event] = []
        subscribe_logger_to_every_type(bus)
        for event_type in EventType:
            bus.subscribe(event_type, other.append)
        rig = make_rig([RuntimeError("provider down")], [RecordingTool("t")], bus=bus)

        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            await rig.run("task")

        assert [e.type for e in other] == [EventType.USER_MESSAGE, EventType.PROVIDER_ERROR]
        assert len(logged_messages(caplog)) == len(other) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestSinSuscriptorDeProduccion:
    def test_the_logging_subscriber_does_not_exist_in_the_source_code(self) -> None:
        offenders = [
            path.name
            for path in SRC.rglob("*.py")
            if LOGGER_NAME in path.read_text(encoding="utf-8")
        ]

        assert offenders == []
