"""Canonical English event catalog and AuthorizedArea contract (contract-naming standardization)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harness_agent.core import AuthorizedArea as CoreAuthorizedArea
from harness_agent.core.events import Event, EventType
from harness_agent.core.interfaces import AuthorizedArea
from tests.doubles.dummy_authorized_area import DummyAuthorizedArea

CANONICAL_EVENTS = {
    "USER_MESSAGE": "user_message",
    "ASSISTANT_MESSAGE": "assistant_message",
    "TOOL_REQUESTED": "tool_requested",
    "TOOL_FINISHED": "tool_finished",
    "APPROVAL_REQUESTED": "approval_requested",
    "APPROVAL_RESOLVED": "approval_resolved",
    "CONTEXT_COMPACTED": "context_compacted",
    "PERMISSION_DECIDED": "permission_decided",
    "CRITERIA_TAMPERED": "criteria_tampered",
    "LIMIT_REACHED": "limit_reached",
    "PROVIDER_ERROR": "provider_error",
    "PROVIDER_SWITCHED": "provider_switched",
    "SUBAGENT_STARTED": "subagent_started",
    "SUBAGENT_FINISHED": "subagent_finished",
    "INTERRUPTED": "interrupted",
    "SESSION_STARTED": "session_started",
    "CRITERION_VERIFIED": "criterion_verified",
}


def test_event_type_has_exactly_the_17_canonical_members() -> None:
    assert {m.name: m.value for m in EventType} == CANONICAL_EVENTS
    assert len(EventType) == 17
    assert len({m.value for m in EventType}) == 17


@pytest.mark.parametrize(("name", "value"), CANONICAL_EVENTS.items())
def test_event_type_values_parse_from_serialized_string(name: str, value: str) -> None:
    assert EventType(value) is EventType[name]


def test_event_serialization_round_trip_uses_english_values() -> None:
    event = Event.create(session_id="s1", type=EventType.APPROVAL_REQUESTED, payload={"k": 1})
    wire = json.dumps({"type": event.type.value, "payload": event.payload})
    restored = Event.create(session_id="s1", type=json.loads(wire)["type"])
    assert wire.startswith('{"type": "approval_requested"')
    assert restored.type is EventType.APPROVAL_REQUESTED


def test_previous_spanish_values_are_not_accepted() -> None:
    with pytest.raises(ValueError):
        EventType("mensaje_usuario")


def test_authorized_area_is_exported_from_core_and_interfaces() -> None:
    assert AuthorizedArea is CoreAuthorizedArea


def test_authorized_area_exposes_only_root_and_contains() -> None:
    assert AuthorizedArea.__abstractmethods__ == frozenset({"root", "contains"})


def test_authorized_area_double_contains_and_rejects_escape(tmp_path: Path) -> None:
    area = DummyAuthorizedArea(tmp_path)
    assert isinstance(area, AuthorizedArea)
    assert area.root == tmp_path.resolve()
    assert area.contains("sub/file.txt")
    assert not area.contains("../outside.txt")


def test_event_coerces_string_type_to_enum() -> None:
    event = Event(id="e1", session_id="s1", type="user_message")  # type: ignore[arg-type]
    assert event.type is EventType.USER_MESSAGE


def test_event_naive_timestamp_becomes_utc() -> None:
    naive = datetime(2026, 10, 23, 12, 0, 0)
    event = Event(id="e1", session_id="s1", type=EventType.USER_MESSAGE, timestamp=naive)
    assert event.timestamp.tzinfo is timezone.utc
    assert event.timestamp.replace(tzinfo=None) == naive


def test_event_aware_timestamp_is_preserved() -> None:
    aware = datetime(2026, 10, 23, 12, 0, 0, tzinfo=timezone.utc)
    event = Event(id="e1", session_id="s1", type=EventType.USER_MESSAGE, timestamp=aware)
    assert event.timestamp == aware
