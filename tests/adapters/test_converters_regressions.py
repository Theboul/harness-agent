"""Regression tests for audited converter defects D3-D7 (HU-07-01, tasks T010-T015).

Each test reproduces a defect found by the audit of the first converter implementation.
Defects D1/D2 are covered at the end of this module through the conversion envelope (T023);
the remaining D-02 behavior lives in ``test_envelope_*.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.adapters.converters import (
    ConversionError,
    from_anthropic_payload,
    from_anthropic_response,
    from_openai_messages,
    from_openai_response,
    restore_messages,
    to_anthropic_envelope,
    to_anthropic_payload,
    to_openai_envelope,
    to_openai_messages,
)
from harness_agent.core.entities import Message, Role, ToolCall, ToolResult

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

# ============================================================================
# Helpers
# ============================================================================


def _openai_response_with_args(raw_args: Any) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_x",
                            "type": "function",
                            "function": {"name": "my_tool", "arguments": raw_args},
                        }
                    ],
                }
            }
        ]
    }


def _openai_assistant_message_with_args(raw_args: Any) -> list[dict[str, Any]]:
    return [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_x",
                    "type": "function",
                    "function": {"name": "my_tool", "arguments": raw_args},
                }
            ],
        }
    ]


def _anthropic_payload(content: Any, role: str = "user") -> dict[str, Any]:
    return {"messages": [{"role": role, "content": content}]}


# ============================================================================
# D3 - tool-call arguments must be JSON objects
# ============================================================================


@pytest.mark.parametrize("raw_args", ["[1,2]", "5", "null", '"text"', "true", "3.14"])
def test_d3_openai_response_rejects_non_object_json_arguments(raw_args: str) -> None:
    with pytest.raises(ConversionError, match="JSON object") as exc_info:
        from_openai_response(_openai_response_with_args(raw_args))
    # Diagnosable: names the tool call id and tool name
    assert "call_x" in str(exc_info.value)
    assert "my_tool" in str(exc_info.value)


@pytest.mark.parametrize("raw_args", ["[1,2]", "5", "null", '"text"', "true"])
def test_d3_openai_messages_reject_non_object_json_arguments(raw_args: str) -> None:
    with pytest.raises(ConversionError, match="JSON object") as exc_info:
        from_openai_messages(_openai_assistant_message_with_args(raw_args))
    assert "call_x" in str(exc_info.value)


@pytest.mark.parametrize("raw_args", [5, [1, 2], None, 1.5, True])
def test_d3_openai_rejects_arguments_of_unsupported_python_type(raw_args: Any) -> None:
    with pytest.raises(ConversionError):
        from_openai_response(_openai_response_with_args(raw_args))
    with pytest.raises(ConversionError):
        from_openai_messages(_openai_assistant_message_with_args(raw_args))


def test_d3_openai_accepts_valid_object_empty_and_dict_arguments() -> None:
    resp = from_openai_response(_openai_response_with_args('{"a": 1, "b": {"c": [1, 2]}}'))
    assert resp.tool_calls[0].arguments == {"a": 1, "b": {"c": [1, 2]}}

    assert from_openai_response(_openai_response_with_args("")).tool_calls[0].arguments == {}
    assert from_openai_response(_openai_response_with_args("   ")).tool_calls[0].arguments == {}
    assert from_openai_response(_openai_response_with_args({"k": "v"})).tool_calls[0].arguments == {
        "k": "v"
    }
    msgs = from_openai_messages(_openai_assistant_message_with_args('{"x": true}'))
    assert msgs[0].tool_calls[0].arguments == {"x": True}


def test_d3_diagnostic_truncates_very_long_values() -> None:
    long_value = "[" + "1," * 5000 + "1]"
    with pytest.raises(ConversionError) as exc_info:
        from_openai_response(_openai_response_with_args(long_value))
    assert len(str(exc_info.value)) < 600


def test_d3_non_serializable_arguments_raise_conversion_error_when_sending() -> None:
    msg = Message(
        role=Role.ASSISTANT,
        tool_calls=(ToolCall(id="c1", name="t", arguments={"bad": {1, 2}}),),
    )
    with pytest.raises(ConversionError, match="serializ"):
        to_openai_messages([msg])
    with pytest.raises(ConversionError, match="serializ"):
        to_anthropic_payload([msg])


# ============================================================================
# D4 - Anthropic request payload: no silent drops
# ============================================================================


def test_d4_tool_result_mixed_with_text_is_rejected_not_dropped() -> None:
    payload = _anthropic_payload(
        [
            {"type": "tool_result", "tool_use_id": "a", "content": "r"},
            {"type": "text", "text": "text that must not vanish"},
        ]
    )
    with pytest.raises(ConversionError, match="tool_result"):
        from_anthropic_payload(payload)


def test_d4_text_before_tool_result_is_rejected_too() -> None:
    payload = _anthropic_payload(
        [
            {"type": "text", "text": "leading text"},
            {"type": "tool_result", "tool_use_id": "a", "content": "r"},
        ]
    )
    with pytest.raises(ConversionError, match="tool_result"):
        from_anthropic_payload(payload)


@pytest.mark.parametrize("role", ["user", "assistant"])
def test_d4_unknown_block_types_are_rejected_with_their_name(role: str) -> None:
    payload = _anthropic_payload([{"type": "image", "source": {"type": "base64"}}], role=role)
    with pytest.raises(ConversionError, match="Unsupported Anthropic block type") as exc_info:
        from_anthropic_payload(payload)
    assert "image" in str(exc_info.value)


def test_d4_unknown_block_next_to_text_is_rejected() -> None:
    payload = _anthropic_payload(
        [{"type": "text", "text": "hi"}, {"type": "document", "source": {}}]
    )
    with pytest.raises(ConversionError, match="document"):
        from_anthropic_payload(payload)


def test_d4_tool_use_mixed_with_tool_result_is_rejected() -> None:
    payload = _anthropic_payload(
        [
            {"type": "tool_use", "id": "t", "name": "n", "input": {}},
            {"type": "tool_result", "tool_use_id": "t", "content": "x"},
        ],
        role="assistant",
    )
    with pytest.raises(ConversionError):
        from_anthropic_payload(payload)


def test_d4_blocks_in_the_wrong_role_are_rejected() -> None:
    tool_use_in_user = _anthropic_payload(
        [{"type": "tool_use", "id": "t", "name": "n", "input": {}}], role="user"
    )
    with pytest.raises(ConversionError):
        from_anthropic_payload(tool_use_in_user)
    tool_result_in_assistant = _anthropic_payload(
        [{"type": "tool_result", "tool_use_id": "t", "content": "x"}], role="assistant"
    )
    with pytest.raises(ConversionError):
        from_anthropic_payload(tool_result_in_assistant)


@pytest.mark.parametrize(
    "block",
    [
        {"type": "tool_use", "name": "n", "input": {}},  # no id
        {"type": "tool_use", "id": "t", "input": {}},  # no name
        {"type": "tool_use", "id": "t", "name": "n", "input": [1]},  # input not object
        {"type": "tool_use", "id": 7, "name": "n", "input": {}},  # id not str
    ],
)
def test_d4_incomplete_tool_use_blocks_are_rejected(block: dict[str, Any]) -> None:
    with pytest.raises(ConversionError):
        from_anthropic_payload(_anthropic_payload([block], role="assistant"))


@pytest.mark.parametrize(
    "block",
    [
        {"type": "tool_result", "content": "x"},  # no tool_use_id
        {"type": "tool_result", "tool_use_id": "", "content": "x"},  # empty id
        {"type": "tool_result", "tool_use_id": 3, "content": "x"},  # id not str
        {"type": "tool_result", "tool_use_id": "t", "content": "x", "is_error": "no"},
    ],
)
def test_d4_incomplete_tool_result_blocks_are_rejected(block: dict[str, Any]) -> None:
    with pytest.raises(ConversionError):
        from_anthropic_payload(_anthropic_payload([block]))


@pytest.mark.parametrize(
    "block",
    [
        {"type": "text"},  # no text
        {"type": "text", "text": 5},  # text not str
        "not-a-dict",
        None,
    ],
)
def test_d4_malformed_text_and_non_dict_blocks_are_rejected(block: Any) -> None:
    with pytest.raises(ConversionError):
        from_anthropic_payload(_anthropic_payload([block]))


@pytest.mark.parametrize("role", ["system", "tool", "developer", None, 5])
def test_d4_unsupported_roles_in_messages_are_rejected(role: Any) -> None:
    payload = {"messages": [{"role": role, "content": "x"}]}
    with pytest.raises(ConversionError):
        from_anthropic_payload(payload)


def test_d4_empty_content_list_is_rejected_not_turned_into_empty_message() -> None:
    with pytest.raises(ConversionError, match="empty"):
        from_anthropic_payload(_anthropic_payload([]))


def test_d4_invalid_payload_shapes_are_rejected() -> None:
    with pytest.raises(ConversionError):
        from_anthropic_payload({"messages": "nope"})
    with pytest.raises(ConversionError):
        from_anthropic_payload({"messages": ["nope"]})
    with pytest.raises(ConversionError):
        from_anthropic_payload({"messages": [{"role": "user", "content": 42}]})


def test_d4_valid_blocks_still_reconstruct_losslessly() -> None:
    payload = {
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "calling"},
                    {"type": "tool_use", "id": "t1", "name": "shell", "input": {"cmd": "ls"}},
                    {"type": "tool_use", "id": "t2", "name": "shell", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "t1", "content": "a", "is_error": True},
                    {"type": "tool_result", "tool_use_id": "t2", "content": "b"},
                ],
            },
        ]
    }
    msgs = from_anthropic_payload(payload)
    assert [m.role for m in msgs] == [Role.USER, Role.ASSISTANT, Role.TOOL, Role.TOOL]
    assert msgs[1].tool_calls == (
        ToolCall("t1", "shell", {"cmd": "ls"}),
        ToolCall("t2", "shell", {}),
    )
    assert msgs[2].tool_result == ToolResult("t1", "a", True)
    assert msgs[3].tool_result == ToolResult("t2", "b", False)


# ============================================================================
# D5 - ToolResult.content (and Message.content) must be str
# ============================================================================


def test_d5_tool_result_text_block_list_is_joined_explicitly() -> None:
    payload = _anthropic_payload(
        [
            {
                "type": "tool_result",
                "tool_use_id": "a",
                "content": [{"type": "text", "text": "line1"}, {"type": "text", "text": "line2"}],
            }
        ]
    )
    msgs = from_anthropic_payload(payload)
    assert msgs[0].tool_result is not None
    assert msgs[0].tool_result.content == "line1\nline2"
    assert isinstance(msgs[0].tool_result.content, str)
    assert msgs[0].content == "line1\nline2"


@pytest.mark.parametrize(
    "content",
    [
        [{"type": "image", "source": {}}],
        [{"type": "text", "text": "ok"}, {"type": "image", "source": {}}],
        [{"type": "text"}],
        ["raw string in list"],
        42,
        {"type": "text", "text": "dict instead of list"},
    ],
)
def test_d5_tool_result_incompatible_content_is_rejected(content: Any) -> None:
    payload = _anthropic_payload([{"type": "tool_result", "tool_use_id": "a", "content": content}])
    with pytest.raises(ConversionError):
        from_anthropic_payload(payload)


def test_d5_tool_result_without_content_is_empty_text() -> None:
    payload = _anthropic_payload([{"type": "tool_result", "tool_use_id": "a"}])
    msgs = from_anthropic_payload(payload)
    assert msgs[0].tool_result == ToolResult("a", "", False)


@pytest.mark.parametrize("content", [["part"], 7, {"k": "v"}])
def test_d5_openai_message_content_must_be_text(content: Any) -> None:
    for role_msg in (
        {"role": "user", "content": content},
        {"role": "assistant", "content": content},
        {"role": "system", "content": content},
        {"role": "tool", "tool_call_id": "c", "content": content},
    ):
        with pytest.raises(ConversionError):
            from_openai_messages([role_msg])


def test_d5_openai_none_content_is_empty_text() -> None:
    msgs = from_openai_messages(
        [
            {"role": "assistant", "content": None},
            {"role": "tool", "tool_call_id": "c", "content": None},
        ]
    )
    assert msgs[0].content == ""
    assert msgs[1].tool_result == ToolResult("c", "", False)


@pytest.mark.parametrize("content", [["part"], 7, {"k": "v"}])
def test_d5_openai_response_content_must_be_text(content: Any) -> None:
    response = {"choices": [{"message": {"role": "assistant", "content": content}}]}
    with pytest.raises(ConversionError):
        from_openai_response(response)


@pytest.mark.parametrize("text", [None, 5, ["x"]])
def test_d5_anthropic_response_text_block_must_be_str(text: Any) -> None:
    with pytest.raises(ConversionError):
        from_anthropic_response({"content": [{"type": "text", "text": text}]})


# ============================================================================
# D6 - system messages keep their boundaries and order
# ============================================================================


def test_d6_openai_preserves_two_system_messages_in_order() -> None:
    canonical = [
        Message(role=Role.SYSTEM, content="A"),
        Message(role=Role.SYSTEM, content="B"),
        Message(role=Role.USER, content="u"),
    ]
    wire = to_openai_messages(canonical)
    assert [m["role"] for m in wire] == ["system", "system", "user"]
    assert from_openai_messages(wire) == canonical


def test_d6_anthropic_two_system_messages_round_trip_in_order() -> None:
    canonical = [
        Message(role=Role.SYSTEM, content="A"),
        Message(role=Role.SYSTEM, content="B"),
        Message(role=Role.USER, content="u"),
    ]
    payload = to_anthropic_payload(canonical)
    assert payload["system"] == [
        {"type": "text", "text": "A"},
        {"type": "text", "text": "B"},
    ]
    assert from_anthropic_payload(payload) == canonical


def test_d6_anthropic_single_system_keeps_plain_string() -> None:
    payload = to_anthropic_payload(
        [Message(role=Role.SYSTEM, content="A"), Message(role=Role.USER, content="u")]
    )
    assert payload["system"] == "A"


def test_d6_anthropic_system_with_internal_blank_lines_is_not_split() -> None:
    canonical = [
        Message(role=Role.SYSTEM, content="line1\n\nline2"),
        Message(role=Role.USER, content="u"),
    ]
    assert from_anthropic_payload(to_anthropic_payload(canonical)) == canonical


def test_d6_anthropic_payload_with_system_block_list_returns_one_message_per_block() -> None:
    payload = {
        "system": [{"type": "text", "text": "A"}, {"type": "text", "text": "B"}],
        "messages": [{"role": "user", "content": "u"}],
    }
    msgs = from_anthropic_payload(payload)
    assert [(m.role, m.content) for m in msgs] == [
        (Role.SYSTEM, "A"),
        (Role.SYSTEM, "B"),
        (Role.USER, "u"),
    ]


def test_d6_anthropic_system_after_other_messages_is_rejected_not_hoisted() -> None:
    canonical = [
        Message(role=Role.SYSTEM, content="A"),
        Message(role=Role.USER, content="u"),
        Message(role=Role.SYSTEM, content="B"),
    ]
    # Wording follows the shared validator (PO decision 2026-10-18); the rejection is unchanged.
    with pytest.raises(ConversionError, match="contiguous prefix"):
        to_anthropic_payload(canonical)
    with pytest.raises(ConversionError, match="contiguous prefix"):
        to_anthropic_payload(canonical[1:])  # user, system


def test_d6_anthropic_empty_system_message_is_rejected_not_dropped() -> None:
    with pytest.raises(ConversionError, match="empty"):
        to_anthropic_payload([Message(role=Role.SYSTEM, content=""), Message(Role.USER, "u")])


@pytest.mark.parametrize(
    "system",
    [5, {"type": "text", "text": "dict"}, [{"type": "image"}], [{"type": "text"}], ["raw"]],
)
def test_d6_anthropic_invalid_system_shapes_are_rejected(system: Any) -> None:
    payload = {"system": system, "messages": [{"role": "user", "content": "u"}]}
    with pytest.raises(ConversionError):
        from_anthropic_payload(payload)


# ============================================================================
# D7 - invalid external payloads raise ConversionError (not KeyError/AttributeError/...)
# ============================================================================


def _tc(**function: Any) -> dict[str, Any]:
    return {"id": "c1", "type": "function", "function": function}


@pytest.mark.parametrize(
    "response",
    [
        [],  # response is not a dict
        "text",
        {"choices": "x"},
        {"choices": []},
        {"choices": ["x"]},
        {"choices": [None]},
        {"choices": [{}]},
        {"choices": [{"message": "x"}]},
        {"choices": [{"message": {"tool_calls": "x"}}]},
        {"choices": [{"message": {"tool_calls": ["x"]}}]},
        {"choices": [{"message": {"tool_calls": [{"function": {"name": "n"}}]}}]},  # no id
        {"choices": [{"message": {"tool_calls": [{"id": 5, "function": {"name": "n"}}]}}]},
        {"choices": [{"message": {"tool_calls": [{"id": "c1"}]}}]},  # no function
        {"choices": [{"message": {"tool_calls": [{"id": "c1", "function": "x"}]}}]},
        {"choices": [{"message": {"tool_calls": [_tc(arguments="{}")]}}]},  # no name
        {"choices": [{"message": {"tool_calls": [_tc(name="", arguments="{}")]}}]},
        {"choices": [{"message": {"tool_calls": [_tc(name=3, arguments="{}")]}}]},
    ],
)
def test_d7_openai_response_invalid_structures(response: Any) -> None:
    with pytest.raises(ConversionError):
        from_openai_response(response)


def _usage_response(usage: Any) -> dict[str, Any]:
    return {"choices": [{"message": {"content": "ok"}}], "usage": usage}


@pytest.mark.parametrize(
    "usage",
    [
        [],
        "x",
        {"prompt_tokens": "abc", "completion_tokens": 1},
        {"prompt_tokens": 1, "completion_tokens": [1]},
        {"prompt_tokens": True, "completion_tokens": 1},
        {"prompt_tokens": 1, "completion_tokens": -1},
        {"prompt_tokens": 1.5, "completion_tokens": 1},
    ],
)
def test_d7_openai_usage_with_incompatible_types(usage: Any) -> None:
    with pytest.raises(ConversionError):
        from_openai_response(_usage_response(usage))


def test_d7_openai_usage_absent_or_none_is_allowed() -> None:
    assert from_openai_response({"choices": [{"message": {"content": "ok"}}]}).usage is None
    resp = from_openai_response(_usage_response({"prompt_tokens": None, "completion_tokens": 2}))
    assert resp.usage is not None
    assert (resp.usage.input_tokens, resp.usage.output_tokens) == (0, 2)


@pytest.mark.parametrize(
    "raw_messages",
    [
        "x",
        ["x"],
        [{}],  # no role
        [{"role": 5}],
        [{"role": "developer", "content": "x"}],  # unknown role
        [{"role": "assistant", "tool_calls": "x"}],
        [{"role": "assistant", "tool_calls": ["x"]}],
        [{"role": "assistant", "tool_calls": [{"function": {"name": "n", "arguments": "{}"}}]}],
        [{"role": "assistant", "tool_calls": [{"id": "c1"}]}],
        [{"role": "assistant", "tool_calls": [{"id": "c1", "function": "x"}]}],
        [{"role": "assistant", "tool_calls": [{"id": "c1", "function": {"arguments": "{}"}}]}],
        [{"role": "tool", "content": "orphan without tool_call_id"}],
        [{"role": "tool", "tool_call_id": 5, "content": "x"}],
    ],
)
def test_d7_openai_messages_invalid_structures(raw_messages: Any) -> None:
    with pytest.raises(ConversionError):
        from_openai_messages(raw_messages)


def test_d7_openai_unknown_role_error_is_chained_and_names_the_role() -> None:
    with pytest.raises(ConversionError, match="developer") as exc_info:
        from_openai_messages([{"role": "developer", "content": "x"}])
    assert isinstance(exc_info.value.__cause__, ValueError)


@pytest.mark.parametrize(
    "response",
    [
        [],
        {},  # no content
        {"content": 5},
        {"content": None},
        {"content": ["x"]},  # list items are not dict blocks
        {"content": [{"type": "tool_use", "name": "n", "input": {}}]},  # no id
        {"content": [{"type": "tool_use", "id": "t", "input": {}}]},  # no name
        {"content": [{"type": "tool_use", "id": 5, "name": "n", "input": {}}]},
        {"content": [{"type": "tool_use", "id": "t", "name": "n", "input": "x"}]},
        {"content": [{"type": "tool_use", "id": "t", "name": "n"}]},  # no input
    ],
)
def test_d7_anthropic_response_invalid_structures(response: Any) -> None:
    with pytest.raises(ConversionError):
        from_anthropic_response(response)


@pytest.mark.parametrize(
    "usage",
    [
        [],
        {"input_tokens": "abc", "output_tokens": 1},
        {"input_tokens": 1, "output_tokens": True},
        {"input_tokens": -4, "output_tokens": 1},
    ],
)
def test_d7_anthropic_usage_with_incompatible_types(usage: Any) -> None:
    with pytest.raises(ConversionError):
        from_anthropic_response({"content": "ok", "usage": usage})


def test_d7_valid_payloads_still_parse() -> None:
    resp = from_anthropic_response(
        {
            "content": [
                {"type": "text", "text": "a"},
                {"type": "tool_use", "id": "t", "name": "n", "input": {}},
            ],
            "usage": {"input_tokens": 3, "output_tokens": 4},
        }
    )
    assert resp.content == "a"
    assert resp.tool_calls == [ToolCall("t", "n", {})]
    assert resp.usage is not None and resp.usage.total_tokens == 7


def test_d4_text_after_tool_use_is_rejected_not_reordered() -> None:
    payload = _anthropic_payload(
        [
            {"type": "tool_use", "id": "t", "name": "n", "input": {}},
            {"type": "text", "text": "trailing text"},
        ],
        role="assistant",
    )
    with pytest.raises(ConversionError, match="text after a tool_use"):
        from_anthropic_payload(payload)


# ============================================================================
# D1/D2 (T023): preserved through the conversion envelope (design D-02). The payload-only functions
# still cannot recover these attributes (and are deprecated); that limit is pinned below so any
# change to it is deliberate.
# ============================================================================


def test_d1_is_external_is_preserved_by_the_envelope_for_both_providers() -> None:
    msgs = [Message(role=Role.USER, content="hi", is_external=True)]
    assert restore_messages(to_openai_envelope(msgs)) == msgs
    assert restore_messages(to_anthropic_envelope(msgs)) == msgs


def test_d1_is_external_never_reaches_the_wire() -> None:
    msgs = [Message(role=Role.USER, content="hi", is_external=True)]
    assert "is_external" not in str(to_openai_envelope(msgs).payload)
    assert "is_external" not in str(to_anthropic_envelope(msgs).payload)


def test_d2_is_error_is_preserved_by_the_envelope_for_both_providers() -> None:
    msgs = [
        Message(Role.ASSISTANT, "", tool_calls=(ToolCall("c1", "n", {}),)),
        Message(Role.TOOL, "boom", tool_result=ToolResult("c1", "boom", True)),
    ]
    assert restore_messages(to_openai_envelope(msgs)) == msgs
    assert restore_messages(to_anthropic_envelope(msgs)) == msgs


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_payload_only_functions_still_cannot_recover_local_attributes() -> None:
    external = [Message(role=Role.USER, content="hi", is_external=True)]
    assert from_openai_messages(to_openai_messages(external))[0].is_external is False
    assert from_anthropic_payload(to_anthropic_payload(external))[0].is_external is False
    errored = [Message(Role.TOOL, "boom", tool_result=ToolResult("c1", "boom", True))]
    openai_back = from_openai_messages(to_openai_messages(errored))
    assert openai_back[0].tool_result == ToolResult("c1", "boom", False)  # lost without envelope
    anthropic_back = from_anthropic_payload(to_anthropic_payload(errored))
    assert anthropic_back[0].tool_result == ToolResult("c1", "boom", True)
