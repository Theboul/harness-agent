"""HARNESS CLI package.

Terminal user interface, interactive console loop, and command-line
entry point. The public API is ``render_event`` (event to text),
``attach_renderer`` (subscribe the terminal to the bus), ``run_cli`` (the input cycle, which
returns the exit code of the session), ``ConsoleApprover`` (the approval prompt), ``Style`` and
``detect_style`` (optional color), ``ActivityRenderer`` (activity lines with durations) and the text
of the session commands (``SessionRow``, ``ModelView``, ``format_sessions``, ``format_model``,
``format_compaction``, ``format_new_session``).
"""

from harness_agent.cli.activity import ActivityRenderer
from harness_agent.cli.app import attach_renderer, run_cli
from harness_agent.cli.approval import ConsoleApprover
from harness_agent.cli.criteria import CriteriaBoard, attach_criteria_status, criterion_line
from harness_agent.cli.render import render_event
from harness_agent.cli.session_commands import (
    ModelView,
    SessionRow,
    format_compaction,
    format_model,
    format_new_session,
    format_sessions,
)
from harness_agent.cli.style import Style, detect_style

__all__ = [
    "ActivityRenderer",
    "ConsoleApprover",
    "CriteriaBoard",
    "ModelView",
    "SessionRow",
    "Style",
    "attach_criteria_status",
    "attach_renderer",
    "criterion_line",
    "detect_style",
    "format_compaction",
    "format_model",
    "format_new_session",
    "format_sessions",
    "render_event",
    "run_cli",
]
