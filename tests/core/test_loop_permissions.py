"""Permission decisions and the R-07 invariant of the agentic loop (HU-01-01, US3, T015).

SC-002: the execution counter only advances for a valid call with an explicit ALLOW.
R-07: the policy evaluates the effective validated arguments and the tool runs with
exactly the authorized arguments; later mutations cannot change the authorized operation.
"""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.core.entities import Role, ToolCall
from harness_agent.core.events import EventType
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.interfaces.security import PermissionDecision
from harness_agent.core.loop import TurnStatus
from tests.core.support import call, make_rig, response
from tests.doubles import InMemoryToolRegistry, RecordingTool, ScriptedPolicy

ALLOW = PermissionDecision.ALLOW


def _one_call_script(name: str = "act", **arguments: Any) -> list[ProviderResponse | BaseException]:
    return [response(call("c1", name, **arguments)), ProviderResponse(content="done")]


@pytest.mark.parametrize(
    ("outcome", "expected_prefix", "expected_fragment"),
    [
        (PermissionDecision.DENY, "[permission_denied]", "was denied by the permission policy"),
        (
            PermissionDecision.ASK,
            "[approval_required_unavailable]",
            "resolved as denied",
        ),
        (RuntimeError("policy crashed"), "[permission_denied]", "fail closed"),
        ("allow", "[permission_denied]", "fail closed"),
        (True, "[permission_denied]", "fail closed"),
        (None, "[permission_denied]", "fail closed"),
    ],
)
async def test_anything_other_than_an_explicit_allow_never_executes(
    outcome: Any, expected_prefix: str, expected_fragment: str
) -> None:
    tool = RecordingTool("act")
    rig = make_rig(_one_call_script(), [tool], decisions={"act": outcome})

    result = await rig.run()

    assert result.status is TurnStatus.COMPLETED
    assert tool.executions == []
    message = next(m for m in result.history if m.role is Role.TOOL)
    assert message.tool_result is not None
    assert message.tool_result.is_error and message.tool_result.call_id == "c1"
    assert message.content.startswith(expected_prefix)
    assert expected_fragment in message.content
    assert message.is_external is False
    emitted = {event.type for event in rig.recording_bus.emitted_events}
    assert EventType.APPROVAL_REQUESTED not in emitted
    assert EventType.APPROVAL_RESOLVED not in emitted


async def test_a_tool_the_policy_does_not_know_is_denied_by_default() -> None:
    tool = RecordingTool("act")
    rig = make_rig(_one_call_script(), [tool], decisions={})

    result = await rig.run()

    assert tool.executions == []
    message = next(m for m in result.history if m.role is Role.TOOL)
    assert message.content.startswith("[permission_denied]")


async def test_invalid_arguments_never_consult_the_policy_and_never_execute() -> None:
    tool = RecordingTool("act")
    rig = make_rig(_one_call_script(), [tool])
    rig.registry.validate_error = ValueError("nope")

    await rig.run()

    assert rig.policy.received == [] and tool.executions == []


async def test_allow_executes_exactly_once_per_valid_call() -> None:
    tool = RecordingTool("act")
    script: list[ProviderResponse | BaseException] = [
        response(call("a", "act"), call("b", "act")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool])

    await rig.run()

    assert len(tool.executions) == 2 and len(rig.policy.received) == 2


# --------------------------------------------------------------------------- R-07


async def test_r07_policy_receives_effective_arguments_and_tool_runs_the_authorized_ones() -> None:
    tool = RecordingTool("act")
    rig = make_rig(
        _one_call_script(path="a.txt"),
        [tool],
        normalizer=lambda _name, args: {**args, "encoding": "utf-8"},
    )

    result = await rig.run()

    evaluated = rig.policy.received[0]
    assert (evaluated.id, evaluated.name) == ("c1", "act")
    assert evaluated.arguments == {"path": "a.txt", "encoding": "utf-8"}
    assert tool.executions == [{"path": "a.txt", "encoding": "utf-8"}]
    assert tool.executions[0] is not evaluated.arguments
    assert tool.executions[0] is not rig.registry.returned_dicts[0]
    # The original arguments the model sent stay untouched in the assistant message.
    assistant = next(m for m in result.history if m.role is Role.ASSISTANT)
    assert assistant.tool_calls[0].arguments == {"path": "a.txt"}


async def test_r07_the_original_call_is_never_what_the_policy_evaluates() -> None:
    tool = RecordingTool("act")
    rig = make_rig(_one_call_script(path="a.txt"), [tool])

    result = await rig.run()

    original = next(m for m in result.history if m.role is Role.ASSISTANT).tool_calls[0]
    assert rig.policy.received[0] is not original
    assert rig.policy.received[0].arguments is not original.arguments


async def test_r07_a_policy_that_mutates_what_it_receives_cannot_change_the_execution() -> None:
    class MutatingPolicy(ScriptedPolicy):
        def evaluate(self, call: ToolCall) -> PermissionDecision:
            decision = super().evaluate(call)
            call.arguments["path"] = "/etc/passwd"
            return decision

    tool = RecordingTool("act")
    rig = make_rig(_one_call_script(path="a.txt"), [tool], policy=MutatingPolicy({"act": ALLOW}))

    await rig.run()

    assert tool.executions == [{"path": "a.txt"}]


async def test_r07_mutating_the_validated_dict_or_the_original_call_after_it_changes_nothing() -> (
    None
):
    class TamperingPolicy(ScriptedPolicy):
        def __init__(self, registry: InMemoryToolRegistry, original: dict[str, Any]) -> None:
            super().__init__({"act": ALLOW})
            self._registry = registry
            self._original = original

        def evaluate(self, call: ToolCall) -> PermissionDecision:
            # Something holding references tampers with them while authorization happens.
            self._registry.returned_dicts[0]["path"] = "tampered-validated"
            self._original["path"] = "tampered-original"
            return super().evaluate(call)

    tool = RecordingTool("act")
    original_args = {"path": "a.txt"}
    script: list[ProviderResponse | BaseException] = [
        ProviderResponse(tool_calls=[ToolCall("c1", "act", original_args)]),
        ProviderResponse(content="done"),
    ]
    registry = InMemoryToolRegistry([tool])
    rig = make_rig(
        script,
        [tool],
        registry=registry,
        policy=TamperingPolicy(registry, original_args),
    )

    await rig.run()

    assert tool.executions == [{"path": "a.txt"}]


async def test_r07_a_registry_cannot_mutate_the_arguments_the_model_sent() -> None:
    class MutatingRegistry(InMemoryToolRegistry):
        def validate_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
            args["injected"] = True
            return {"path": "a.txt"}

    tool = RecordingTool("act")
    rig = make_rig(_one_call_script(path="a.txt"), [tool], registry=MutatingRegistry([tool]))

    result = await rig.run()

    assistant = next(m for m in result.history if m.role is Role.ASSISTANT)
    assert assistant.tool_calls[0].arguments == {"path": "a.txt"}
    assert tool.executions == [{"path": "a.txt"}]


async def test_r07_the_effective_arguments_of_one_call_do_not_leak_into_the_next() -> None:
    tool = RecordingTool("act")
    script: list[ProviderResponse | BaseException] = [
        response(call("a", "act", n=1), call("b", "act", n=2)),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool], normalizer=lambda _n, args: {**args, "seen": args["n"]})

    await rig.run()

    assert tool.executions == [{"n": 1, "seen": 1}, {"n": 2, "seen": 2}]
