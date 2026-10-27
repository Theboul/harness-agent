"""Task definition and its Markdown parser (HU-11-01), with its verification commands (HU-11-03).

Only the standard library and ``harness_agent.core`` are used here.
"""

from harness_agent.core.tasks.commands import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    MAX_COMMAND_TEXT_CHARS,
    MAX_COMMAND_TIMEOUT_SECONDS,
    CommandKind,
    TaskCommand,
    commands_notice,
)
from harness_agent.core.tasks.condition import (
    MAX_EXIT_CODE,
    Condition,
    condition_met,
    parse_condition,
)
from harness_agent.core.tasks.definition import (
    MAX_CRITERIA,
    MAX_FIELD_CHARS,
    MAX_SECTION_CHARS,
    MAX_TASK_CHARS,
    CriterionDefinition,
    CriterionKind,
    TaskDefinition,
)
from harness_agent.core.tasks.errors import TaskFormatError
from harness_agent.core.tasks.parser import parse_task

__all__ = [
    "MAX_CRITERIA",
    "MAX_FIELD_CHARS",
    "MAX_SECTION_CHARS",
    "MAX_TASK_CHARS",
    "CriterionDefinition",
    "CriterionKind",
    "TaskDefinition",
    "TaskFormatError",
    "parse_task",
    "MAX_EXIT_CODE",
    "Condition",
    "condition_met",
    "parse_condition",
    "DEFAULT_COMMAND_TIMEOUT_SECONDS",
    "MAX_COMMAND_TEXT_CHARS",
    "MAX_COMMAND_TIMEOUT_SECONDS",
    "CommandKind",
    "TaskCommand",
    "commands_notice",
]
