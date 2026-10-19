"""History ownership, multi-turn continuity and canonical validity (HU-01-01, US5, T020).

The canonical oracle of HU-07-01 (``adapters/converters``) is used here, in tests only: the
core never imports it (FR-032). Every history the provider receives must be accepted by it
and convert cleanly for both wire formats (SC-005).
"""

from __future__ import annotations

import pytest

from harness_agent.adapters.converters import to_anthropic_payload, to_openai_messages
from harness_agent.adapters.converters._validation import (
    validate_canonical_messages,
    validate_tool_correlation,
)
from harness_agent.core.entities import Message, Role, ToolCall, ToolResult
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.loop import AgentLoop, InvalidHistoryError, TurnStatus
from tests.core.support import SESSION, call, make_rig, response
from tests.doubles import RecordingTool


def _assert_canonical(messages: list[Message]) -> None:
    validate_canonical_messages(messages)
    validate_tool_correlation(messages)
    to_openai_messages(messages)
    to_anthropic_payload(messages)


async def test_history_is_append_only_and_tool_content_matches_the_result() -> None:
    tool = RecordingTool("step_1", content="payload")
    prior = [Message(Role.SYSTEM, "be helpful")]
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "step_1")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool], history=prior)
    before = list(prior)

    result = await rig.run("go")

    assert rig.history[: len(before)] == before
    assert all(a is b for a, b in zip(before, rig.history, strict=False))
    assert result.history == tuple(rig.history)
    for message in rig.history:
        if message.tool_result is not None:
            assert message.content == message.tool_result.content


async def test_two_turns_over_the_same_list_keep_order_and_id_correlation() -> None:
    tool = RecordingTool("step_1")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "step_1")),
        ProviderResponse(content="first answer"),
        response(call("c2", "step_1")),
        ProviderResponse(content="second answer"),
    ]
    rig = make_rig(script, [tool], history=[Message(Role.SYSTEM, "sys")])

    first = await rig.run("question one")
    length_after_first = len(rig.history)
    second = await rig.run("question two")

    assert first.final_response == "first answer" and second.final_response == "second answer"
    assert rig.history[:length_after_first] == list(first.history)
    assert [m.role for m in rig.history] == [
        Role.SYSTEM,
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
        Role.ASSISTANT,
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
        Role.ASSISTANT,
    ]
    ids = [m.tool_result.call_id for m in rig.history if m.tool_result is not None]
    assert ids == ["c1", "c2"]
    for snapshot in rig.provider.received:
        _assert_canonical(snapshot)
    _assert_canonical(rig.history)


async def test_a_multi_turn_history_is_not_assumed_to_contain_only_system_messages() -> None:
    rig = make_rig(
        [ProviderResponse(content="ok")],
        [],
        history=[
            Message(Role.SYSTEM, "sys"),
            Message(Role.USER, "earlier question"),
            Message(Role.ASSISTANT, "earlier answer"),
        ],
    )

    result = await rig.run("follow-up")

    assert result.status is TurnStatus.COMPLETED
    assert len(result.history) == 5


