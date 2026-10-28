"""Doubles and helpers to test the conversation log without a database (HU-03-04).

``InMemoryMessageLog`` is a ``MessageLog`` that records its batches and can be made to fail.
``LoopSim`` keeps a history and publishes events to a capture in the order the loop does: the
message is appended first and the event follows. Both live here, next to the tests, and are not
part of ``tests/doubles``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from harness_agent.core import (
    Event,
    EventType,
    Message,
    MessageRecord,
    Role,
    StoredConversation,
    StoredMessage,
    ToolCall,
    ToolResult,
)

SESSION = "sesion-1"
REJECTION = "[approval_rejected] Tool '{name}' was rejected by the user."


def standard_rejection(name: str) -> str:
    """The rejection text the composition hands to the capture."""
    return REJECTION.format(name=name)


class InMemoryMessageLog:
    """A ``MessageLog`` over lists; ``fail_at`` makes the n-th ``append`` (1-based) raise."""

    def __init__(self) -> None:
        self.batches: list[tuple[str, tuple[MessageRecord, ...]]] = []
        self.calls = 0
        self.fail_at: int | None = None
        self.error: BaseException = RuntimeError("fallo del almacen")

    def append(self, session_id: str, records: Sequence[MessageRecord]) -> None:
        self.calls += 1
        if self.fail_at is not None and self.calls == self.fail_at:
            raise self.error
        self.batches.append((session_id, tuple(records)))

    def last_position(self, session_id: str) -> int:
        positions = [r.position for s, batch in self.batches if s == session_id for r in batch]
        return max(positions, default=0)

    @property
    def records(self) -> list[MessageRecord]:
        return [record for _, batch in self.batches for record in batch]


class LoopSim:
    """Imitates the order of the loop: append the message, then publish its event."""

    def __init__(self, capture: Any, session_id: str = SESSION, prefix: Sequence[Message] = ()):
        self.capture = capture
        self.session_id = session_id
        self.history: list[Message] = list(prefix)
        self.events: list[Event] = []
        self._count = 0

    def event(self, kind: EventType, payload: dict[str, Any]) -> Event:
        self._count += 1
        event = Event.create(self.session_id, kind, payload, event_id=f"e{self._count}")
        self.events.append(event)
        self.capture.on_event(event)
        return event

    def user(self, text: str) -> Message:
        message = Message(Role.USER, text)
        self.history.append(message)
        self.event(EventType.USER_MESSAGE, {"content": text})
        return message

    def assistant(self, text: str = "", calls: Sequence[ToolCall] = ()) -> Message:
        message = Message(Role.ASSISTANT, text, tuple(calls))
        self.history.append(message)
        if text:
            self.event(
                EventType.ASSISTANT_MESSAGE,
                {"content": text, "tool_call_count": len(calls), "final": not calls},
            )
        return message

    def requested(self, call: ToolCall) -> None:
        self.event(EventType.TOOL_REQUESTED, {"call_id": call.id, "name": call.name})

    def finished(
        self,
        call: ToolCall,
        content: str,
        *,
        is_error: bool = False,
        category: str = "ok",
        external: bool = False,
    ) -> Message:
        message = Message(
            Role.TOOL,
            content,
            tool_result=ToolResult(call.id, content, is_error),
            is_external=external,
        )
        self.history.append(message)
        self.event(
            EventType.TOOL_FINISHED,
            {"call_id": call.id, "name": call.name, "is_error": is_error, "category": category},
        )
        return message


MESSAGE_EVENTS = frozenset(
    {EventType.USER_MESSAGE.value, EventType.ASSISTANT_MESSAGE.value, EventType.TOOL_FINISHED.value}
)


class InMemoryConversationSource:
    """A ``MessageLog`` and a ``ResumeSource`` over lists that follow the rules of the SQLite
    adapter: the stored events carry the mark of the summary that covers them, a stored message
    points at its event by identifier, and ``load_conversation`` reads it all back."""

    def __init__(self) -> None:
        self.rows: dict[str, list[MessageRecord]] = {}
        self.events: dict[str, list[dict[str, Any]]] = {}
        self.summaries: dict[str, list[str]] = {}
        self.models: dict[str, str | None] = {}
        self.tasks: set[str] = set()
        self.loads = 0

    # -- MessageLog
    def append(self, session_id: str, records: Sequence[MessageRecord]) -> None:
        """All or none; a record already saved is ignored, a different one in its place fails."""
        saved = {r.position: r for r in self.rows.get(session_id, [])}
        fresh: list[MessageRecord] = []
        for record in records:
            known = saved.get(record.position)
            if known is None:
                fresh.append(record)
            elif known != record:
                raise ValueError("posicion ocupada")
        self.rows.setdefault(session_id, []).extend(fresh)

    def last_position(self, session_id: str) -> int:
        return max((r.position for r in self.rows.get(session_id, [])), default=0)

    # -- what the event recorder and the compaction archive do
    def record_event(self, event: Event) -> None:
        self.events.setdefault(event.session_id, []).append(
            {"id": event.id, "type": event.type.value, "by": None}
        )

    def cover_through(self, session_id: str, position: int, summary: str) -> None:
        """Cover the events of the messages up to ``position`` (the head stays) with a summary."""
        covered_ids = {
            r.event_id
            for r in self.rows.get(session_id, [])
            if 1 < r.position <= position and r.event_id is not None
        }
        for event in self.events.get(session_id, []):
            if event["id"] in covered_ids and event["by"] is None:
                event["by"] = f"s{len(self.summaries.get(session_id, [])) + 1}"
        self.summaries.setdefault(session_id, []).append(summary)

    # -- ResumeSource
    def load_conversation(self, session_id: str) -> StoredConversation | None:
        self.loads += 1
        if session_id not in self.rows and session_id not in self.events:
            return None
        events = {e["id"]: e for e in self.events.get(session_id, [])}
        rows = sorted(self.rows.get(session_id, []), key=lambda r: r.position)
        pointed = {r.event_id for r in rows if r.event_id is not None}
        messages = tuple(
            StoredMessage(
                r,
                None
                if r.event_id is None or r.event_id not in events
                else events[r.event_id]["by"] is not None,
            )
            for r in rows
        )
        summaries = self.summaries.get(session_id, [])
        kinds = [e for e in self.events.get(session_id, []) if e["type"] != "context_compacted"]
        return StoredConversation(
            session_id,
            self.models.get(session_id, "m"),
            session_id in self.tasks,
            messages,
            summaries[-1] if summaries else None,
            sum(
                1 for e in events.values() if e["type"] in MESSAGE_EVENTS and e["id"] not in pointed
            ),
            kinds[-1]["type"] if kinds else None,
        )


class Cut(Exception):
    """The simulated process died."""


class Tee:
    """What the bus does for two subscribers: the capture first, then the event recorder.

    ``die_at`` (1-based count of delivered events) with ``stage`` ``before_capture`` or
    ``after_capture`` raises ``Cut`` at that point, as a process that dies would."""

    def __init__(self, capture: Any, source: InMemoryConversationSource) -> None:
        self.capture = capture
        self.source = source
        self.count = 0
        self.die_at: int | None = None
        self.stage = "before_capture"

    def on_event(self, event: Event) -> None:
        self.count += 1
        dying = self.die_at == self.count
        if dying and self.stage == "before_capture":
            raise Cut()
        self.capture.on_event(event)
        if dying and self.stage == "after_capture":
            raise Cut()
        self.source.record_event(event)
