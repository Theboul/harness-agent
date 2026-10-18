"""Tests for the canonical-sequence rules enforced at the converter boundary (HU-07-01).

D6 - Product Owner decision (2026-10-18): SYSTEM messages are valid only as a contiguous prefix
at the start of the conversation. Any SYSTEM message after a USER, ASSISTANT or TOOL message is an
invalid canonical sequence and must be rejected with ``ConversionError`` (never reordered).

D10 - audit defect: incoherent role/attribute combinations (``tool_calls`` outside ASSISTANT,
``tool_result`` outside TOOL) used to be dropped silently by the converters.

Expected wire values are hand-written literals, not derived from the converter output. These tests
do not cover D1/D2/D8/D9 (pending the technical approval of D-02); the TOOL case with a
``Message.content`` that differs from ``ToolResult.content`` only asserts that it is still accepted.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from harness_agent.adapters.converters import (
    ConversionError,
    from_openai_messages,
    to_anthropic_payload,
    to_openai_messages,
)
from harness_agent.core.entities import Message, Role, ToolCall, ToolResult

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

# ============================================================================
# Helpers
# ============================================================================

Converter = Callable[[list[Message]], Any]


def _openai(messages: list[Message]) -> Any:
    return to_openai_messages(messages)


def _anthropic(messages: list[Message]) -> Any:
    return to_anthropic_payload(messages)


BOTH = pytest.mark.parametrize("convert", [_openai, _anthropic], ids=["openai", "anthropic"])


def _sys(text: str) -> Message:
    return Message(role=Role.SYSTEM, content=text)


def _user(text: str) -> Message:
    return Message(role=Role.USER, content=text)


def _assistant(text: str = "", calls: tuple[ToolCall, ...] = ()) -> Message:
    return Message(role=Role.ASSISTANT, content=text, tool_calls=calls)


def _tool(call_id: str, text: str) -> Message:
    return Message(role=Role.TOOL, content=text, tool_result=ToolResult(call_id, text))


def _call(call_id: str, name: str = "shell", **arguments: Any) -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=dict(arguments))


# ============================================================================
# D6 - valid domain: zero, one or several leading SYSTEM messages
# ============================================================================


def test_d6_empty_sequence_is_admitted_by_both_providers() -> None:
    assert to_openai_messages([]) == []
    assert to_anthropic_payload([]) == {"messages": []}


def test_d6_no_system_message_openai() -> None:
    wire = to_openai_messages([_user("u1"), _assistant("a1")])
    assert wire == [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]


def test_d6_no_system_message_anthropic() -> None:
    payload = to_anthropic_payload([_user("u1"), _assistant("a1")])
    assert "system" not in payload
    assert payload["messages"] == [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]


def test_d6_single_leading_system_openai() -> None:
    assert to_openai_messages([_sys("S"), _user("u")]) == [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "u"},
    ]


def test_d6_single_leading_system_anthropic() -> None:
    payload = to_anthropic_payload([_sys("S"), _user("u")])
    assert payload["system"] == "S"
    assert payload["messages"] == [{"role": "user", "content": "u"}]


def test_d6_several_leading_system_messages_keep_order_and_boundaries_openai() -> None:
    wire = to_openai_messages([_sys("A"), _sys("B"), _sys("C"), _user("u")])
    assert wire == [
        {"role": "system", "content": "A"},
        {"role": "system", "content": "B"},
        {"role": "system", "content": "C"},
        {"role": "user", "content": "u"},
    ]


def test_d6_several_leading_system_messages_keep_order_and_boundaries_anthropic() -> None:
    payload = to_anthropic_payload([_sys("A"), _sys("B"), _sys("C"), _user("u")])
    assert payload["system"] == [
        {"type": "text", "text": "A"},
        {"type": "text", "text": "B"},
        {"type": "text", "text": "C"},
    ]
    assert payload["messages"] == [{"role": "user", "content": "u"}]


def test_d6_only_system_messages_is_a_valid_prefix() -> None:
    assert to_openai_messages([_sys("A"), _sys("B")]) == [
        {"role": "system", "content": "A"},
        {"role": "system", "content": "B"},
    ]
    payload = to_anthropic_payload([_sys("A"), _sys("B")])
    assert payload["system"] == [{"type": "text", "text": "A"}, {"type": "text", "text": "B"}]
    assert payload["messages"] == []


def test_d6_valid_sequence_is_not_mutated_nor_reordered() -> None:
    original = [_sys("B"), _sys("A"), _user("u"), _assistant("a")]
    snapshot = list(original)
    wire = to_openai_messages(original)
    to_anthropic_payload(original)
    assert original == snapshot
    assert [m["content"] for m in wire] == ["B", "A", "u", "a"]  # input order, not sorted


# ============================================================================
# D6 - invalid domain: SYSTEM after any non-SYSTEM message
# ============================================================================


@BOTH
@pytest.mark.parametrize(
    ("prefix", "prefix_role"),
    [
        (_user("u"), "user"),
        (_assistant("a"), "assistant"),
        (_tool("c1", "out"), "tool"),
    ],
    ids=["after-user", "after-assistant", "after-tool"],
)
def test_d6_system_after_non_system_message_is_rejected(
    convert: Converter, prefix: Message, prefix_role: str
) -> None:
    sequence = [prefix, _sys("late")]
    with pytest.raises(ConversionError) as excinfo:
        convert(sequence)
    text = str(excinfo.value)
    assert "SYSTEM" in text
    assert "contiguous prefix" in text
    assert "position 1" in text
    assert prefix_role in text


@BOTH
def test_d6_interleaved_system_between_messages_is_rejected(convert: Converter) -> None:
    sequence = [_sys("A"), _user("u"), _sys("B"), _assistant("a")]
    with pytest.raises(ConversionError, match=r"position 2"):
        convert(sequence)


@BOTH
def test_d6_system_at_the_end_is_rejected_not_moved_to_the_front(convert: Converter) -> None:
    with pytest.raises(ConversionError, match="contiguous prefix"):
        convert([_user("u"), _assistant("a"), _sys("S")])


@BOTH
def test_d6_rejection_reports_first_offending_position(convert: Converter) -> None:
    sequence = [_sys("A"), _user("u"), _sys("B"), _sys("C")]
    with pytest.raises(ConversionError, match=r"position 2"):
        convert(sequence)


def test_d6_openai_reverse_direction_rejects_interleaved_system() -> None:
    wire = [
        {"role": "user", "content": "u"},
        {"role": "system", "content": "late"},
    ]
    with pytest.raises(ConversionError, match="contiguous prefix"):
        from_openai_messages(wire)


def test_d6_openai_reverse_direction_accepts_leading_system_messages() -> None:
    wire = [
        {"role": "system", "content": "A"},
        {"role": "system", "content": "B"},
        {"role": "user", "content": "u"},
    ]
    restored = from_openai_messages(wire)
    assert [(m.role, m.content) for m in restored] == [
        (Role.SYSTEM, "A"),
        (Role.SYSTEM, "B"),
        (Role.USER, "u"),
    ]


# ============================================================================
# D10 - incoherent role/attribute combinations must not be dropped silently
# ============================================================================

INCOHERENT = [
    pytest.param(
        Message(role=Role.USER, content="u", tool_calls=(_call("c1"),)),
        "USER",
        "tool_calls",
        id="user-with-tool_calls",
    ),
    pytest.param(
        Message(role=Role.SYSTEM, content="s", tool_calls=(_call("c1"),)),
        "SYSTEM",
        "tool_calls",
        id="system-with-tool_calls",
    ),
    pytest.param(
        Message(role=Role.USER, content="u", tool_result=ToolResult("c1", "x")),
        "USER",
        "tool_result",
        id="user-with-tool_result",
    ),
    pytest.param(
        Message(role=Role.SYSTEM, content="s", tool_result=ToolResult("c1", "x")),
        "SYSTEM",
        "tool_result",
        id="system-with-tool_result",
    ),
    pytest.param(
        Message(role=Role.ASSISTANT, content="a", tool_result=ToolResult("c1", "x")),
        "ASSISTANT",
        "tool_result",
        id="assistant-with-tool_result",
    ),
    pytest.param(
        Message(
            role=Role.TOOL,
            content="x",
            tool_calls=(_call("c2"),),
            tool_result=ToolResult("c1", "x"),
        ),
        "TOOL",
        "tool_calls",
        id="tool-with-tool_calls",
    ),
]


@BOTH
@pytest.mark.parametrize(("bad", "role", "field"), INCOHERENT)
def test_d10_incoherent_message_is_rejected_with_a_diagnosable_error(
    convert: Converter, bad: Message, role: str, field: str
) -> None:
    sequence = [_user("first"), bad] if bad.role != Role.SYSTEM else [bad]
    position = sequence.index(bad)
    with pytest.raises(ConversionError) as excinfo:
        convert(sequence)
    text = str(excinfo.value)
    assert role in text
    assert field in text
    assert f"position {position}" in text


@BOTH
def test_d10_error_is_a_conversion_error_not_an_internal_exception(convert: Converter) -> None:
    bad = Message(role=Role.USER, content="u", tool_calls=(_call("c1"),))
    with pytest.raises(ConversionError):
        convert([bad])


# --- coherent combinations that must keep converting ------------------------


def test_d10_assistant_text_with_valid_tool_calls_openai() -> None:
    wire = to_openai_messages([_assistant("thinking", (_call("c1", "shell", cmd="ls"),))])
    assert len(wire) == 1
    entry = wire[0]
    assert entry["role"] == "assistant"
    assert entry["content"] == "thinking"
    [tc] = entry["tool_calls"]
    assert tc["id"] == "c1"
    assert tc["type"] == "function"
    assert tc["function"]["name"] == "shell"
    assert json.loads(tc["function"]["arguments"]) == {"cmd": "ls"}


def test_d10_assistant_text_with_valid_tool_calls_anthropic() -> None:
    payload = to_anthropic_payload([_assistant("thinking", (_call("c1", "shell", cmd="ls"),))])
    assert payload["messages"] == [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "thinking"},
                {"type": "tool_use", "id": "c1", "name": "shell", "input": {"cmd": "ls"}},
            ],
        }
    ]


def test_d10_valid_tool_message_openai() -> None:
    assert to_openai_messages([_tool("c1", "out")]) == [
        {"role": "tool", "tool_call_id": "c1", "content": "out"}
    ]


def test_d10_valid_tool_message_anthropic() -> None:
    payload = to_anthropic_payload([_tool("c1", "out")])
    assert payload["messages"] == [
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "c1",
                    "content": "out",
                    "is_error": False,
                }
            ],
        }
    ]


@BOTH
def test_d10_tool_message_whose_content_differs_from_result_is_still_accepted(
    convert: Converter,
) -> None:
    """Message.content != ToolResult.content is D9 (pending D-02), not an invalid combination."""
    message = Message(role=Role.TOOL, content="DIFFERENT", tool_result=ToolResult("c1", "real"))
    result = convert([message])  # must not raise
    assert result is not None


def test_d10_several_valid_tool_calls_and_results_convert_in_order() -> None:
    sequence = [
        _user("go"),
        _assistant("", (_call("c1", "a", x=1), _call("c2", "b", y=2))),
        _tool("c1", "r1"),
        _tool("c2", "r2"),
    ]
    wire = to_openai_messages(sequence)
    assert [m["role"] for m in wire] == ["user", "assistant", "tool", "tool"]
    assert [tc["id"] for tc in wire[1]["tool_calls"]] == ["c1", "c2"]
    assert [m["tool_call_id"] for m in wire[2:]] == ["c1", "c2"]

    payload = to_anthropic_payload(sequence)
    blocks = payload["messages"][1]["content"]
    assert [b["id"] for b in blocks] == ["c1", "c2"]
    assert [m["content"][0]["tool_use_id"] for m in payload["messages"][2:]] == ["c1", "c2"]


@BOTH
def test_d10_empty_tool_calls_tuple_is_not_incoherent(convert: Converter) -> None:
    """An empty tuple is the default value, so USER/SYSTEM messages with it are fine."""
    assert convert([_sys("s"), _user("u")]) is not None


# --- reverse direction -------------------------------------------------------


def test_d10_openai_reverse_direction_rejects_user_with_tool_calls() -> None:
    wire = [
        {
            "role": "user",
            "content": "u",
            "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "n", "arguments": "{}"}}
            ],
        }
    ]
    with pytest.raises(ConversionError, match="tool_calls"):
        from_openai_messages(wire)
