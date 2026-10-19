"""Provider failures, cancellation and the R-08 precedence rule (HU-01-01, US6, T023).

Five situations that must never be treated as equivalent: an isolated subscriber failure
(HU-01-05, out of the loop), a genuine ``EventBus.emit`` failure (Q4: propagates), a tool
failure (a structured result), a provider failure (an explicit TurnResult) and a
cancellation (propagates as CancelledError).

R-08: the cancellation prevails over a failure while publishing INTERRUPTED. The original
CancelledError is re-raised and the diagnostic of the bus failure travels as a note
(``add_note``); ``__context__`` is deliberately NOT relied upon.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any

import pytest

from harness_agent.core.entities import Message, Role
from harness_agent.core.events import EventType
from harness_agent.core.interfaces.provider import ProviderResponse, ToolDefinition
from harness_agent.core.interfaces.tool import Tool
from harness_agent.core.loop import AgentLoop, InvalidHistoryError, TurnStatus
from tests.core.support import SESSION, Rig, call, make_rig, response
from tests.doubles import (
    BlockingTool,
    FailingEventBus,
    InMemoryToolRegistry,
    RecordingTool,
    ScriptedProvider,
    run_bounded,
)

ET = EventType


async def _cancel_once(task: asyncio.Task[object], started: asyncio.Event) -> None:
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()


async def _cancel_run(rig: Rig, started: asyncio.Event) -> BaseException:
    """Start a turn, cancel it once ``started`` is set and return what it raised."""
    task: asyncio.Task[object] = asyncio.create_task(_as_object(rig.run()))
    await _cancel_once(task, started)
    with pytest.raises(asyncio.CancelledError) as raised:
        await task
    return raised.value


async def _as_object(awaitable: Awaitable[object]) -> object:
    return await awaitable


def _event_types(rig: Rig) -> list[EventType]:
    return [event.type for event in rig.recording_bus.emitted_events]


# ---------------------------------------------------------------- provider failure


async def test_provider_failure_ends_the_turn_explicitly_without_retries() -> None:
    rig = make_rig([RuntimeError("provider down")], [RecordingTool("t")])

    result = await rig.run("task")

    assert result.status is TurnStatus.PROVIDER_FAILED
    assert result.final_response is None
    assert result.error == "RuntimeError: provider down"
    assert rig.provider.call_count == 1  # no retry, no fallback
    events = rig.recording_bus.emitted_events
    assert _event_types(rig) == [ET.USER_MESSAGE, ET.PROVIDER_ERROR]
    assert events[1].payload == {
        "reason": "provider_exception",
        "error_type": "RuntimeError",
        "message": "provider down",
    }
    assert ET.PROVIDER_SWITCHED not in _event_types(rig)
    assert [m.role for m in rig.history] == [Role.USER]


async def test_provider_failure_in_the_middle_runs_nothing_further() -> None:
    tool = RecordingTool("t")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "t")),
        ConnectionError("timeout"),
    ]
    rig = make_rig(script, [tool])

    result = await rig.run()

    assert result.status is TurnStatus.PROVIDER_FAILED
    assert len(tool.executions) == 1
    assert rig.provider.call_count == 2
    assert result.history == tuple(rig.history)


async def test_a_failing_provider_error_event_propagates_chained_to_the_provider_error() -> None:
    bus = FailingEventBus({ET.PROVIDER_ERROR})
    provider_error = RuntimeError("provider down")
    rig = make_rig([provider_error], [], bus=bus)

    with pytest.raises(RuntimeError, match="event bus failure") as raised:
        await rig.run()

    assert raised.value is bus.error
    assert raised.value.__context__ is provider_error
    assert bus.failed_attempts == [ET.PROVIDER_ERROR]


@pytest.mark.parametrize(
    "bad_response",
    [
        pytest.param(
            ProviderResponse(tool_calls=[call("dup", "t"), call("dup", "t")]),
            id="duplicate-ids-in-one-response",
        ),
        pytest.param(ProviderResponse(tool_calls=[call("", "t")]), id="empty-id"),
    ],
)
async def test_an_invalid_provider_response_runs_nothing_and_is_not_recorded(
    bad_response: ProviderResponse,
) -> None:
    tool = RecordingTool("t")
    rig = make_rig([bad_response], [tool], allow_invalid_ids=True)

    result = await rig.run()

    assert result.status is TurnStatus.INVALID_PROVIDER_RESPONSE
    assert result.error
    assert tool.executions == [] and rig.policy.received == []
    assert [m.role for m in rig.history] == [Role.USER]  # the bad response was not added
    events = rig.recording_bus.emitted_events
    assert _event_types(rig) == [ET.USER_MESSAGE, ET.PROVIDER_ERROR]
    assert events[1].payload["reason"] == "invalid_response"


async def test_a_provider_returning_something_else_than_a_response_is_invalid() -> None:
    class WrongTypeProvider(ScriptedProvider):
        async def complete(  # type: ignore[override]
            self, messages: list[Message], tools: list[ToolDefinition] | None = None
        ) -> object:
            return "just text"

    rig = make_rig([], [])
    rig.loop = AgentLoop(WrongTypeProvider([]), rig.registry, rig.policy, rig.bus)

    result = await run_bounded(rig.loop.run_turn(session_id=SESSION, task="t", history=[]))

    assert result.status is TurnStatus.INVALID_PROVIDER_RESPONSE
    assert result.error is not None and "str" in result.error


async def test_a_tool_call_of_the_wrong_type_in_a_response_is_invalid() -> None:
    bad = ProviderResponse(tool_calls=["not-a-tool-call"])  # type: ignore[list-item]
    rig = make_rig([bad], [RecordingTool("t")], allow_invalid_ids=True)

    result = await rig.run()

    assert result.status is TurnStatus.INVALID_PROVIDER_RESPONSE
    assert rig.recording_bus.emitted_events[-1].type is ET.PROVIDER_ERROR


# ------------------------------------------------------------------- cancellation


async def test_cancellation_during_the_provider_call_propagates_with_one_interrupted() -> None:
    tool = RecordingTool("t")
    rig = make_rig([ProviderResponse(content="never")], [tool], block_on_call=0)

    raised = await _cancel_run(rig, rig.provider.blocked)

    assert isinstance(raised, asyncio.CancelledError)
    assert not getattr(raised, "__notes__", [])  # the bus did not fail: no diagnostic note
    assert _event_types(rig) == [ET.USER_MESSAGE, ET.INTERRUPTED]
    assert rig.recording_bus.emitted_events[1].payload == {
        "phase": "provider_call",
        "call_id": None,
    }
    assert rig.provider.call_count == 1 and tool.executions == []
    assert [m.role for m in rig.history] == [Role.USER]


async def test_cancellation_during_a_tool_leaves_calls_without_fabricated_results() -> None:
    blocking = BlockingTool("slow")
    after = RecordingTool("after")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "slow"), call("c2", "after")),
        ProviderResponse(content="never"),
    ]
    rig = make_rig(script, [blocking, after])

    raised = await _cancel_run(rig, blocking.started)

    assert isinstance(raised, asyncio.CancelledError)
    assert _event_types(rig).count(ET.INTERRUPTED) == 1
    interrupted = next(e for e in rig.recording_bus.emitted_events if e.type is ET.INTERRUPTED)
    assert interrupted.payload == {"phase": "tool_execution", "call_id": "c1"}
    assert after.executions == [] and rig.provider.call_count == 1
    assert [m.role for m in rig.history] == [Role.USER, Role.ASSISTANT]  # no ToolResult invented
    assert ET.TOOL_FINISHED not in _event_types(rig)


async def test_the_history_left_by_a_cancelled_turn_is_rejected_by_the_next_turn() -> None:
    blocking = BlockingTool("slow")
    script: list[ProviderResponse | BaseException] = [response(call("c1", "slow"))]
    rig = make_rig(script, [blocking])
    await _cancel_run(rig, blocking.started)
    length = len(rig.history)

    with pytest.raises(InvalidHistoryError):
        await rig.run("again")

    assert len(rig.history) == length


# ----------------------------------------------------------------------------- R-08


@pytest.mark.parametrize("phase", ["provider_call", "tool_execution"])
async def test_r08_cancellation_prevails_over_a_failing_interrupted_event(phase: str) -> None:
    bus = FailingEventBus({ET.INTERRUPTED}, RuntimeError("event bus failure"))
    blocking = BlockingTool("slow")
    if phase == "provider_call":
        rig = make_rig([ProviderResponse(content="never")], [blocking], bus=bus, block_on_call=0)
        started = rig.provider.blocked
    else:
        rig = make_rig([response(call("c1", "slow"))], [blocking], bus=bus)
        started = blocking.started

    raised = await _cancel_run(rig, started)

    assert isinstance(raised, asyncio.CancelledError)  # the ORIGINAL cancellation, not the bus
    assert not isinstance(raised, RuntimeError)
    notes = getattr(raised, "__notes__", [])
    assert len(notes) == 1 and "RuntimeError" in notes[0] and "event bus failure" in notes[0]
    assert bus.failed_attempts == [ET.INTERRUPTED]  # one attempt, no retry
    assert rig.provider.call_count == 1
    assert len(blocking.executions) == (1 if phase == "tool_execution" else 0)
    assert not any(m.role is Role.TOOL for m in rig.history)  # never a ToolResult


async def test_r08_contrast_an_ordinary_emit_failure_propagates_as_the_bus_error() -> None:
    bus = FailingEventBus({ET.TOOL_REQUESTED})
    tool = RecordingTool("t")
    rig = make_rig([response(call("c1", "t"))], [tool], bus=bus)

    with pytest.raises(RuntimeError, match="event bus failure") as raised:
        await rig.run()

    assert not isinstance(raised.value, asyncio.CancelledError)
    assert raised.value is bus.error and tool.executions == []


async def test_cancellation_is_never_swallowed_into_a_tool_result() -> None:
    blocking = BlockingTool("slow")
    rig = make_rig([response(call("c1", "slow"))], [blocking])

    raised = await _cancel_run(rig, blocking.started)

    assert isinstance(raised, asyncio.CancelledError)
    assert all(m.tool_result is None for m in rig.history)


async def test_failures_and_cancellation_write_nothing_to_the_console(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rig = make_rig([RuntimeError("down")], [])
    await rig.run()
    blocking = BlockingTool("slow")
    cancelled = make_rig([response(call("c1", "slow"))], [blocking])
    await _cancel_run(cancelled, blocking.started)

    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


# ------------------------------------------- T033: registry failures are not provider failures


class _ListFailingRegistry(InMemoryToolRegistry):
    """Registry whose ``list()`` raises: a structural failure of the loop's own collaborator."""

    def __init__(self, error: Exception) -> None:
        super().__init__([RecordingTool("t")])
        self.list_error: Exception | None = error

    def list(self) -> list[Tool]:
        if self.list_error is not None:
            raise self.list_error
        return super().list()


