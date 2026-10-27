"""HARNESS CLI package.

Terminal user interface, interactive console loop, and command-line
entry point. The public API is ``render_event`` (event to text),
``attach_renderer`` (subscribe the terminal to the bus), ``run_cli`` (the input cycle, which
returns the exit code of the session) and ``ConsoleApprover`` (the approval prompt).
"""

from harness_agent.cli.app import attach_renderer, run_cli
from harness_agent.cli.approval import ConsoleApprover
from harness_agent.cli.criteria import CriteriaBoard, attach_criteria_status, criterion_line
from harness_agent.cli.render import render_event

__all__ = [
    "ConsoleApprover",
    "CriteriaBoard",
    "attach_criteria_status",
    "attach_renderer",
    "criterion_line",
    "render_event",
    "run_cli",
]
