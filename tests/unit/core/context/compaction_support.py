"""Helpers to test the compactor without a database or a real provider (HU-02-03).

``FakeArchive`` follows the rules of ``SqliteCompactionArchive`` (contracts/store_protocol.md) over
a list in memory, and ``Conversation`` keeps a history and its events in step, as the loop and the
recorder do. Both live here, next to the tests, and are not part of ``tests/doubles``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from harness_agent.core import (
    CompactionCommit,
    CompactionReceipt,
    ContextCompactor,
    ContextSettings,
    Event,
    EventType,
    Message,
    MessageEvent,
    Role,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from harness_agent.core.interfaces import Provider
from tests.doubles.fake_provider import FakeProvider, Step

SESSION = "sesion-1"
PAD = " " + "relleno " * 25
KINDS = {"user_message": "user", "assistant_message": "assistant", "tool_finished": "tool"}

# Threshold of 450 estimated tokens, a recent window that is just the four last messages and a
# summary of at most 200 estimated tokens (800 characters). ``Conversation`` pads its messages so
# that a short conversation passes the threshold and, once compacted, falls below it.
SMALL = ContextSettings(
    window_tokens=1_000,
    threshold_percent=45,
    recent_percent=5,
    min_recent_messages=4,
    summary_tokens=100,
)


@dataclass
class StoredEvent:
    seq: int
    type: str
    covered_by: str | None = None


@dataclass
class FakeArchive:
    """A ``CompactionStore`` over a list; it records what it is asked and can be made to fail."""

    events: list[StoredEvent] = field(default_factory=list)
    commits: list[CompactionCommit] = field(default_factory=list)
    on_commit: Callable[[CompactionCommit], None] | None = None
    failure: BaseException | None = None
    answer_none: bool = False

    def add(self, type_name: str) -> int:
        seq = len(self.events) + 1
        self.events.append(StoredEvent(seq, type_name))
        return seq

    def message_events(self, session_id: str) -> list[MessageEvent]:
        return [
            MessageEvent(e.seq, KINDS[e.type], e.covered_by is not None)
            for e in self.events
            if e.type in KINDS
        ]

    def commit_compaction(self, commit: CompactionCommit) -> CompactionReceipt | None:
        self.commits.append(commit)
        if self.on_commit is not None:
            self.on_commit(commit)
        if self.failure is not None:
            raise self.failure
        if self.answer_none:
            return None
        rows = [
            e
            for e in self.events
            if e.covered_by is None
            and commit.protected_seq < e.seq <= commit.through_seq
            and e.type != "context_compacted"
        ]
        if not rows:
            return None
        for row in rows:
            row.covered_by = commit.summary_id
        counted = {"desde": rows[0].seq, "hasta": rows[-1].seq, "eventos": len(rows)}
        self.add("context_compacted")
        event = Event(
            commit.event_id, commit.session_id, EventType.CONTEXT_COMPACTED, payload=counted
        )
        return CompactionReceipt(commit.summary_id, rows[0].seq, rows[-1].seq, len(rows), event)

    def covered(self) -> list[int]:
        return [e.seq for e in self.events if e.covered_by is not None]


@dataclass
class Conversation:
    """A history in memory and the events that the loop and the recorder would have stored."""

    archive: FakeArchive
    history: list[Message] = field(default_factory=list)
    pad: str = PAD

    def _padded(self, text: str) -> str:
        return text + self.pad if text else text

    def system(self, text: str = "entorno") -> Message:
        message = Message(Role.SYSTEM, text)
        self.history.append(message)
        return message

    def user(self, text: str = "dato de la conversación para llenar el contexto") -> Message:
        message = Message(Role.USER, self._padded(text))
        self.history.append(message)
        self.archive.add("user_message")
        return message

    def assistant(
        self, text: str = "respuesta con texto para llenar el contexto", *calls: str
    ) -> Message:
        message = Message(
            Role.ASSISTANT,
            self._padded(text),
            tuple(ToolCall(c, "leer_archivo", {"path": "a.txt"}) for c in calls),
        )
        self.history.append(message)
        if text:
            self.archive.add("assistant_message")
        return message

    def tool(self, call_id: str, text: str = "resultado de la herramienta") -> Message:
        padded = self._padded(text)
        message = Message(
            Role.TOOL, padded, tool_result=ToolResult(call_id, padded), is_external=True
        )
        self.history.append(message)
        for name in ("tool_requested", "permission_decided", "tool_finished"):
            self.archive.add(name)
        return message

    def turns(self, count: int) -> None:
        """``count`` rounds of a user message and an answer."""
        for _ in range(count):
            self.user()
            self.assistant()


@dataclass
class Rig:
    compactor: ContextCompactor
    provider: Any  # a FakeProvider unless the test brings its own
    archive: FakeArchive
    emitted: list[tuple[EventType, dict[str, Any]]]
    published: list[Event]
    warnings: list[str]
    model: list[str]


def make_rig(
    script: Sequence[Step],
    archive: FakeArchive,
    *,
    provider: Provider | None = None,
    settings: ContextSettings = SMALL,
    definitions: Sequence[ToolDefinition] | Callable[[], Sequence[ToolDefinition]] = (),
    model: str | Callable[[], str] = "fake/test",
    publish: Callable[[Event], None] | None = None,
) -> Rig:
    provider = provider if provider is not None else FakeProvider(script)
    emitted: list[tuple[EventType, dict[str, Any]]] = []
    published: list[Event] = []
    warnings: list[str] = []
    current = [model if isinstance(model, str) else ""]
    read_model = model if callable(model) else lambda: current[0]
    read_definitions = definitions if callable(definitions) else lambda: definitions
    counter = iter(range(1, 1_000))

    def default_publish(event: Event) -> None:
        published.append(event)

    compactor = ContextCompactor(
        provider,
        archive,
        settings,
        session_id=SESSION,
        model=read_model,
        definitions=read_definitions,
        emit=lambda kind, payload: emitted.append((kind, payload)),
        publish=publish or default_publish,
        warn=warnings.append,
        new_id=lambda: f"id-{next(counter)}",
    )
    return Rig(compactor, provider, archive, emitted, published, warnings, current)
