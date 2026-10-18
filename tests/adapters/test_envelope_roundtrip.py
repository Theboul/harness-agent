"""T020/T021: lossless round trip via ``to_*_envelope`` / ``restore_messages`` (D-02 section 11).

Resolves D1 (``is_external``), D2 (``is_error``), D8 (``usage``) and D9 (TOOL content) for both
providers, plus tool correlation (section 4.7) and the empty-SYSTEM mechanism.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest

from harness_agent.adapters.converters import (
    AnthropicConverter,
    ConversionError,
    OpenAIConverter,
    restore_messages,
    to_anthropic_envelope,
    to_anthropic_payload,
    to_openai_envelope,
    to_openai_messages,
)
from harness_agent.adapters.converters.sidecar import ConversionEnvelope
from harness_agent.core.entities import Message, Role, TokenUsage, ToolCall, ToolResult
from harness_agent.core.interfaces.provider import ToolDefinition

EnvelopeFactory = Callable[..., ConversionEnvelope]

FACTORIES: list[tuple[str, EnvelopeFactory]] = [
    ("openai", to_openai_envelope),
    ("anthropic", to_anthropic_envelope),
]


@pytest.fixture(params=FACTORIES, ids=[name for name, _ in FACTORIES])
def make(request: pytest.FixtureRequest) -> EnvelopeFactory:
    factory: EnvelopeFactory = request.param[1]
    return factory


def _roundtrip(make: EnvelopeFactory, messages: list[Message], **kw: Any) -> list[Message]:
    return restore_messages(make(messages, **kw))


def _call(call_id: str, name: str = "t", **arguments: Any) -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=arguments)


# --- D1 -----------------------------------------------------------------------------------


def test_d1_is_external_is_preserved(make: EnvelopeFactory) -> None:
    messages = [
        Message(Role.USER, "hi", is_external=True),
        Message(Role.USER, "hi", is_external=False),
        Message(Role.ASSISTANT, "ok", is_external=True),
    ]
    assert _roundtrip(make, messages) == messages


# --- D2 / D8 / D9 ---------------------------------------------------------------------------


def test_d2_is_error_is_preserved_and_never_enters_the_payload_for_openai() -> None:
    messages = [
        Message(Role.ASSISTANT, "", tool_calls=(_call("c1"), _call("c2"))),
        Message(Role.TOOL, "boom", tool_result=ToolResult("c1", "boom", is_error=True)),
        Message(Role.TOOL, "fine", tool_result=ToolResult("c2", "fine", is_error=False)),
    ]
    env = to_openai_envelope(messages)
    assert all("is_error" not in m for m in env.payload["messages"])
    assert restore_messages(env) == messages


def test_d2_mixed_results_keep_ids_and_flags_for_both_providers(make: EnvelopeFactory) -> None:
    messages = [
        Message(Role.ASSISTANT, "x", tool_calls=(_call("a"), _call("b"), _call("c"))),
        Message(Role.TOOL, "1", tool_result=ToolResult("c", "1", is_error=True)),
        Message(Role.TOOL, "2", tool_result=ToolResult("a", "2")),
        Message(Role.TOOL, "3", tool_result=ToolResult("b", "3", is_error=True)),
    ]
    assert _roundtrip(make, messages) == messages


def test_d8_message_usage_is_preserved_and_not_emitted(make: EnvelopeFactory) -> None:
    messages = [
        Message(Role.USER, "q"),
        Message(Role.ASSISTANT, "a", usage=TokenUsage(3, 4)),
    ]
    env = make(messages)
    assert "usage" not in str(env.payload)
    restored = restore_messages(env)
    assert restored == messages
    assert restored[1].usage == TokenUsage(3, 4)


def test_d9_tool_message_content_differing_from_result_content(make: EnvelopeFactory) -> None:
    messages = [
        Message(Role.ASSISTANT, "", tool_calls=(_call("c"),)),
        Message(Role.TOOL, "DIFFERENT", tool_result=ToolResult("c", "real")),
    ]
    restored = _roundtrip(make, messages)
    assert restored == messages
    assert restored[1].content == "DIFFERENT"
    assert restored[1].tool_result == ToolResult("c", "real")


def test_d9_empty_message_content_with_nonempty_result_is_preserved(make: EnvelopeFactory) -> None:
    messages = [
        Message(Role.ASSISTANT, "", tool_calls=(_call("c"),)),
        Message(Role.TOOL, "", tool_result=ToolResult("c", "real")),
    ]
    assert _roundtrip(make, messages) == messages


# --- Round-trip sweep over valid canonical sequences (AC-01 domain) --------------------------


def _valid_sequences() -> list[list[Message]]:
    sequences: list[list[Message]] = [
        [],
        [Message(Role.USER, "")],
        [Message(Role.SYSTEM, "s"), Message(Role.USER, "u")],
        [Message(Role.SYSTEM, "s1"), Message(Role.SYSTEM, "s2"), Message(Role.USER, "u")],
        [Message(Role.SYSTEM, "s", is_external=True)],
        [Message(Role.USER, "ñandú 🙂 \n línea", is_external=True)],
        [
            Message(Role.SYSTEM, "sys"),
            Message(Role.USER, "u", is_external=True),
            Message(
                Role.ASSISTANT,
                "t",
                tool_calls=(_call("c1", "a", x=1, y={"z": [1, 2.5, None, True]}), _call("c2")),
                usage=TokenUsage(10, 20),
            ),
            Message(Role.TOOL, "r1", tool_result=ToolResult("c1", "r1", is_error=True)),
            Message(Role.TOOL, "r2!", tool_result=ToolResult("c2", "r2"), is_external=True),
            Message(Role.USER, "next"),
            Message(Role.ASSISTANT, "done"),
        ],
        [
            Message(Role.USER, "u"),
            Message(Role.ASSISTANT, "", tool_calls=(_call("only"),)),
            Message(Role.TOOL, "", tool_result=ToolResult("only", "")),
            Message(Role.USER, "after tool"),
        ],
        [Message(Role.USER, "a"), Message(Role.USER, "b"), Message(Role.ASSISTANT, "")],
    ]
    return sequences


@pytest.mark.parametrize("messages", _valid_sequences())
def test_ac01_round_trip_is_lossless_for_valid_sequences(
    make: EnvelopeFactory, messages: list[Message]
) -> None:
    assert _roundtrip(make, messages) == messages


def test_ac01_generated_sweep_is_lossless(make: EnvelopeFactory) -> None:
    """Deterministic combinatorial sweep of roles, flags, usage and tool outcomes."""
    count = 0
    for external in (False, True):
        for error in (False, True):
            for usage in (None, TokenUsage(0, 0), TokenUsage(7, 9)):
                for diff in (False, True):
                    for n_sys in (0, 1, 3):
                        for n_calls in (0, 1, 2):
                            messages: list[Message] = [
                                Message(Role.SYSTEM, f"s{i}", is_external=external)
                                for i in range(n_sys)
                            ]
                            messages.append(Message(Role.USER, "u", is_external=external))
                            calls = tuple(_call(f"c{i}") for i in range(n_calls))
                            messages.append(
                                Message(Role.ASSISTANT, "a", tool_calls=calls, usage=usage)
                            )
                            for c in calls:
                                messages.append(
                                    Message(
                                        Role.TOOL,
                                        "other" if diff else "out",
                                        tool_result=ToolResult(c.id, "out", is_error=error),
                                        is_external=external,
                                        usage=usage,
                                    )
                                )
                            assert _roundtrip(make, messages) == messages
                            count += 1
    assert count == 2 * 2 * 3 * 2 * 3 * 3


# --- Payload parity with the unchanged conversion functions ---------------------------------


def test_envelope_payload_equals_the_production_payload_openai() -> None:
    messages = [
        Message(Role.SYSTEM, "s"),
        Message(Role.USER, "u", is_external=True),
        Message(Role.ASSISTANT, "", tool_calls=(_call("c", x=1),)),
        Message(Role.TOOL, "d", tool_result=ToolResult("c", "r", is_error=True)),
    ]
    tools = [ToolDefinition(name="t", description="d", parameters={"type": "object"})]
    env = to_openai_envelope(messages, tools)
    assert env.payload == OpenAIConverter().to_provider_payload(messages, tools)
    assert env.payload["messages"] == to_openai_messages(messages)


def test_envelope_payload_equals_the_production_payload_anthropic() -> None:
    messages = [
        Message(Role.SYSTEM, "s1"),
        Message(Role.SYSTEM, "s2"),
        Message(Role.USER, "u", is_external=True),
        Message(Role.ASSISTANT, "t", tool_calls=(_call("c", x=1),)),
        Message(Role.TOOL, "d", tool_result=ToolResult("c", "r", is_error=True)),
        Message(Role.USER, "next"),
    ]
    tools = [ToolDefinition(name="t", description="d", parameters={"type": "object"})]
    env = to_anthropic_envelope(messages, tools)
    assert env.payload == AnthropicConverter().to_provider_payload(messages, tools)
    assert env.payload == to_anthropic_payload(messages, tools)
    assert len(env.payload["messages"]) == 4  # 2 SYSTEM go to the top-level parameter
    assert len(env.entries) == 6


def test_converter_classes_expose_to_provider_envelope() -> None:
    messages = [Message(Role.USER, "u", is_external=True)]
    for conv in (OpenAIConverter(), AnthropicConverter()):
        assert restore_messages(conv.to_provider_envelope(messages)) == messages


def test_tools_in_envelope_are_part_of_the_payload(make: EnvelopeFactory) -> None:
    tools = [ToolDefinition(name="t", description="d", parameters={"type": "object"})]
    env = make([Message(Role.USER, "u")], tools)
    assert "tools" in env.payload
    assert make([Message(Role.USER, "u")], []).payload["tools"] == []


# --- Tool correlation (section 4.7) ---------------------------------------------------------


def test_duplicate_or_empty_call_ids_are_rejected(make: EnvelopeFactory) -> None:
    dup = [
        Message(Role.ASSISTANT, "", tool_calls=(_call("d"),)),
        Message(Role.ASSISTANT, "", tool_calls=(_call("d"),)),
    ]
    with pytest.raises(ConversionError, match="d"):
        make(dup)
    with pytest.raises(ConversionError):
        make([Message(Role.ASSISTANT, "", tool_calls=(_call(""),))])
    with pytest.raises(ConversionError):
        make([Message(Role.ASSISTANT, "", tool_calls=(_call("x"), _call("x")))])


def test_two_results_for_the_same_call_are_rejected_even_in_partial_window(
    make: EnvelopeFactory,
) -> None:
    messages = [
        Message(Role.ASSISTANT, "", tool_calls=(_call("c"),)),
        Message(Role.TOOL, "1", tool_result=ToolResult("c", "1")),
        Message(Role.TOOL, "2", tool_result=ToolResult("c", "2")),
    ]
    with pytest.raises(ConversionError, match="c"):
        make(messages)
    with pytest.raises(ConversionError):
        make(messages, partial_window=True)


def test_result_before_its_call_is_rejected_even_in_partial_window(make: EnvelopeFactory) -> None:
    messages = [
        Message(Role.TOOL, "1", tool_result=ToolResult("c", "1")),
        Message(Role.ASSISTANT, "", tool_calls=(_call("c"),)),
    ]
    with pytest.raises(ConversionError, match="before"):
        make(messages)
    with pytest.raises(ConversionError, match="before"):
        make(messages, partial_window=True)


def test_empty_result_call_id_is_rejected(make: EnvelopeFactory) -> None:
    with pytest.raises(ConversionError):
        make([Message(Role.TOOL, "x", tool_result=ToolResult("", "x"))], partial_window=True)


def test_orphan_result_needs_partial_window_opt_in(make: EnvelopeFactory) -> None:
    messages = [
        Message(Role.TOOL, "r", tool_result=ToolResult("gone", "r", is_error=True)),
        Message(Role.USER, "next"),
    ]
    with pytest.raises(ConversionError, match="gone"):
        make(messages)
    env = make(messages, partial_window=True)
    assert env.partial_window is True
    assert restore_messages(env) == messages
    assert make([Message(Role.USER, "u")]).partial_window is False


def test_call_without_result_is_allowed(make: EnvelopeFactory) -> None:
    messages = [Message(Role.ASSISTANT, "", tool_calls=(_call("pending"),))]
    assert _roundtrip(make, messages) == messages


# --- Strict JSON in arguments ----------------------------------------------------------------


def test_arguments_that_json_would_coerce_are_rejected(make: EnvelopeFactory) -> None:
    messages = [Message(Role.ASSISTANT, "", tool_calls=(_call("c", pair=(1, 2)),))]
    with pytest.raises(ConversionError):
        make(messages)


# --- Scenario 6/17: identical content, different metadata ------------------------------------


def test_identical_content_keeps_each_conversions_own_metadata(make: EnvelopeFactory) -> None:
    trusted = [Message(Role.USER, "Hola", is_external=False)]
    external = [Message(Role.USER, "Hola", is_external=True)]
    env_a, env_b = make(trusted), make(external)
    assert env_a.payload == env_b.payload
    assert env_a.payload_digest == env_b.payload_digest
    assert env_a.conversion_id != env_b.conversion_id
    assert restore_messages(env_a) == trusted
    assert restore_messages(env_b) == external


def test_scenario_18_wrong_envelope_is_not_detectable_but_returns_that_envelopes_data(
    make: EnvelopeFactory,
) -> None:
    env_a = make([Message(Role.USER, "Hola", is_external=False)])
    env_b = make([Message(Role.USER, "Hola", is_external=True)])
    # Documented limit (D-02 4.1): the library cannot tell which envelope belongs to a request.
    assert restore_messages(env_b)[0].is_external is True
    assert restore_messages(env_a)[0].is_external is False


# --- Scenario 10/25: concurrency --------------------------------------------------------------


async def _convert_and_restore(
    make: EnvelopeFactory, n: int
) -> tuple[list[Message], list[Message]]:
    messages = [
        Message(Role.USER, "same", is_external=bool(n % 2)),
        Message(Role.ASSISTANT, "", tool_calls=(_call(f"c{n}"),), usage=TokenUsage(n, n)),
        Message(Role.TOOL, f"d{n}", tool_result=ToolResult(f"c{n}", "r", is_error=bool(n % 2))),
    ]
    env = make(messages)
    await asyncio.sleep(0)
    restored = restore_messages(env)
    await asyncio.sleep(0)
    return messages, restored


async def test_concurrent_conversions_do_not_contaminate_each_other(make: EnvelopeFactory) -> None:
    results = await asyncio.gather(*(_convert_and_restore(make, n) for n in range(8)))
    for original, restored in results:
        assert restored == original


# --- Scenario 19/20: Anthropic structure --------------------------------------------------------


def test_scenario_19_anthropic_system_prefix_blocks_keep_boundaries() -> None:
    messages = [
        Message(Role.SYSTEM, "A"),
        Message(Role.SYSTEM, "B", is_external=True),
        Message(Role.USER, "u"),
    ]
    env = to_anthropic_envelope(messages)
    assert env.payload["system"] == [
        {"type": "text", "text": "A"},
        {"type": "text", "text": "B"},
    ]
    assert restore_messages(env) == messages


def test_scenario_20_tool_then_user_become_two_user_messages_and_restore_roles() -> None:
    messages = [
        Message(Role.ASSISTANT, "", tool_calls=(_call("c"),)),
        Message(Role.TOOL, "a", tool_result=ToolResult("c", "a")),
        Message(Role.USER, "u"),
    ]
    env = to_anthropic_envelope(messages)
    wire = env.payload["messages"]
    assert [m["role"] for m in wire] == ["assistant", "user", "user"]
    assert [m.role for m in restore_messages(env)] == [Role.ASSISTANT, Role.TOOL, Role.USER]


def test_anthropic_message_count_differs_from_canonical_count() -> None:
    messages = [Message(Role.SYSTEM, "A"), Message(Role.SYSTEM, "B"), Message(Role.USER, "u")]
    env = to_anthropic_envelope(messages)
    assert len(env.payload["messages"]) == 1
    assert len(env.entries) == 3
    assert [e.refs[0].kind for e in env.entries] == ["system_block", "system_block", "message"]


# --- Empty SYSTEM (Product Owner decision) ------------------------------------------------------


def test_empty_system_is_kept_for_openai() -> None:
    messages = [Message(Role.SYSTEM, ""), Message(Role.USER, "u")]
    env = to_openai_envelope(messages)
    assert env.payload["messages"][0] == {"role": "system", "content": ""}
    assert restore_messages(env) == messages


@pytest.mark.parametrize(
    "contents",
    [[""], ["", ""], ["", "A"], ["A", ""], ["", "A", "", "B", ""], ["A", "", "B"]],
)
def test_empty_system_is_omitted_from_anthropic_payload_but_kept_in_the_sidecar(
    contents: list[str],
) -> None:
    messages = [Message(Role.SYSTEM, c, is_external=bool(i % 2)) for i, c in enumerate(contents)]
    messages.append(Message(Role.USER, "u"))
    env = to_anthropic_envelope(messages)
    non_empty = [c for c in contents if c]
    payload = env.payload
    if not non_empty:
        assert "system" not in payload
    elif len(non_empty) == 1:
        assert payload["system"] == non_empty[0]
    else:
        assert payload["system"] == [{"type": "text", "text": c} for c in non_empty]
    assert sum(1 for e in env.entries if e.omitted) == len(contents) - len(non_empty)
    restored = restore_messages(env)
    assert restored == messages  # existence, content, position and flags preserved


def test_payload_only_anthropic_function_still_rejects_empty_system() -> None:
    with pytest.raises(ConversionError, match="empty"):
        to_anthropic_payload([Message(Role.SYSTEM, "")])


# --- Scenario 12/21/24/26 -----------------------------------------------------------------------


def test_scenario_12_restore_requires_an_envelope() -> None:
    with pytest.raises((TypeError, ConversionError)):
        restore_messages(None)  # type: ignore[arg-type]
    with pytest.raises((TypeError, ConversionError)):
        restore_messages({"messages": []})  # type: ignore[arg-type]


def test_scenario_21_mutating_inputs_after_creation_changes_nothing(make: EnvelopeFactory) -> None:
    messages = [
        Message(Role.ASSISTANT, "", tool_calls=(_call("c", nested={"k": [1]}),)),
        Message(Role.TOOL, "r", tool_result=ToolResult("c", "r", is_error=True)),
    ]
    env = make(messages)
    before = restore_messages(env)
    returned = env.payload
    returned["messages"].clear()
    messages[0].tool_calls[0].arguments["nested"]["k"].append(99)
    assert restore_messages(env) == before


def test_scenario_24_responses_never_take_or_use_an_envelope() -> None:
    from harness_agent.adapters.converters import from_anthropic_response, from_openai_response

    with pytest.raises(TypeError):
        from_openai_response({}, envelope=None)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        from_anthropic_response({}, envelope=None)  # type: ignore[call-arg]
    env = to_openai_envelope([Message(Role.USER, "u", is_external=True)])
    response = from_openai_response(
        {
            "choices": [{"message": {"role": "assistant", "content": "hello"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        }
    )
    assert response.content == "hello"
    assert response.usage == TokenUsage(1, 2)
    assert env.payload["messages"][0]["content"] == "u"


def test_scenario_26_message_usage_is_independent_of_response_usage() -> None:
    from harness_agent.adapters.converters import from_openai_response

    messages = [Message(Role.ASSISTANT, "a", usage=TokenUsage(3, 4))]
    restored = restore_messages(to_openai_envelope(messages))
    response = from_openai_response(
        {
            "choices": [{"message": {"role": "assistant", "content": "n"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200},
        }
    )
    assert restored[0].usage == TokenUsage(3, 4)
    assert response.usage == TokenUsage(100, 200)


# --- Invalid canonical input keeps failing closed through the envelope path --------------------


def test_invalid_canonical_sequences_are_rejected_by_the_envelope_path(
    make: EnvelopeFactory,
) -> None:
    with pytest.raises(ConversionError, match="prefix"):
        make([Message(Role.USER, "u"), Message(Role.SYSTEM, "late")])
    with pytest.raises(ConversionError):
        make([Message(Role.USER, "u", tool_calls=(_call("c"),))])
    with pytest.raises(ConversionError):
        make([Message(Role.TOOL, "x")])