@pytest.mark.parametrize(
    "bad_history",
    [
        pytest.param(
            [Message(Role.USER, "hi"), Message(Role.SYSTEM, "late system")],
            id="system-after-non-system",
        ),
        pytest.param(
            [Message(Role.ASSISTANT, "", (ToolCall("c1", "t"),))],
            id="pending-calls-without-results",
        ),
        pytest.param(
            [
                Message(Role.ASSISTANT, "", (ToolCall("c1", "t"), ToolCall("c2", "t"))),
                Message(Role.TOOL, "r", tool_result=ToolResult("c1", "r")),
            ],
            id="partial-results",
        ),
        pytest.param(
            [
                Message(Role.ASSISTANT, "", (ToolCall("c1", "t"),)),
                Message(Role.TOOL, "r", tool_result=ToolResult("c1", "r")),
                Message(Role.ASSISTANT, "", (ToolCall("c1", "t"),)),
                Message(Role.TOOL, "r", tool_result=ToolResult("c1", "r")),
            ],
            id="repeated-call-id",
        ),
        pytest.param(
            [Message(Role.ASSISTANT, "", (ToolCall("", "t"),))],
            id="empty-call-id",
        ),
        pytest.param(
            [
                Message(Role.ASSISTANT, "", (ToolCall("c1", "t"),)),
                Message(Role.USER, "interleaved"),
                Message(Role.TOOL, "r", tool_result=ToolResult("c1", "r")),
            ],
            id="non-tool-message-while-calls-are-pending",
        ),
        pytest.param(
            [Message(Role.USER, "x", (ToolCall("c1", "t"),))],
            id="tool-calls-on-a-user-message",
        ),
        pytest.param(
            [Message(Role.USER, "x", tool_result=ToolResult("c1", "r"))],
            id="tool-result-on-a-user-message",
        ),
        pytest.param(
            [
                Message(Role.ASSISTANT, "", (ToolCall("c1", "t"),)),
                Message(Role.TOOL, "no result attached"),
            ],
            id="tool-message-without-result",
        ),
        pytest.param(
            [Message(Role.TOOL, "orphan", tool_result=ToolResult("zz", "orphan"))],
            id="orphan-result",
        ),
    ],
)
async def test_an_invalid_initial_history_fails_before_any_effect(
    bad_history: list[Message],
) -> None:
    tool = RecordingTool("t")
    rig = make_rig([ProviderResponse(content="never asked")], [tool], history=list(bad_history))

    with pytest.raises(InvalidHistoryError):
        await rig.run()

    assert rig.history == bad_history  # nothing added
    assert rig.recording_bus.emitted_events == []  # nothing published
    assert rig.provider.call_count == 0 and tool.executions == []


async def test_results_in_any_order_within_a_call_group_are_accepted_like_the_canonical_rules() -> (
    None
):
    history = [
        Message(Role.ASSISTANT, "", (ToolCall("c1", "t"), ToolCall("c2", "t"))),
        Message(Role.TOOL, "r2", tool_result=ToolResult("c2", "r2")),
        Message(Role.TOOL, "r1", tool_result=ToolResult("c1", "r1")),
    ]
    _assert_canonical(history)  # the HU-07-01 oracle accepts it, so the loop must too
    rig = make_rig([ProviderResponse(content="ok")], [], history=history)

    result = await rig.run()

    assert result.status is TurnStatus.COMPLETED


async def test_a_response_repeating_an_id_already_in_the_history_is_invalid() -> None:
    tool = RecordingTool("step_1")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "step_1")),
        ProviderResponse(content="first"),
        response(call("c1", "step_1")),  # id reused in the second turn
    ]
    rig = make_rig(script, [tool], allow_invalid_ids=True)
    await rig.run("one")
    length = len(rig.history)

    second = await rig.run("two")

    assert second.status is TurnStatus.INVALID_PROVIDER_RESPONSE
    assert len(tool.executions) == 1  # the repeated call never ran
    assert len(rig.history) == length + 1  # only the USER of the second turn was added
    _assert_canonical(rig.history)


async def test_the_next_turn_after_a_provider_failure_is_accepted() -> None:
    script: list[ProviderResponse | BaseException] = [
        RuntimeError("provider down"),
        ProviderResponse(content="back"),
    ]
    rig = make_rig(script, [])

    failed = await rig.run("first")
    recovered = await rig.run("second")

    assert failed.status is TurnStatus.PROVIDER_FAILED
    assert recovered.status is TurnStatus.COMPLETED
    _assert_canonical(rig.history)


def test_the_loop_instance_keeps_no_per_turn_state() -> None:
    rig = make_rig([], [])
    assert isinstance(rig.loop, AgentLoop)
    assert not [
        name for name in vars(rig.loop) if name not in {"_provider", "_registry", "_policy", "_bus"}
    ]
    assert SESSION  # the session id is only an opaque label supplied per turn
