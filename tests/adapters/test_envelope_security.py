"""T022: restoration checks, tampering and hand-written fixtures (D-02 scenarios 7-9, 13-14, 27-28).

Envelopes here are built with ``ConversionEnvelope._create`` from LITERAL payloads and sidecar
entries written by hand (digests computed with ``hashlib`` directly), so the converters are not
used to produce their own test input.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from harness_agent.adapters.converters import (
    ConversionError,
    restore_messages,
    to_anthropic_envelope,
    to_openai_envelope,
)
from harness_agent.adapters.converters.sidecar import (
    ConversionEnvelope,
    MessageMeta,
    WireRef,
)
from harness_agent.core.entities import Message, Role, TokenUsage, ToolCall, ToolResult


def _digest(elements: list[Any]) -> str:
    text = json.dumps(
        elements, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ref(index: int) -> WireRef:
    return WireRef(kind="message", message_index=index)


def _entry(
    index: int,
    role: Role,
    elements: list[Any],
    refs: tuple[WireRef, ...] | None = None,
    **kw: Any,
) -> MessageMeta:
    return MessageMeta(
        index=index,
        role=role,
        refs=refs if refs is not None else (_ref(index),),
        wire_digest=_digest(elements),
        is_external=kw.pop("is_external", False),
        **kw,
    )


# --- Hand-written OpenAI fixture (shape taken from the Chat Completions documentation) ----------

OPENAI_WIRE: dict[str, Any] = {
    "messages": [
        {"role": "system", "content": "You are terse."},
        {"role": "user", "content": "List files"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_abc",
                    "type": "function",
                    "function": {"name": "ls", "arguments": '{"path": "."}'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_abc", "content": "a.txt"},
    ]
}


def _openai_entries() -> tuple[MessageMeta, ...]:
    m = OPENAI_WIRE["messages"]
    return (
        _entry(0, Role.SYSTEM, [m[0]]),
        _entry(1, Role.USER, [m[1]], is_external=True),
        _entry(2, Role.ASSISTANT, [m[2]], usage=TokenUsage(5, 6)),
        _entry(
            3,
            Role.TOOL,
            [m[3]],
            tool_call_id="call_abc",
            tool_is_error=True,
            tool_message_content="shown to the model",
        ),
    )


def test_scenario_28_openai_hand_written_fixture_restores() -> None:
    env = ConversionEnvelope._create(
        provider="openai", payload=OPENAI_WIRE, entries=_openai_entries()
    )
    assert restore_messages(env) == [
        Message(Role.SYSTEM, "You are terse."),
        Message(Role.USER, "List files", is_external=True),
        Message(
            Role.ASSISTANT,
            "",
            tool_calls=(ToolCall("call_abc", "ls", {"path": "."}),),
            usage=TokenUsage(5, 6),
        ),
        Message(Role.TOOL, "shown to the model", tool_result=ToolResult("call_abc", "a.txt", True)),
    ]


def test_scenario_28_converter_output_matches_the_hand_written_shape() -> None:
    messages = [
        Message(Role.SYSTEM, "You are terse."),
        Message(Role.USER, "List files"),
        Message(Role.ASSISTANT, "", tool_calls=(ToolCall("call_abc", "ls", {"path": "."}),)),
        Message(Role.TOOL, "a.txt", tool_result=ToolResult("call_abc", "a.txt")),
    ]
    env = to_openai_envelope(messages)
    expected = json.loads(json.dumps(OPENAI_WIRE))
    # json.dumps spacing inside the arguments string is converter-defined; compare structurally.
    wire = env.payload["messages"]
    assert [m["role"] for m in wire] == [m["role"] for m in expected["messages"]]
    assert json.loads(wire[2]["tool_calls"][0]["function"]["arguments"]) == {"path": "."}
    assert wire[3] == expected["messages"][3]


ANTHROPIC_WIRE: dict[str, Any] = {
    "system": [{"type": "text", "text": "S1"}, {"type": "text", "text": "S2"}],
    "messages": [
        {"role": "user", "content": "run it"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "ok"},
                {"type": "tool_use", "id": "toolu_1", "name": "sh", "input": {"cmd": "ls"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": "out",
                    "is_error": True,
                }
            ],
        },
    ],
}


def _anthropic_entries() -> tuple[MessageMeta, ...]:
    s, m = ANTHROPIC_WIRE["system"], ANTHROPIC_WIRE["messages"]
    return (
        _entry(0, Role.SYSTEM, [s[0]], (WireRef("system_block", None, 0),)),
        _entry(1, Role.SYSTEM, [s[1]], (WireRef("system_block", None, 1),), is_external=True),
        _entry(2, Role.USER, [m[0]], (_ref(0),), is_external=True),
        _entry(3, Role.ASSISTANT, [m[1]], (_ref(1),)),
        _entry(4, Role.TOOL, [m[2]], (_ref(2),), tool_call_id="toolu_1", tool_is_error=True),
    )


def test_scenario_28_anthropic_hand_written_fixture_restores() -> None:
    env = ConversionEnvelope._create(
        provider="anthropic", payload=ANTHROPIC_WIRE, entries=_anthropic_entries()
    )
    assert restore_messages(env) == [
        Message(Role.SYSTEM, "S1"),
        Message(Role.SYSTEM, "S2", is_external=True),
        Message(Role.USER, "run it", is_external=True),
        Message(Role.ASSISTANT, "ok", tool_calls=(ToolCall("toolu_1", "sh", {"cmd": "ls"}),)),
        Message(Role.TOOL, "out", tool_result=ToolResult("toolu_1", "out", True)),
    ]


# --- Tampering with entries ---------------------------------------------------------------------


def _openai(entries: tuple[MessageMeta, ...], payload: dict[str, Any] | None = None) -> Any:
    return ConversionEnvelope._create(
        provider="openai", payload=payload or OPENAI_WIRE, entries=entries
    )


def _anthropic(entries: tuple[MessageMeta, ...], payload: dict[str, Any] | None = None) -> Any:
    return ConversionEnvelope._create(
        provider="anthropic", payload=payload or ANTHROPIC_WIRE, entries=entries
    )


def test_scenario_7_reordered_references_are_rejected() -> None:
    e = list(_openai_entries())
    swapped = (
        e[0],
        MessageMeta(**{**e[2].__dict__, "index": 1}),
        MessageMeta(**{**e[1].__dict__, "index": 2}),
        e[3],
    )
    with pytest.raises(ConversionError):
        restore_messages(_openai(swapped))


def test_scenario_7_payload_with_swapped_messages_is_rejected() -> None:
    payload = json.loads(json.dumps(OPENAI_WIRE))
    payload["messages"][1], payload["messages"][2] = payload["messages"][2], payload["messages"][1]
    with pytest.raises(ConversionError):
        restore_messages(_openai(_openai_entries(), payload))


def test_scenario_8_swapped_metadata_between_entries_is_rejected() -> None:
    e = list(_openai_entries())
    a = MessageMeta(**{**e[1].__dict__, "index": 2})  # USER metadata onto the ASSISTANT slot
    b = MessageMeta(**{**e[2].__dict__, "index": 1})
    with pytest.raises(ConversionError):
        restore_messages(_openai((e[0], b, a, e[3])))


def test_scenario_9_altered_payload_content_fails_the_digest() -> None:
    payload = json.loads(json.dumps(OPENAI_WIRE))
    payload["messages"][1]["content"] = "something else"
    with pytest.raises(ConversionError, match="digest"):
        restore_messages(_openai(_openai_entries(), payload))


@pytest.mark.parametrize("field", ["role", "tool_call_id"])
def test_scenario_9_altered_roles_or_ids_are_rejected(field: str) -> None:
    payload = json.loads(json.dumps(OPENAI_WIRE))
    payload["messages"][3][field] = "user" if field == "role" else "other"
    with pytest.raises(ConversionError):
        restore_messages(_openai(_openai_entries(), payload))


def test_matches_is_false_for_altered_copies_of_converter_output() -> None:
    env = to_openai_envelope([Message(Role.USER, "u"), Message(Role.ASSISTANT, "a")])
    copy = env.payload
    copy["messages"][1]["content"] = "tampered"
    assert env.matches(copy) is False


def test_scenario_13_anthropic_is_error_differing_from_sidecar_is_rejected() -> None:
    e = list(_anthropic_entries())
    wrong = MessageMeta(**{**e[4].__dict__, "tool_is_error": False})
    with pytest.raises(ConversionError, match="is_error"):
        restore_messages(_anthropic(tuple(e[:4]) + (wrong,)))


def test_scenario_14_openai_payload_cannot_inject_trust_or_error_flags() -> None:
    payload = json.loads(json.dumps(OPENAI_WIRE))
    payload["messages"][1]["is_external"] = False
    payload["messages"][3]["is_error"] = False
    payload["messages"][3]["usage"] = {"prompt_tokens": 1}
    # The digests were computed over the clean fixtures, so recompute them for the injected ones.
    m = payload["messages"]
    entries = (
        _entry(0, Role.SYSTEM, [m[0]]),
        _entry(1, Role.USER, [m[1]], is_external=True),
        _entry(2, Role.ASSISTANT, [m[2]]),
        _entry(3, Role.TOOL, [m[3]], tool_call_id="call_abc", tool_is_error=True),
    )
    restored = restore_messages(_openai(entries, payload))
    assert restored[1].is_external is True  # payload tried to lower it to False
    assert restored[3].tool_result is not None and restored[3].tool_result.is_error is True
    assert restored[3].usage is None


def test_openai_tool_call_id_must_match_the_sidecar() -> None:
    e = list(_openai_entries())
    wrong = MessageMeta(**{**e[3].__dict__, "tool_call_id": "different"})
    with pytest.raises(ConversionError, match="does not match"):
        restore_messages(_openai(tuple(e[:3]) + (wrong,)))


# --- Coverage, overlap, ordering, structure -----------------------------------------------------


def test_uncovered_payload_element_is_rejected() -> None:
    with pytest.raises(ConversionError, match="cover"):
        restore_messages(_openai(_openai_entries()[:3]))


def test_overlapping_or_repeated_references_are_rejected() -> None:
    m = OPENAI_WIRE["messages"]
    entries = (
        _entry(0, Role.SYSTEM, [m[0]]),
        _entry(1, Role.USER, [m[1]], (_ref(1),)),
        _entry(2, Role.USER, [m[1]], (_ref(1),)),
        _entry(3, Role.TOOL, [m[3]], (_ref(3),), tool_call_id="call_abc", tool_is_error=False),
    )
    with pytest.raises(ConversionError):
        restore_messages(_openai(entries))


def test_non_contiguous_indexes_are_rejected() -> None:
    e = list(_openai_entries())
    e[2] = MessageMeta(**{**e[2].__dict__, "index": 7})
    with pytest.raises(ConversionError, match="contiguous"):
        restore_messages(_openai(tuple(e)))


def test_dangling_reference_is_rejected() -> None:
    e = list(_openai_entries())
    e[3] = MessageMeta(**{**e[3].__dict__, "refs": (_ref(9),)})
    with pytest.raises(ConversionError, match="out of range"):
        restore_messages(_openai(tuple(e)))


def test_provider_mismatch_is_rejected() -> None:
    env = to_openai_envelope([Message(Role.ASSISTANT, "", tool_calls=(ToolCall("c", "n", {}),))])
    forged = ConversionEnvelope._create(
        provider="anthropic", payload=env.payload, entries=env.entries
    )
    with pytest.raises(ConversionError):
        restore_messages(forged)
    from harness_agent.adapters.converters.openai_converter import restore_openai_messages

    with pytest.raises(ConversionError, match="provider"):
        restore_openai_messages(forged)


def test_unknown_provider_is_rejected() -> None:
    forged = ConversionEnvelope._create(provider="gemini", payload={"messages": []}, entries=())
    with pytest.raises(ConversionError, match="Unknown"):
        restore_messages(forged)


def test_non_text_system_block_is_rejected() -> None:
    payload = {
        "system": [{"type": "image"}, {"type": "text", "text": "x"}],
        "messages": [],
    }
    entries = (
        _entry(0, Role.SYSTEM, [payload["system"][0]], (WireRef("system_block", None, 0),)),
        _entry(1, Role.SYSTEM, [payload["system"][1]], (WireRef("system_block", None, 1),)),
    )
    with pytest.raises(ConversionError):
        restore_messages(_anthropic(entries, payload))


def test_anthropic_user_message_with_tool_result_is_not_a_canonical_user() -> None:
    m = ANTHROPIC_WIRE["messages"]
    entries = (
        _entry(0, Role.SYSTEM, [ANTHROPIC_WIRE["system"][0]], (WireRef("system_block", None, 0),)),
        _entry(1, Role.SYSTEM, [ANTHROPIC_WIRE["system"][1]], (WireRef("system_block", None, 1),)),
        _entry(2, Role.USER, [m[0]], (_ref(0),)),
        _entry(3, Role.ASSISTANT, [m[1]], (_ref(1),)),
        _entry(4, Role.USER, [m[2]], (_ref(2),)),  # a tool_result carried as a USER: ambiguous
    )
    with pytest.raises(ConversionError):
        restore_messages(_anthropic(entries))


def test_omitted_entries_are_only_valid_for_empty_system() -> None:
    bad = MessageMeta(
        index=0, role=Role.USER, refs=(), wire_digest=_digest([]), is_external=False, omitted=True
    )
    with pytest.raises(ConversionError, match="omitted"):
        restore_messages(_anthropic((bad,), {"messages": []}))


def test_message_block_references_group_several_tool_results_in_one_user_message() -> None:
    """Section 4.3: ``message_block`` is already verified even though converters do not emit it."""
    blocks = [
        {"type": "tool_result", "tool_use_id": "t1", "content": "a", "is_error": False},
        {"type": "tool_result", "tool_use_id": "t2", "content": "b", "is_error": True},
    ]
    payload = {
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "t1", "name": "n", "input": {}},
                    {"type": "tool_use", "id": "t2", "name": "n", "input": {}},
                ],
            },
            {"role": "user", "content": blocks},
        ]
    }
    refs = (WireRef("message_block", 1, 0), WireRef("message_block", 1, 1))
    entries = (
        _entry(0, Role.ASSISTANT, [payload["messages"][0]], (_ref(0),)),
        _entry(1, Role.TOOL, [blocks[0]], (refs[0],), tool_call_id="t1", tool_is_error=False),
        _entry(2, Role.TOOL, [blocks[1]], (refs[1],), tool_call_id="t2", tool_is_error=True),
    )
    restored = restore_messages(_anthropic(entries, payload))
    assert [m.role for m in restored] == [Role.ASSISTANT, Role.TOOL, Role.TOOL]
    assert restored[2].tool_result == ToolResult("t2", "b", True)
    # Covering only one of the two blocks must fail.
    with pytest.raises(ConversionError, match="cover"):
        restore_messages(_anthropic(entries[:2], payload))


# --- Orphans, correlation at restore time ------------------------------------------------------


def test_forged_orphan_result_is_rejected_at_restore_without_partial_window() -> None:
    wire = {"messages": [{"role": "tool", "tool_call_id": "x", "content": "r"}]}
    entry = _entry(0, Role.TOOL, [wire["messages"][0]], tool_call_id="x", tool_is_error=False)
    with pytest.raises(ConversionError, match="not in the window"):
        restore_messages(_openai((entry,), wire))
    ok = ConversionEnvelope._create(
        provider="openai", payload=wire, entries=(entry,), partial_window=True
    )
    assert restore_messages(ok)[0].tool_result == ToolResult("x", "r", False)


# --- Scenario 27: D4 and D6 stay explicit rejections -------------------------------------------


@pytest.mark.parametrize("before", [Role.USER, Role.ASSISTANT])
@pytest.mark.parametrize("factory", [to_openai_envelope, to_anthropic_envelope])
def test_scenario_27_system_after_conversation_is_rejected_with_position(
    factory: Any, before: Role
) -> None:
    messages = [Message(before, "x"), Message(Role.SYSTEM, "late")]
    with pytest.raises(ConversionError, match="position 1"):
        factory(messages)


def test_scenario_27_system_after_tool_is_rejected() -> None:
    messages = [
        Message(Role.ASSISTANT, "", tool_calls=(ToolCall("c", "n", {}),)),
        Message(Role.TOOL, "r", tool_result=ToolResult("c", "r")),
        Message(Role.SYSTEM, "late"),
    ]
    for factory in (to_openai_envelope, to_anthropic_envelope):
        with pytest.raises(ConversionError, match="position 2"):
            factory(messages)


def test_scenario_27_d4_mixed_tool_result_and_text_in_third_party_payload_is_rejected() -> None:
    from harness_agent.adapters.converters import from_anthropic_payload

    with pytest.warns(DeprecationWarning), pytest.raises(ConversionError, match="mixes"):
        from_anthropic_payload(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "hi"},
                            {"type": "tool_result", "tool_use_id": "t", "content": "x"},
                        ],
                    }
                ]
            }
        )
