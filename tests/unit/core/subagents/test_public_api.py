"""Public API of ``core.subagents`` and its re-export from ``core`` (HU-09-01 / T007)."""

from __future__ import annotations

import harness_agent.core as core
import harness_agent.core.subagents as subagents

API = {
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
}


def test_the_package_exports_exactly_the_public_api() -> None:
    assert set(subagents.__all__) == API
    assert len(subagents.__all__) == len(API)  # no repeated name
    for name in subagents.__all__:
        assert hasattr(subagents, name), name


def test_the_core_re_exports_the_same_objects() -> None:
    for name in API:
        assert name in core.__all__, name
        assert getattr(core, name) is getattr(subagents, name), name
