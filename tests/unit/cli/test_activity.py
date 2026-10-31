"""The activity view: one line per step, with the duration of each tool (HU-06-05 / T007, AC-03)."""

from __future__ import annotations

import io
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from harness_agent.cli.activity import MAX_PENDING_CALLS, ActivityRenderer, format_duration
from harness_agent.cli.app import attach_renderer
from harness_agent.cli.style import ESCAPE, Style
from harness_agent.core import Event, EventType, InMemoryEventBus

ET = EventType
START = datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"


def at(seconds: float, event_type: EventType, **payload: Any) -> Event:
    return Event.create(
        "s1", event_type, dict(payload), timestamp=START + timedelta(seconds=seconds)
    )


def requested(seconds: float, call_id: str = "c1", name: str = "shell") -> Event:
    return at(seconds, ET.TOOL_REQUESTED, call_id=call_id, name=name)


def finished(seconds: float, call_id: str = "c1", name: str = "shell", **extra: Any) -> Event:
    payload: dict[str, Any] = {"call_id": call_id, "name": name, "is_error": False}
    payload.update(extra)
    return at(seconds, ET.TOOL_FINISHED, **payload)


class TestFormatDuration:
    @pytest.mark.parametrize(
        ("seconds", "text"),
        [
            (0, "0 ms"),
            (0.25, "250 ms"),
            (0.9994, "999 ms"),
            (0.9996, "1,0 s"),
            (1.2, "1,2 s"),
            (59.94, "59,9 s"),
            (60, "1 min 0 s"),
            (125, "2 min 5 s"),
        ],
    )
    def test_the_format_is_short_and_in_spanish(self, seconds: float, text: str) -> None:
        assert format_duration(timedelta(seconds=seconds)) == text


class TestDuration:
    def test_a_tool_shows_how_long_it_took(self) -> None:
        view = ActivityRenderer()

        assert view.render(requested(0)) == "  [..] shell: ejecutando"
        assert view.render(finished(1.2)) == "  [ok] shell: correcto (1,2 s)"

    def test_two_tools_at_once_are_matched_by_their_call_id(self) -> None:
        view = ActivityRenderer()
        view.render(requested(0, "a", "uno"))
        view.render(requested(0.5, "b", "dos"))

        assert view.render(finished(2, "b", "dos")) == "  [ok] dos: correcto (1,5 s)"
        assert view.render(finished(3, "a", "uno")) == "  [ok] uno: correcto (3,0 s)"

    def test_the_wait_for_the_approval_is_not_counted(self) -> None:
        view = ActivityRenderer()
        view.render(requested(0))
        view.render(at(0.1, ET.PERMISSION_DECIDED, call_id="c1", name="shell", decision="ask"))
        view.render(at(8.1, ET.APPROVAL_RESOLVED, call_id="c1", name="shell", action="approve"))

        assert view.render(finished(9.1)) == "  [ok] shell: correcto (1,1 s)"

    def test_a_finish_without_a_request_has_no_duration(self) -> None:
        assert ActivityRenderer().render(finished(5)) == "  [ok] shell: correcto"

    def test_a_call_id_that_is_not_text_has_no_duration(self) -> None:
        view = ActivityRenderer()
        view.render(at(0, ET.TOOL_REQUESTED, call_id=7, name="shell"))

        line = view.render(at(1, ET.TOOL_FINISHED, call_id=7, name="shell", is_error=False))

        assert line == "  [ok] shell: correcto"

    def test_a_clock_that_goes_backwards_shows_no_duration(self) -> None:
        view = ActivityRenderer()
        view.render(requested(10))

        assert view.render(finished(5)) == "  [ok] shell: correcto"

    def test_a_wait_longer_than_the_run_shows_no_duration(self) -> None:
        view = ActivityRenderer()
        view.render(requested(0))
        view.render(at(0, ET.PERMISSION_DECIDED, call_id="c1", name="shell", decision="ask"))
        view.render(at(5, ET.APPROVAL_RESOLVED, call_id="c1", name="shell", action="reject"))

        assert view.render(finished(3)) == "  [ok] shell: correcto"

    def test_a_finished_call_is_forgotten(self) -> None:
        view = ActivityRenderer()
        view.render(requested(0))
        view.render(finished(1))

        assert view.render(finished(9)) == "  [ok] shell: correcto"

    def test_a_resolution_without_a_question_changes_nothing(self) -> None:
        view = ActivityRenderer()
        view.render(requested(0))
        view.render(at(4, ET.APPROVAL_RESOLVED, call_id="c1", name="shell", action="approve"))

        assert view.render(finished(5)) == "  [ok] shell: correcto (5,0 s)"

    def test_an_error_line_has_no_duration(self) -> None:
        view = ActivityRenderer()
        view.render(requested(0))

        line = view.render(finished(2, is_error=True, category="tool_error"))

        assert line is not None
        assert "2,0 s" not in line

    def test_the_pending_calls_are_bounded(self) -> None:
        view = ActivityRenderer()
        for number in range(MAX_PENDING_CALLS + 10):
            view.render(requested(0, f"c{number}"))

        # the oldest were dropped: no duration; the newest are still matched
        assert view.render(finished(1, "c0")) == "  [ok] shell: correcto"
        newest = f"c{MAX_PENDING_CALLS + 9}"
        assert view.render(finished(1, newest)) == "  [ok] shell: correcto (1,0 s)"

    def test_the_state_is_per_renderer(self) -> None:
        first, second = ActivityRenderer(), ActivityRenderer()
        first.render(requested(0))

        assert second.render(finished(1)) == "  [ok] shell: correcto"


