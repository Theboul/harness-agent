"""The three write points redact secrets before they reach the disk (HU-10-02 / T003).

The key shape is built by concatenation so the repository secret detector never sees it whole.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from harness_agent.adapters.storage import (
    SqliteCompactionArchive,
    SqliteSessionStore,
    attach_event_recorder,
)
from harness_agent.core import (
    HIDDEN_SECRET,
    CompactionCommit,
    Event,
    EventType,
    InMemoryEventBus,
    Message,
    Role,
    SecretRedactor,
    ToolCall,
    ToolResult,
)
from harness_agent.core.context.conversation import clean_message

T0 = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
KEY = "sk-" + "proj-" + "Ab3dEf6hIj9kLm2nOp5qRs8tUv1wXy4z"
REAL = "provider-key-without-pattern-1"
REDACTOR = SecretRedactor([REAL])


def test_clean_message_redacts_content_arguments_and_tool_result() -> None:
    message = Message(
        role=Role.TOOL,
        content=f"key is {KEY}",
        tool_calls=(ToolCall("c1", "shell", {"command": f"echo {REAL}", "n": 3}),),
        tool_result=ToolResult("c1", f"key is {KEY}", False),
    )
    clean = clean_message(message, redact=REDACTOR)
    assert clean.content == f"key is {HIDDEN_SECRET}"
    assert clean.tool_result == ToolResult("c1", f"key is {HIDDEN_SECRET}", False)
    assert clean.tool_calls[0].arguments == {"command": f"echo {HIDDEN_SECRET}", "n": 3}
    assert message.content == f"key is {KEY}"  # the original (the live history) is untouched


def test_clean_message_without_a_redactor_still_hides_url_credentials_only() -> None:
    message = Message(role=Role.USER, content=f"{KEY} https://u:pw@host/x")
    clean = clean_message(message)
    assert KEY in clean.content
    assert "pw@" not in clean.content


def test_the_recorder_stores_a_redacted_payload_and_subscribers_see_the_original() -> None:
    bus = InMemoryEventBus()
    seen: list[Event] = []
    bus.subscribe(EventType.USER_MESSAGE, seen.append)
    with SqliteSessionStore(":memory:") as store:
        sid = store.create_session().id
        attach_event_recorder(bus, store, redact=REDACTOR.value)
        event = Event("e1", sid, EventType.USER_MESSAGE, T0, {"text": f"use {KEY} and {REAL}"})
        bus.emit(event)
        saved = store.load_session(sid)
    assert saved[0].payload == {"text": f"use {HIDDEN_SECRET} and {HIDDEN_SECRET}"}
    assert saved[0].id == "e1" and saved[0].timestamp == T0
    assert seen == [event] and event.payload["text"].startswith("use sk-")


def test_the_recorder_without_a_redactor_keeps_the_old_behavior() -> None:
    bus = InMemoryEventBus()
    with SqliteSessionStore(":memory:") as store:
        sid = store.create_session().id
        attach_event_recorder(bus, store)
        bus.emit(Event("e1", sid, EventType.USER_MESSAGE, T0, {"text": KEY}))
        assert store.load_session(sid)[0].payload == {"text": KEY}


def test_the_archive_stores_a_redacted_summary(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    store = SqliteSessionStore(db)
    try:
        sid = store.create_session().id
        for n, kind in enumerate(
            [EventType.USER_MESSAGE, EventType.ASSISTANT_MESSAGE, EventType.USER_MESSAGE], 1
        ):
            store.save_event(Event(f"x{n}", sid, kind, T0, {}))
        archive = SqliteCompactionArchive(store, clock=lambda: T0, redact=REDACTOR)
        receipt = archive.commit_compaction(
            CompactionCommit(sid, 1, 3, f"the user pasted {KEY}", "r1", "ev-r1")
        )
        assert receipt is not None
    finally:
        store.close()
    with sqlite3.connect(db) as raw:
        (text,) = raw.execute("SELECT texto FROM resumenes").fetchone()
    assert text == f"the user pasted {HIDDEN_SECRET}"
