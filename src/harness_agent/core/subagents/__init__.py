"""Minimal subagents (HU-09-01, HU-09-03, HU-09-04): the rules of a delegation.

An orchestrator delegates a task to a subagent that works in a child session with an empty context,
its own loop and its own limits, under the same permissions. What comes back is a short structured
result, never the transcript. The public API is exported by ``harness_agent.core``.
"""

from harness_agent.core.subagents.approval import REQUESTER_KEY, SubagentApprover, requester_label
from harness_agent.core.subagents.registry import DELEGATE_TOOL_NAME, RegistryView
from harness_agent.core.subagents.result import (
    INVALID_PROVIDER_RESPONSE,
    INVALID_RESULT,
    LIMIT_REACHED,
    NO_CHILD_SESSION,
    PROVIDER_FAILED,
    RESULT_SCHEMA,
    SUBAGENT_FAILED,
    failure_output,
    parse_result,
    shorten_output,
)
from harness_agent.core.subagents.runner import (
    ChildLoop,
    ChildSessions,
    ChildTurn,
    LoopSubagentRunner,
)
from harness_agent.core.subagents.task import build_task

__all__ = [
    "DELEGATE_TOOL_NAME",
    "REQUESTER_KEY",
    "RESULT_SCHEMA",
    "INVALID_RESULT",
    "PROVIDER_FAILED",
    "INVALID_PROVIDER_RESPONSE",
    "SUBAGENT_FAILED",
    "NO_CHILD_SESSION",
    "LIMIT_REACHED",
    "ChildLoop",
    "ChildSessions",
    "ChildTurn",
    "LoopSubagentRunner",
    "RegistryView",
    "SubagentApprover",
    "build_task",
    "failure_output",
    "parse_result",
    "requester_label",
    "shorten_output",
]
