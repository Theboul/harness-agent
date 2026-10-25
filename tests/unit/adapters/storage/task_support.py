"""Shared helpers for the task store tests (HU-11-01)."""

from __future__ import annotations

import itertools
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.core import (
    CriterionDefinition,
    Event,
    EventBus,
    EventHandler,
    EventType,
    TaskDefinition,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)

TASK = TaskDefinition(
    title="TAREA-14",
    objective=f"Exigir el correo {SENTINEL}",
    context="contexto",
    rules="reglas",
    criteria=(
        CriterionDefinition("El email es obligatorio", "pytest tests/test_email.py", "salida 0"),
        CriterionDefinition("El mensaje de error es claro"),
    ),
)


class RecordingBus(EventBus):
    """Collects the events it is given."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:  # pragma: no cover
        raise NotImplementedError

    def motives(self) -> list[object]:
        return [event.payload["motivo"] for event in self.events]


def sequential_ids(prefix: str = "id") -> Callable[[], str]:
    counter = itertools.count(1)
    return lambda: f"{prefix}-{next(counter)}"


def open_session_store(tmp_path: Path) -> SqliteSessionStore:
    return SqliteSessionStore(tmp_path / "db" / "sessions.db")


def raw(store: SqliteSessionStore) -> sqlite3.Connection:
    """The connection of the store, to look at (and tamper with) the tables directly."""
    return store.connection()