class _SchemaFailingTool(RecordingTool):
    """Tool whose declaration cannot be read while building the ToolDefinition."""

    @property
    def schema(self) -> dict[str, Any]:
        raise RuntimeError("schema unavailable")


async def test_t033_a_registry_failure_is_structural_not_a_provider_failure() -> None:
    registry = _ListFailingRegistry(RuntimeError("registry down"))
    rig = make_rig([ProviderResponse(content="never")], [], registry=registry)

    with pytest.raises(RuntimeError, match="registry down"):
        await rig.run("task")

    assert rig.provider.call_count == 0  # the provider was never queried
    assert ET.PROVIDER_ERROR not in _event_types(rig)
    assert _event_types(rig) == [ET.USER_MESSAGE]  # nothing else was published
    assert rig.policy.received == [] and rig.provider.exhausted is False


async def test_t033_the_failed_turn_keeps_the_user_message_and_the_next_turn_can_run() -> None:
    registry = _ListFailingRegistry(RuntimeError("registry down"))
    rig = make_rig([ProviderResponse(content="recovered")], [], registry=registry)

    with pytest.raises(RuntimeError):
        await rig.run("first")

    # Not rolled back and not lost: the user message stays; a USER-ending history is valid.
    assert [(m.role, m.content) for m in rig.history] == [(Role.USER, "first")]
    registry.list_error = None  # the registry recovers

    result = await rig.run("second")

    assert result.status is TurnStatus.COMPLETED
    assert [(m.role, m.content) for m in rig.history] == [
        (Role.USER, "first"),
        (Role.USER, "second"),
        (Role.ASSISTANT, "recovered"),
    ]