class TestLines:
    def test_the_approval_answer_and_the_compaction_have_a_line(self) -> None:
        view = ActivityRenderer()

        assert view.render(at(0, ET.APPROVAL_RESOLVED, name="shell", action="reject")) == (
            "  [?] shell: rechazado"
        )
        assert view.render(at(0, ET.CONTEXT_COMPACTED, eventos=3)) == (
            "  [~] Contexto compactado: 3 eventos resumidos."
        )

    def test_an_allowed_permission_shows_nothing(self) -> None:
        assert ActivityRenderer().render(at(0, ET.PERMISSION_DECIDED, decision="allow")) is None

    def test_a_type_that_is_not_shown_gives_nothing(self) -> None:
        assert ActivityRenderer().render(at(0, ET.USER_MESSAGE, content=SENTINEL)) is None

    def test_the_arguments_never_appear(self) -> None:
        view = ActivityRenderer()
        line = view.render(at(0, ET.TOOL_REQUESTED, call_id="c", name="shell", arguments=SENTINEL))

        assert line is not None
        assert SENTINEL not in line


class TestPaint:
    def test_a_plain_view_has_no_codes(self) -> None:
        assert ESCAPE not in (ActivityRenderer().render(finished(1)) or "")

    def test_the_painted_line_without_codes_is_the_plain_line(self) -> None:
        plain, painted = ActivityRenderer(), ActivityRenderer(Style(enabled=True))
        events = [
            requested(0),
            finished(1),
            finished(2, is_error=True, category="tool_error"),
            at(3, ET.APPROVAL_RESOLVED, name="shell", action="approve"),
            at(4, ET.CONTEXT_COMPACTED, eventos=1),
            at(5, ET.ASSISTANT_MESSAGE, content="uno\ndos"),
            at(6, ET.LIMIT_REACHED, limit="turns", maximum=3),
        ]

        for event in events:
            expected = plain.render(event)
            shown = painted.render(event)
            assert shown is not None
            assert expected is not None
            assert ESCAPE in shown
            assert re.sub(re.escape(ESCAPE) + r"\[[0-9;]*m", "", shown) == expected

    def test_a_line_without_a_known_marker_is_left_as_it_is(self) -> None:
        painted = ActivityRenderer(Style(enabled=True))
        line = painted.render(at(0, ET.PERMISSION_DECIDED, name="shell", decision="deny"))

        assert line is not None
        assert line.startswith("  ")


class TestAttach:
    def test_the_attached_renderer_shows_the_duration(self) -> None:
        bus, output = InMemoryEventBus(), io.StringIO()
        attach_renderer(bus, output)

        bus.emit(requested(0))
        bus.emit(finished(2))

        assert output.getvalue() == "  [..] shell: ejecutando\n  [ok] shell: correcto (2,0 s)\n"
