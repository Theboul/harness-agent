"""Missing collaborators fail closed before anything runs (HU-01-01, US5, T020, SC-008)."""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.core.loop import AgentLoop, MissingDependencyError
from tests.doubles import (
    InMemoryToolRegistry,
    RecordingEventBus,
    ScriptedPolicy,
    ScriptedProvider,
)


def _collaborators() -> dict[str, Any]:
    return {
        "provider": ScriptedProvider([]),
        "registry": InMemoryToolRegistry(),
        "policy": ScriptedPolicy(),
        "bus": RecordingEventBus(),
    }


@pytest.mark.parametrize("missing", ["provider", "registry", "policy", "bus"])
def test_a_missing_collaborator_is_named_and_nothing_runs(missing: str) -> None:
    collaborators = _collaborators()
    provider = collaborators["provider"]
    collaborators[missing] = None

    with pytest.raises(MissingDependencyError, match=missing):
        AgentLoop(**collaborators)

    assert provider.call_count == 0


def test_there_is_no_default_permission_policy() -> None:
    collaborators = _collaborators()
    del collaborators["policy"]

    with pytest.raises(TypeError):
        AgentLoop(**collaborators)
