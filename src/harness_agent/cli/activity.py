"""The activity view: a line per step of the agent, with how long each tool took (HU-06-05).

``ActivityRenderer`` turns the events of the bus into the lines of ``render.render_event`` and adds
the one thing that needs memory: the duration of a tool, derived from the timestamps of its
``tool_requested`` and ``tool_finished`` events (matched by ``call_id``) minus the time the person
took to answer an approval (between the ``ask`` permission decision and ``approval_resolved``).
It keeps only timestamps, never arguments or content, and at most ``MAX_PENDING_CALLS`` of them.
A color style only paints the marker of the first line; the text is the same without it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from harness_agent.core import Event, EventType

from .render import render_event
from .style import PLAIN, Style

MAX_PENDING_CALLS = 256
# Marker at the start of the text -> the color of that marker.
MARKER_COLORS = {
    "[..]": "cyan",
    "[ok]": "green",
    "[x]": "red",
    "[?]": "yellow",
    "[~]": "cyan",
    "agente>": "bold",
}
MARKER_PATTERN = re.compile(r"\A( *)(" + "|".join(re.escape(m) for m in MARKER_COLORS) + ")")


@dataclass
class _Pending:
    requested_at: datetime
    asked_at: datetime | None = None
    waited: timedelta = field(default_factory=timedelta)


def format_duration(elapsed: timedelta) -> str:
    """``250 ms``, ``1,2 s`` or ``2 min 5 s``: short, with the decimal comma of Spanish."""
    total_ms = round(elapsed.total_seconds() * 1000)
    if total_ms < 1000:
        return f"{total_ms} ms"
    if total_ms < 60_000:
        return f"{total_ms / 1000:.1f}".replace(".", ",") + " s"
    minutes, seconds = divmod(total_ms // 1000, 60)
    return f"{minutes} min {seconds} s"


class ActivityRenderer:
    """Renders events as activity lines; one instance per terminal (it keeps the pending calls)."""

    def __init__(self, style: Style = PLAIN) -> None:
        self._style = style
        self._pending: dict[str, _Pending] = {}

    def render(self, event: Event) -> str | None:
        """The line to show for ``event``, or ``None`` when it shows nothing."""
        duration = self._track(event)
        text = render_event(event, duration)
        return None if text is None else self._paint(text)

    def _track(self, event: Event) -> str | None:
        call_id = event.payload.get("call_id")
        if not isinstance(call_id, str):
            return None
        if event.type is EventType.TOOL_REQUESTED:
            self._pending[call_id] = _Pending(event.timestamp)
            if len(self._pending) > MAX_PENDING_CALLS:
                del self._pending[next(iter(self._pending))]
            return None
        pending = self._pending.get(call_id)
        if pending is None:
            return None
        if event.type is EventType.PERMISSION_DECIDED and event.payload.get("decision") == "ask":
            pending.asked_at = event.timestamp
        elif event.type is EventType.APPROVAL_RESOLVED and pending.asked_at is not None:
            pending.waited += event.timestamp - pending.asked_at
            pending.asked_at = None
        elif event.type is EventType.TOOL_FINISHED:
            del self._pending[call_id]
            elapsed = event.timestamp - pending.requested_at - pending.waited
            return format_duration(elapsed) if elapsed >= timedelta(0) else None
        return None

    def _paint(self, text: str) -> str:
        """Paint the marker at the start of the first line; the rest of the text is untouched."""

        def color_marker(found: re.Match[str]) -> str:
            marker = found.group(2)
            return found.group(1) + self._style.paint(marker, MARKER_COLORS[marker])

        return MARKER_PATTERN.sub(color_marker, text, count=1)
