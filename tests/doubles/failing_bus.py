"""Test double: FailingEventBus (HU-01-01, T004).

A RecordingEventBus that raises a configured exception when it receives selected
event types, counting the attempts. It stands for a genuine failure propagated by
``EventBus.emit`` (not an isolated subscriber failure, which is HU-01-05's job).
"""

from __future__ import annotations

from harness_agent.core.events import Event, EventType
from tests.doubles.recording_bus import RecordingEventBus


class FailingEventBus(RecordingEventBus):
    """Event bus that raises ``error`` whenever an event of a configured type is emitted."""

    def __init__(self, fail_on: set[EventType], error: Exception | None = None) -> None:
        super().__init__()
        self.fail_on = set(fail_on)
        self.error = error or RuntimeError("event bus failure")
        self.failed_attempts: list[EventType] = []

    def emit(self, event: Event) -> None:
        if event.type in self.fail_on:
            self.failed_attempts.append(event.type)
            raise self.error
        super().emit(event)
