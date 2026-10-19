"""AC-02 and tool failure handling of the agentic loop (HU-01-01, US2, T013).

AC-02 (literal): "Dado una herramienta que falla, cuando el bucle recibe el error, entonces
lo devuelve al modelo como resultado estructurado y continua."
"""

from __future__ import annotations

from harness_agent.core.entities import Role, ToolResult
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.loop import TurnStatus
from tests.core.support import call, make_rig, response
from tests.doubles import FailingTool, RaisingTool, RecordingTool


async def test_ac02_failing_tool_error_reaches_the_model_and_the_loop_continues() -> None:
    first = RecordingTool("step_1", content="first ok")
    failing = FailingTool("step_2", content="file not found: missing.txt")
    last = RecordingTool("step_3", content="third ok")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "step_1")),
        response(call("c2", "step_2")),
        response(call("c3", "step_3")),
        ProviderResponse(content="recovered and finished"),
    ]
    rig = make_rig(script, [first, failing, last])

    result = await rig.run()

    assert result.status is TurnStatus.COMPLETED
    assert result.final_response == "recovered and finished"
    assert len(last.executions) == 1
    # The model received the structured error before deciding its next step.
    seen_by_model = rig.provider.received[2][-1]
    assert seen_by_model.role is Role.TOOL
    assert seen_by_model.tool_result == ToolResult("c2", "file not found: missing.txt", True)
    assert seen_by_model.content == "file not found: missing.txt"


async def test_tool_exception_becomes_a_structured_error_without_traceback() -> None:
    tool = RaisingTool("explode", error=ValueError("kaput"))
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "explode")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool])

    result = await rig.run()

    assert result.status is TurnStatus.COMPLETED
    message = next(m for m in result.history if m.role is Role.TOOL)
    assert message.tool_result == ToolResult(
        "c1", "[tool_exception] Tool 'explode' raised ValueError: kaput", True
    )
    assert "Traceback" not in message.content
    assert message.is_external is True


async def test_long_exception_messages_are_bounded() -> None:
    tool = RaisingTool("explode", error=RuntimeError("x" * 2000))
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "explode")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool])

    result = await rig.run()

    message = next(m for m in result.history if m.role is Role.TOOL)
    assert len(message.content) < 700 and message.content.endswith("...")


async def test_a_value_that_is_not_a_tool_result_is_a_structured_error() -> None:
    tool = RecordingTool("odd", raw_result="plain string")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "odd")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool])

    result = await rig.run()

    assert result.status is TurnStatus.COMPLETED
    message = next(m for m in result.history if m.role is Role.TOOL)
    assert message.tool_result is not None and message.tool_result.is_error
    assert message.tool_result.call_id == "c1"
    assert message.content == "[tool_exception] Tool 'odd' returned an invalid result (str)."


async def test_the_call_id_of_the_request_is_forced_on_the_result() -> None:
    tool = RecordingTool("liar", result_call_id="somebody-elses-id", content="payload")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "liar")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool])

    result = await rig.run()

    message = next(m for m in result.history if m.role is Role.TOOL)
    assert message.tool_result is not None
    assert message.tool_result.call_id == "c1"
    assert message.tool_result.content == "payload"


async def test_one_failure_among_several_calls_does_not_skip_the_others() -> None:
    boom = RaisingTool("boom")
    after = RecordingTool("after", content="still ran")
    script: list[ProviderResponse | BaseException] = [
        response(call("a", "boom"), call("b", "after")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [boom, after])

    result = await rig.run()

    tool_results = [m.tool_result for m in result.history if m.tool_result is not None]
    assert [r.call_id for r in tool_results] == ["a", "b"]
    assert [r.is_error for r in tool_results] == [True, False]
    assert len(after.executions) == 1


async def test_tool_output_is_not_truncated_by_the_loop() -> None:
    big = "y" * 5000
    tool = RecordingTool("big", content=big)
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "big")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool])

    result = await rig.run()

    message = next(m for m in result.history if m.role is Role.TOOL)
    assert message.content == big


async def test_is_external_marks_tool_originated_content_only() -> None:
    ok = RecordingTool("ok_tool")
    bad = FailingTool("bad_tool")
    script: list[ProviderResponse | BaseException] = [
        response(call("a", "ok_tool"), call("b", "bad_tool"), call("c", "ghost")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [ok, bad])

    result = await rig.run()

    flags = {m.tool_result.call_id: m.is_external for m in result.history if m.tool_result}
    assert flags == {"a": True, "b": True, "c": False}
    unknown = next(m for m in result.history if m.tool_result and m.tool_result.call_id == "c")
    assert unknown.content.startswith("[unknown_tool]") and "ghost" in unknown.content


async def test_a_registry_that_raises_on_lookup_is_an_unknown_tool_error() -> None:
    tool = RecordingTool("known")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "known")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool])
    rig.registry.get_error = RuntimeError("registry offline")

    result = await rig.run()

    message = next(m for m in result.history if m.role is Role.TOOL)
    assert message.content.startswith("[unknown_tool]") and tool.executions == []


async def test_validate_args_returning_a_non_dict_is_rejected_fail_closed() -> None:
    tool = RecordingTool("known")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "known")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool])
    rig.registry.validate_return = ["not", "a", "dict"]

    result = await rig.run()

    message = next(m for m in result.history if m.role is Role.TOOL)
    assert message.content.startswith("[invalid_arguments]")
    assert rig.policy.received == [] and tool.executions == []


async def test_a_result_that_already_carries_the_right_id_is_kept_as_is() -> None:
    tool = RecordingTool("honest", result_call_id="c1", content="fine")
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "honest")),
        ProviderResponse(content="done"),
    ]
    rig = make_rig(script, [tool])

    result = await rig.run()

    message = next(m for m in result.history if m.role is Role.TOOL)
    assert message.tool_result == ToolResult("c1", "fine", False)
