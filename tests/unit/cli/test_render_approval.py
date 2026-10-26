"""Render of the approval flow: a pending "ask" is no error, a refusal is final (HU-05-03)."""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.cli.render import SHOWN_TYPES, render_event
from harness_agent.core import Event, EventType

ET = EventType


def make(event_type: EventType, **payload: Any) -> Event:
    return Event.create("session-1", event_type, dict(payload))


def test_an_ask_that_waits_for_the_user_shows_nothing() -> None:
    event = make(ET.PERMISSION_DECIDED, name="shell", decision="ask", resolved_as="ask")

    assert render_event(event) is None


def test_an_ask_resolved_as_denied_still_shows_the_permission_guide() -> None:
    event = make(ET.PERMISSION_DECIDED, name="shell", decision="ask", resolved_as="deny")

    line = render_event(event)

    assert line is not None and line.startswith("x Permiso")


@pytest.mark.parametrize("category", ["approval_rejected", "approval_failed"])
def test_a_refused_approval_is_shown_as_not_executed(category: str) -> None:
    event = make(ET.TOOL_FINISHED, name="shell", is_error=True, category=category)

    assert render_event(event) == "x shell: no se ejecutó."


def test_the_approval_events_are_not_shown_by_the_event_render() -> None:
    assert ET.APPROVAL_REQUESTED not in SHOWN_TYPES
    assert ET.APPROVAL_RESOLVED not in SHOWN_TYPES
