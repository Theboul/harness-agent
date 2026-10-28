"""Helpers to leave a past session in a real database, as a process that was cut would (HU-03-04).

``seed_session`` writes the events and the messages of a conversation with the stores of the
adapters (no mocks), so a composition built afterwards on the same file can resume it.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_agent.adapters.storage import SqliteMessageStore, SqliteSessionStore
from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import HarnessConfig
from harness_agent.core import (
    Event,
    EventType,
    Message,
    MessageRecord,
    ProviderResponse,
    Role,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)
MODEL = "openai/modelo-de-prueba"


def event_type(message: Message) -> EventType | None:
    """The event the loop publishes for a message, or ``None`` if it publishes none."""
    if message.role is Role.USER:
        return EventType.USER_MESSAGE
    if message.role is Role.TOOL:
        return EventType.TOOL_FINISHED
    return EventType.ASSISTANT_MESSAGE if message.content else None


def payload(message: Message) -> dict[str, Any]:
    if message.role is Role.TOOL and message.tool_result is not None:
        return {
            "call_id": message.tool_result.call_id,
            "name": "leer_archivo",
            "is_error": message.tool_result.is_error,
            "category": "tool_error" if message.tool_result.is_error else "ok",
        }
    return {"content": message.content}


def seed_session(
    database: Path,
    messages: Sequence[Message],
    *,
    unsaved_events_from: int | None = None,
    model: str | None = MODEL,
) -> str:
    """Save a session with these messages and the events of the ones that have one.

    Args:
        database: The file of the sessions database.
        messages: The conversation, in order.
        unsaved_events_from: From this position (1-based) on, the event of a message is not
            saved, as if the process had died between the message and its event.
        model: The model recorded for the session.

    Returns:
        The identifier of the session.
    """
    store = SqliteSessionStore(database)
    try:
        session = store.create_session(model=model).id
        records: list[MessageRecord] = []
        for position, message in enumerate(messages, start=1):
            kind = event_type(message)
            event_id = None if kind is None else f"{session[:8]}-e{position}"
            records.append(MessageRecord(position, message, event_id))
            if kind is not None and (unsaved_events_from is None or position < unsaved_events_from):
                store.save_event(
                    Event.create(session, kind, payload(message), event_id=event_id, timestamp=NOW)
                )
        SqliteMessageStore(store, clock=lambda: NOW).append(session, records)
        return session
    finally:
        store.close()


def dump_session(connection: Any, session: str) -> dict[str, list[tuple[object, ...]]]:
    """The rows of one session in the tables that hold its history."""
    queries = {
        "events": "SELECT * FROM events WHERE session_id = ? ORDER BY seq",
        "mensajes": "SELECT * FROM mensajes WHERE sesion_id = ? ORDER BY posicion",
        "resumenes": "SELECT * FROM resumenes WHERE sesion_id = ? ORDER BY rowid",
    }
    return {name: connection.execute(sql, (session,)).fetchall() for name, sql in queries.items()}


# --- driving a composition on the same database ------------------------------------------------


def config_for(tmp_path: Path, **changes: Any) -> HarnessConfig:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(exist_ok=True)
    config = make_config(tmp_path, workspace=workspace, model=MODEL)
    if "context" in changes:
        config = replace(config, context=changes.pop("context"))
    return replace(config, limits=replace(config.limits, **changes)) if changes else config


def make(
    tmp_path: Path, opened: list[Composition], *texts: str, **changes: Any
) -> tuple[Composition, FakeProvider]:
    provider = FakeProvider([ProviderResponse(content=text) for text in texts or ("hecho",)])
    composition = build(opened, config_for(tmp_path, **changes), provider, system_name="Linux")
    return composition, provider


async def drive(composition: Composition, *lines: str) -> tuple[int, str]:
    output = io.StringIO()
    code = await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
        output=output,
    )
    return code, output.getvalue()


def dump_all(composition: Composition) -> dict[str, list[tuple[object, ...]]]:
    connection = composition.store.connection()
    names = [
        n
        for (n,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {n: connection.execute(f"SELECT * FROM {n} ORDER BY 1, 2").fetchall() for n in names}


def extend_session(
    database: Path, session: str, messages: Sequence[Message], *, start: int
) -> None:
    """Add messages (and their events) to a session that already exists, from ``start`` on."""
    store = SqliteSessionStore(database)
    try:
        records: list[MessageRecord] = []
        for position, message in enumerate(messages, start=start):
            kind = event_type(message)
            event_id = None if kind is None else f"{session[:8]}-e{position}"
            records.append(MessageRecord(position, message, event_id))
            if kind is not None:
                store.save_event(
                    Event.create(session, kind, payload(message), event_id=event_id, timestamp=NOW)
                )
        SqliteMessageStore(store, clock=lambda: NOW).append(session, records)
    finally:
        store.close()