async def test_t033_a_tool_whose_declaration_cannot_be_read_is_also_structural() -> None:
    rig = make_rig([ProviderResponse(content="never")], [_SchemaFailingTool("t")])

    with pytest.raises(RuntimeError, match="schema unavailable"):
        await rig.run("task")

    assert rig.provider.call_count == 0
    assert ET.PROVIDER_ERROR not in _event_types(rig)


async def test_t033_a_registry_failure_in_a_later_iteration_stops_before_the_next_query() -> None:
    tool = RecordingTool("t")
    registry = InMemoryToolRegistry([tool])
    calls_to_list = 0
    original_list = registry.list

    def flaky_list() -> list[Tool]:
        nonlocal calls_to_list
        calls_to_list += 1
        if calls_to_list == 2:
            raise RuntimeError("registry lost")
        return original_list()

    registry.list = flaky_list  # type: ignore[method-assign]
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "t")),
        ProviderResponse(content="never"),
    ]
    rig = make_rig(script, [tool], registry=registry)

    with pytest.raises(RuntimeError, match="registry lost"):
        await rig.run()

    assert rig.provider.call_count == 1  # the second query never happened
    assert len(tool.executions) == 1
    assert ET.PROVIDER_ERROR not in _event_types(rig)
    # The executed call and its result are in the history (nothing lost, nothing repeated).
    assert [m.role for m in rig.history] == [Role.USER, Role.ASSISTANT, Role.TOOL]


async def test_t033_a_genuine_provider_failure_keeps_its_classification() -> None:
    rig = make_rig([RuntimeError("provider down")], [RecordingTool("t")])

    result = await rig.run("task")

    assert result.status is TurnStatus.PROVIDER_FAILED
    assert _event_types(rig) == [ET.USER_MESSAGE, ET.PROVIDER_ERROR]
