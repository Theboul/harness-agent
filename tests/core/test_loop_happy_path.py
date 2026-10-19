"""AC-01 and the happy path of the agentic loop (HU-01-01, US1, T007).

AC-01 (literal): "Dado un guion de tres pasos con herramientas, cuando el bucle corre,
entonces ejecuta las tres herramientas en orden y termina cuando el modelo no pide mas."
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from harness_agent.core.entities import Message, Role, TokenUsage, ToolCall, ToolResult
from harness_agent.core.interfaces.provider import (
    ProviderResponse,
    ToolDefinition,
)
from harness_agent.core.loop import AgentLoop, TurnStatus
from tests.core.support import SESSION, call, make_rig, response
from tests.doubles import (
    DummyProvider,
    FailingTool,
    InMemoryToolRegistry,
    RecordingEventBus,
    RecordingTool,
    ScriptedPolicy,
    ScriptedProvider,
    run_bounded,
)


def _three_step_rig(order: list[str]) -> tuple[Any, list[RecordingTool]]:
    class OrderedTool(RecordingTool):
        async def run(self, args: dict[str, Any]) -> Any:
            order.append(self.name)
            return await super().run(args)

    tools = [OrderedTool(f"step_{i}", content=f"result-{i}") for i in (1, 2, 3)]
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "step_1", n=1)),
        response(call("c2", "step_2", n=2)),
        response(call("c3", "step_3", n=3)),
        ProviderResponse(content="all done"),
    ]
    return make_rig(script, list(tools)), list(tools)


@pytest.mark.parametrize("repetition", range(20))
async def test_ac01_three_tools_run_in_order_and_loop_stops_when_model_asks_no_more(
    repetition: int,
) -> None:
    order: list[str] = []
    rig, tools = _three_step_rig(order)

    result = await rig.run("run the script")

    assert result.status is TurnStatus.COMPLETED
    assert result.final_response == "all done"
    assert order == ["step_1", "step_2", "step_3"]
    assert [len(tool.executions) for tool in tools] == [1, 1, 1]
    assert rig.provider.call_count == 4
    roles = [message.role for message in result.history]
    assert roles == [
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
        Role.ASSISTANT,
        Role.TOOL,
        Role.ASSISTANT,
        Role.TOOL,
        Role.ASSISTANT,
    ]
    tool_messages = [m for m in result.history if m.role is Role.TOOL]
    assert [m.tool_result.call_id for m in tool_messages if m.tool_result] == ["c1", "c2", "c3"]
    assert [m.content for m in tool_messages] == ["result-1", "result-2", "result-3"]
    assert result.history == tuple(rig.history)


async def test_text_together_with_tool_calls_is_not_a_final_answer() -> None:
    tool = RecordingTool("step_1")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "step_1"), content="let me check"),
        ProviderResponse(content="finished"),
    ]
    rig = make_rig(script, [tool])

    result = await rig.run()

    assert result.status is TurnStatus.COMPLETED
    assert result.final_response == "finished"
    assert len(tool.executions) == 1
    assistant = [m for m in result.history if m.role is Role.ASSISTANT]
    assert assistant[0].content == "let me check"
    assert assistant[0].tool_calls[0].id == "c1"


async def test_several_calls_in_one_response_run_in_order_one_result_each() -> None:
    first = RecordingTool("first", content="one")
    broken = FailingTool("broken", content="it failed")
    last = RecordingTool("last", content="three")
    script: list[ProviderResponse | BaseException] = [
        response(call("a", "first"), call("b", "broken"), call("c", "last")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [first, broken, last])

    result = await rig.run()

    assert result.status is TurnStatus.COMPLETED
    tool_messages = [m for m in result.history if m.role is Role.TOOL]
    assert [m.tool_result.call_id for m in tool_messages if m.tool_result] == ["a", "b", "c"]
    assert [m.tool_result.is_error for m in tool_messages if m.tool_result] == [False, True, False]
    assert len(first.executions) == len(broken.executions) == len(last.executions) == 1
    assert rig.provider.call_count == 2


async def test_each_query_receives_a_copy_of_the_history_not_the_loop_list() -> None:
    tool = RecordingTool("step_1")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "step_1")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool])

    await rig.run("hello")

    assert [len(snapshot) for snapshot in rig.provider.received] == [1, 3]
    assert rig.provider.received[0][0] == Message(Role.USER, "hello")
    assert all(snapshot is not rig.history for snapshot in rig.provider.received)


async def test_a_provider_that_mutates_its_messages_cannot_alter_the_callers_history() -> None:
    class MutatingProvider(ScriptedProvider):
        async def complete(
            self, messages: list[Message], tools: list[ToolDefinition] | None = None
        ) -> ProviderResponse:
            result = await super().complete(messages, tools)
            messages.clear()
            return result

    rig = make_rig([], [])
    rig.loop = AgentLoop(
        MutatingProvider([ProviderResponse(content="ok")]),
        rig.registry,
        rig.policy,
        rig.bus,
    )

    result = await run_bounded(rig.loop.run_turn(session_id=SESSION, task="t", history=rig.history))

    assert result.status is TurnStatus.COMPLETED
    assert [m.role for m in rig.history] == [Role.USER, Role.ASSISTANT]


async def test_tool_definitions_come_from_the_registered_tools() -> None:
    schema = {"type": "object", "properties": {"path": {"type": "string"}}}
    tool = RecordingTool("read", description="Reads a file", schema=schema)
    rig = make_rig([ProviderResponse(content="done")], [tool])

    await rig.run()

    assert rig.provider.received_tools == [
        [ToolDefinition(name="read", description="Reads a file", parameters=schema)]
    ]


async def test_a_plain_real_contract_provider_works_without_adaptation() -> None:
    provider = DummyProvider()
    loop = AgentLoop(provider, InMemoryToolRegistry(), ScriptedPolicy(), RecordingEventBus())
    history: list[Message] = []

    result = await run_bounded(loop.run_turn(session_id=SESSION, task="hi", history=history))

    assert result.status is TurnStatus.COMPLETED
    assert result.final_response == "Dummy response from model"


async def test_unknown_tool_is_a_structured_error_and_never_reaches_policy_or_execution() -> None:
    tool = RecordingTool("known")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "ghost")),
        ProviderResponse(content="recovered"),
    ]
    rig = make_rig(script, [tool])

    result = await rig.run()

    assert result.status is TurnStatus.COMPLETED
    assert rig.policy.received == [] and tool.executions == []
    tool_message = next(m for m in result.history if m.role is Role.TOOL)
    assert tool_message.tool_result is not None
    assert tool_message.tool_result.is_error and tool_message.tool_result.call_id == "c1"
    assert tool_message.content.startswith("[unknown_tool]") and "ghost" in tool_message.content


async def test_rejected_arguments_are_a_structured_error_and_skip_policy_and_execution() -> None:
    tool = RecordingTool("known")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "known", bad=True)),
        ProviderResponse(content="recovered"),
    ]
    rig = make_rig(script, [tool])
    rig.registry.validate_error = ValueError("missing required field 'path'")

    result = await rig.run()

    assert rig.policy.received == [] and tool.executions == []
    tool_message = next(m for m in result.history if m.role is Role.TOOL)
    assert tool_message.tool_result is not None and tool_message.tool_result.is_error
    assert tool_message.content.startswith("[invalid_arguments]")
    assert "missing required field 'path'" in tool_message.content


async def test_policy_sees_the_effective_arguments_with_the_same_id_and_name() -> None:
    tool = RecordingTool("known")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "known", path="a.txt")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool], normalizer=lambda _n, args: {**args, "mode": "text"})

    await rig.run()

    assert len(rig.policy.received) == 1
    evaluated = rig.policy.received[0]
    assert (evaluated.id, evaluated.name) == ("c1", "known")
    assert evaluated.arguments == {"path": "a.txt", "mode": "text"}
    assert tool.executions == [{"path": "a.txt", "mode": "text"}]


# ------------------------------------ T034: the provider gets a deep copy of the history


class _MutatingProvider(ScriptedProvider):
    """Defective provider that mutates what it receives (nested arguments and the list)."""

    def __init__(self, script: list[ProviderResponse | BaseException]) -> None:
        super().__init__(script)
        self.snapshots: list[list[Message]] = []

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        # Keep what it was handed *before* misbehaving, then tamper with everything reachable.
        self.snapshots.append(copy.deepcopy(messages))
        for message in messages:
            for tool_call in message.tool_calls:
                tool_call.arguments["path"] = "/etc/passwd"
                tool_call.arguments.setdefault("nested", {})["injected"] = True
        messages.append(Message(Role.USER, "injected by the provider"))
        return await super().complete(messages, tools)


def _history_with_nested_arguments() -> list[Message]:
    return [
        Message(Role.SYSTEM, "system prompt"),
        Message(Role.USER, "earlier task"),
        Message(
            Role.ASSISTANT,
            "reading",
            (ToolCall("old-1", "t", {"path": "a.txt", "nested": {"keep": [1, 2, 3]}}),),
            usage=TokenUsage(input_tokens=11, output_tokens=7),
        ),
        Message(
            Role.TOOL,
            "file body",
            tool_result=ToolResult("old-1", "file body"),
            is_external=True,
        ),
        Message(Role.ASSISTANT, "done earlier"),
    ]


async def test_t034_a_provider_that_mutates_its_input_cannot_alter_the_callers_history() -> None:
    history = _history_with_nested_arguments()
    original = copy.deepcopy(history)
    provider = _MutatingProvider([ProviderResponse(content="answer")])
    rig = make_rig([], [RecordingTool("t")], history=history)
    rig.loop = AgentLoop(provider, rig.registry, rig.policy, rig.bus)

    result = await run_bounded(
        rig.loop.run_turn(session_id=SESSION, task="new task", history=history),
        provider=provider,
    )

    assert result.status is TurnStatus.COMPLETED
    # Earlier messages are exactly as the caller had them; only the loop's own additions follow.
    assert history[: len(original)] == original
    assert history[0].tool_calls == () and history[2].tool_calls[0].arguments == {
        "path": "a.txt",
        "nested": {"keep": [1, 2, 3]},
    }
    assert [m.role for m in history[len(original) :]] == [Role.USER, Role.ASSISTANT]
    assert history[len(original)].content == "new task"  # not the provider's injected message


async def test_t034_the_provider_receives_equal_values_with_canonical_types_preserved() -> None:
    history = _history_with_nested_arguments()
    original = copy.deepcopy(history)
    provider = _MutatingProvider([ProviderResponse(content="answer")])
    rig = make_rig([], [RecordingTool("t")], history=history)
    rig.loop = AgentLoop(provider, rig.registry, rig.policy, rig.bus)

    await run_bounded(
        rig.loop.run_turn(session_id=SESSION, task="new task", history=history),
        provider=provider,
    )

    received = provider.snapshots[0]
    assert received[: len(original)] == original  # equal values before the tampering
    assert received[-1] == Message(Role.USER, "new task")
    assistant = received[2]
    assert assistant.usage is not None and assistant.usage.total_tokens == 18
    assert isinstance(assistant.tool_calls, tuple)
    assert received[3].tool_result is not None and received[3].is_external is True
    assert received[3].role is Role.TOOL


async def test_t034_every_query_gets_a_fresh_copy_so_tampering_does_not_leak_forward() -> None:
    tool = RecordingTool("t")
    history = _history_with_nested_arguments()
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "t", path="a.txt")),
        ProviderResponse(content="done"),
    ]
    provider = _MutatingProvider(script)
    rig = make_rig([], [tool], history=history)
    rig.loop = AgentLoop(provider, rig.registry, rig.policy, rig.bus)

    result = await run_bounded(
        rig.loop.run_turn(session_id=SESSION, task="go", history=history),
        provider=provider,
    )

    assert result.status is TurnStatus.COMPLETED
    assert len(provider.snapshots) == 2
    # The first query tampered with the old call; the second one was built again from the
    # caller's history, so it still shows the arguments the model originally asked for.
    for snapshot in provider.snapshots:
        old_call = snapshot[2].tool_calls[0]
        assert old_call.arguments == {"path": "a.txt", "nested": {"keep": [1, 2, 3]}}
    assert tool.executions == [{"path": "a.txt"}]


async def test_t034_a_provider_keeping_a_reference_to_its_response_cannot_rewrite_the_history() -> (
    None
):
    arguments: dict[str, Any] = {"path": "a.txt", "nested": {"keep": [1]}}
    scripted_call = call("c1", "t")
    object.__setattr__(scripted_call, "arguments", arguments)
    script: list[ProviderResponse | BaseException] = [
        ProviderResponse(tool_calls=[scripted_call]),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [RecordingTool("t")])

    await rig.run("go")
    arguments["path"] = "/etc/passwd"  # the provider keeps its object and mutates it later
    arguments["nested"]["keep"].append(99)

    recorded = next(m for m in rig.history if m.role is Role.ASSISTANT).tool_calls[0]
    assert recorded.arguments == {"path": "a.txt", "nested": {"keep": [1]}}
