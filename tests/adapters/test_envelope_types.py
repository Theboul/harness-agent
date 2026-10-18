"""T019: envelope types, strict JSON snapshot, digests and ``matches`` (D-02 section 4.2/4.6)."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from harness_agent.adapters.converters import ConversionError
from harness_agent.adapters.converters.sidecar import (
    ConversionEnvelope,
    MessageMeta,
    WireRef,
    canonical_json,
    content_digest,
)
from harness_agent.core.entities import Role, TokenUsage


def _meta(index: int = 0) -> MessageMeta:
    return MessageMeta(
        index=index,
        role=Role.USER,
        refs=(WireRef(kind="message", message_index=index),),
        wire_digest="x",
        is_external=True,
    )


def _envelope(payload: dict[str, Any] | None = None) -> ConversionEnvelope:
    return ConversionEnvelope._create(
        provider="openai",
        payload=payload
        if payload is not None
        else {"messages": [{"role": "user", "content": "hi"}]},
        entries=(_meta(),),
    )


def test_public_constructor_is_not_usable() -> None:
    with pytest.raises(TypeError):
        ConversionEnvelope(  # type: ignore[call-arg]
            provider="openai", payload={}, entries=()
        )


def test_envelope_attributes_are_read_only() -> None:
    env = _envelope()
    with pytest.raises(AttributeError):
        env.provider = "anthropic"
    with pytest.raises(AttributeError):
        env.partial_window = True


def test_wire_ref_and_meta_are_frozen_dataclasses() -> None:
    meta = _meta()
    with pytest.raises(dataclasses.FrozenInstanceError):
        meta.is_external = False  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        meta.refs[0].kind = "system"  # type: ignore[misc]
    assert isinstance(meta.refs, tuple)


def test_meta_defaults_do_not_carry_optional_metadata() -> None:
    meta = _meta()
    assert meta.tool_call_id is None
    assert meta.tool_is_error is None
    assert meta.tool_message_content is None
    assert meta.usage is None
    assert meta.omitted is False
    assert MessageMeta(
        index=0,
        role=Role.ASSISTANT,
        refs=(),
        wire_digest="",
        is_external=False,
        usage=TokenUsage(1, 2),
    ).usage == TokenUsage(1, 2)


def test_payload_returns_a_fresh_deep_copy_on_each_access() -> None:
    env = _envelope()
    first = env.payload
    first["messages"][0]["content"] = "tampered"
    first["extra"] = 1
    assert env.payload == {"messages": [{"role": "user", "content": "hi"}]}
    assert env.payload is not env.payload


def test_mutating_the_original_payload_after_creation_does_not_change_the_envelope() -> None:
    original = {"messages": [{"role": "user", "content": "hi"}]}
    env = _envelope(original)
    original["messages"][0]["content"] = "changed"
    original["messages"].append({"role": "user", "content": "more"})
    assert env.payload == {"messages": [{"role": "user", "content": "hi"}]}
    assert env.matches({"messages": [{"role": "user", "content": "hi"}]})


def test_digest_is_sha256_hex_and_stable() -> None:
    a = _envelope()
    b = _envelope()
    assert len(a.payload_digest) == 64
    assert a.payload_digest == b.payload_digest
    assert a.payload_digest == content_digest(canonical_json(a.payload))


def test_digest_ignores_key_order_but_not_content() -> None:
    a = _envelope({"a": 1, "b": 2})
    b = _envelope({"b": 2, "a": 1})
    c = _envelope({"a": 1, "b": 3})
    assert a.payload_digest == b.payload_digest
    assert a.payload_digest != c.payload_digest


def test_matches_detects_altered_copies() -> None:
    env = _envelope()
    good = env.payload
    assert env.matches(good)
    changed_content = env.payload
    changed_content["messages"][0]["content"] = "other"
    changed_role = env.payload
    changed_role["messages"][0]["role"] = "assistant"
    extra_message = env.payload
    extra_message["messages"].append({"role": "user", "content": "x"})
    extra_key = env.payload
    extra_key["tools"] = []
    for copy in (changed_content, changed_role, extra_message, extra_key):
        assert not env.matches(copy)


def test_matches_is_false_for_non_json_payloads_instead_of_raising() -> None:
    env = _envelope()
    assert env.matches({"messages": float("nan")}) is False
    assert env.matches({"messages": object()}) is False


def test_conversion_id_is_unique_per_envelope_and_not_part_of_the_payload() -> None:
    a, b = _envelope(), _envelope()
    assert a.conversion_id != b.conversion_id
    assert a.conversion_id not in canonical_json(a.payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"x": float("nan")},
        {"x": float("inf")},
        {"x": {1, 2}},
        {"x": object()},
        {1: "int key"},  # silently coerced to "1" by json
        {"x": (1, 2)},  # silently coerced to a list by json
        {"x": b"bytes"},
    ],
)
def test_non_strict_json_payloads_are_rejected(payload: dict[Any, Any]) -> None:
    with pytest.raises(ConversionError):
        _envelope(payload)


def test_canonical_json_is_sorted_compact_and_keeps_unicode() -> None:
    assert canonical_json({"b": "ñ", "a": [1, {"d": 1, "c": 2}]}) == (
        '{"a":[1,{"c":2,"d":1}],"b":"ñ"}'
    )


def test_entries_are_an_immutable_tuple() -> None:
    env = _envelope()
    assert isinstance(env.entries, tuple)
    assert env.entries[0].is_external is True


def test_text_that_cannot_be_encoded_is_rejected_not_leaked_as_unicode_error() -> None:
    with pytest.raises(ConversionError):
        _envelope({"messages": [{"role": "user", "content": "bad \ud800 surrogate"}]})
