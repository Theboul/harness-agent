"""Fakes for the subagent runner tests: sessions, child loop and turn, with no loop and no store."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from harness_agent.core import Event, EventBus, EventHandler, EventType, Message
from harness_agent.core.subagents.runner import LoopSubagentRunner

SENTINEL = "VALOR-DE-PRUEBA-123"
PARENT = "padre-0001"
GOAL = "Resume el módulo de permisos."


@dataclass(frozen=True)
class FakeTurn:
    """What ``AgentLoop.run_turn`` returns, as the runner reads it."""

    status: str = "completed"
    final_response: str | None = None
    history: tuple[Message, ...] = ()
    error: str | None = None


class FakeSessions:
    """Creates child sessions in memory; ``fail`` makes the creation raise."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.created: list[tuple[str, str]] = []

    def create(self, parent_id: str, goal: str) -> str:
        if self.fail:
            raise RuntimeError(SENTINEL)
        self.created.append((parent_id, goal))
        return f"hija-{len(self.created):04d}"


class FakeLoop:
    """The child loop: records what it receives and answers with ``outcome`` (or raises it)."""

    def __init__(self, outcome: FakeTurn | BaseException) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, str, list[Message]]] = []
        self.histories: list[list[Message]] = []

    async def __call__(self, session_id: str, task: str, history: list[Message]) -> FakeTurn:
        self.histories.append(history)
        self.calls.append((session_id, task, list(history)))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class RecordingBus(EventBus):
    """Keeps what is emitted; raises on the types in ``failing``."""

    def __init__(self, failing: frozenset[EventType] = frozenset()) -> None:
        self.events: list[Event] = []
        self.failing = failing

    def emit(self, event: Event) -> None:
        if event.type in self.failing:
            raise RuntimeError(SENTINEL)
        self.events.append(event)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        raise NotImplementedError


def answer(**changes: Any) -> str:
    """A valid final answer of a subagent as the JSON text it would write."""
    data: dict[str, Any] = {
        "resultado": "listo",
        "hallazgos_clave": ["uno", "dos"],
        "fuentes": ["a.py"],
    }
    data.update(changes)
    return json.dumps(data)


def make_runner(
    outcome: FakeTurn | BaseException,
    *,
    sessions: FakeSessions | None = None,
    bus: EventBus | None = None,
    redact: Any = None,
    parent: Any = None,
) -> tuple[LoopSubagentRunner, FakeSessions, FakeLoop, EventBus]:
    sessions = FakeSessions() if sessions is None else sessions
    loop = FakeLoop(outcome)
    bus = RecordingBus() if bus is None else bus
    options: dict[str, Any] = {} if redact is None else {"redact": redact}
    runner = LoopSubagentRunner(
        sessions, loop, bus, (lambda: PARENT) if parent is None else parent, **options
    )
    return runner, sessions, loop, bus
