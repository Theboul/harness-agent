"""Task definition and its Markdown parser (HU-11-01).

Only the standard library and ``harness_agent.core`` are used here.
"""

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
]
