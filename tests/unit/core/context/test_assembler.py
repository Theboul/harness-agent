"""Context assembler: frozen prefix, history and usage correction (HU-02-01, Sp2-10)."""

from __future__ import annotations

import pytest

from harness_agent.core import Message, Role, TokenUsage, ToolCall, ToolDefinition
from harness_agent.core.context import ContextConfigError
from harness_agent.core.context.assembler import ContextAssembler
from harness_agent.core.context.estimator import (
    TokenEstimator,
    estimate_messages,
    estimate_text,
    estimate_tool_definition,
)
from harness_agent.core.context.prefix import PrefixSpec

SPEC = PrefixSpec("Be precise.", ("Ask first.",), "Windows 11", "PowerShell")


class Source:
    """Tool definitions source that counts how many times it was queried."""

    def __init__(self, *names: str) -> None:
        self.names = list(names)
        self.calls = 0

    def __call__(self) -> list[ToolDefinition]:
        self.calls += 1
        return [ToolDefinition(name, f"Tool {name}.", {"type": "object"}) for name in self.names]


def history() -> list[Message]:
    return [
        Message(Role.USER, "List the files."),
        Message(Role.ASSISTANT, "", (ToolCall("c1", "listar_archivos", {"path": "."}),)),
    ]


def test_assemble_returns_prefix_then_a_copy_of_the_history() -> None:
    assembler = ContextAssembler(SPEC, Source("a", "b"))
    original = history()
    context = assembler.assemble("s1", original)
    assert context.provider_messages()[0] is context.prefix.system_message
    assert context.provider_messages()[0].role is Role.SYSTEM
    assert list(context.history) == original
    assert all(a is not b for a, b in zip(context.history, original, strict=True))
    assert context.tools == context.prefix.tools


def test_assemble_does_not_mutate_the_received_history() -> None:
    assembler = ContextAssembler(SPEC, Source("a"))
    original = history()
    snapshot = list(original)
    assembler.assemble("s1", original)
    assert original == snapshot


def test_empty_history_estimates_the_prefix_only() -> None:
    assembler = ContextAssembler(SPEC, Source("a"))
    context = assembler.assemble("s1", [])
    expected = estimate_messages([context.prefix.system_message]) + sum(
        estimate_tool_definition(t) for t in context.tools
    )
    assert context.history == ()
    assert context.raw_tokens == expected > 0
    assert context.estimated_tokens == expected


def test_the_estimate_adds_prefix_tools_and_messages() -> None:
    assembler = ContextAssembler(SPEC, Source("a", "b"))
    context = assembler.assemble("s1", history())
    expected = estimate_messages(context.provider_messages()) + sum(
        estimate_tool_definition(t) for t in context.tools
    )
    assert context.raw_tokens == expected


def test_the_prefix_is_built_once_per_session() -> None:
    source = Source("a")
    assembler = ContextAssembler(SPEC, source)
    first = assembler.assemble("s1", [])
    second = assembler.assemble("s1", history())
    assert source.calls == 1
    assert second.prefix is first.prefix


def test_the_prefix_survives_changes_of_the_tool_source() -> None:
    source = Source("a", "b")
    assembler = ContextAssembler(SPEC, source)
    first = assembler.assemble("s1", [])
    source.names = ["z", "b"]
    assert assembler.assemble("s1", history()).prefix.fingerprint == first.prefix.fingerprint
    assert assembler.assemble("s2", []).prefix.fingerprint != first.prefix.fingerprint


@pytest.mark.parametrize("session_id", ["", "   "])
def test_an_empty_session_id_is_rejected(session_id: str) -> None:
    with pytest.raises(ContextConfigError, match="sesión"):
        ContextAssembler(SPEC, Source("a")).assemble(session_id, [])


def test_an_invalid_tool_source_fails_closed_and_stores_nothing() -> None:
    source = Source("a", "a")
    assembler = ContextAssembler(SPEC, source)
    with pytest.raises(ContextConfigError):
        assembler.assemble("s1", [])
    source.names = ["a"]
    assert assembler.assemble("s1", []).prefix.tools[0].name == "a"


def test_record_usage_calibrates_with_the_reported_input() -> None:
    assembler = ContextAssembler(SPEC, Source("a"))
    context = assembler.assemble("s1", history())
    reported = context.raw_tokens * 2 + 7
    assembler.record_usage("s1", TokenUsage(input_tokens=reported, output_tokens=50))
    again = assembler.assemble("s1", history())
    assert abs(again.estimated_tokens - reported) <= 1
    assert again.raw_tokens == context.raw_tokens


def test_record_usage_without_usage_or_with_zero_changes_nothing() -> None:
    assembler = ContextAssembler(SPEC, Source("a"))
    base = assembler.assemble("s1", history())
    assembler.record_usage("s1", None)
    assembler.record_usage("s1", TokenUsage(0, 10))
    assert assembler.assemble("s1", history()).estimated_tokens == base.raw_tokens


def test_record_usage_without_a_previous_assembly_does_nothing() -> None:
    estimator = TokenEstimator()
    assembler = ContextAssembler(SPEC, Source("a"), estimator)
    assembler.record_usage("s1", TokenUsage(1000, 10))
    assert estimator.factor("s1") == 1.0


def test_a_usage_is_consumed_once() -> None:
    estimator = TokenEstimator()
    assembler = ContextAssembler(SPEC, Source("a"), estimator)
    context = assembler.assemble("s1", history())
    assembler.record_usage("s1", TokenUsage(context.raw_tokens * 2, 1))
    factor = estimator.factor("s1")
    assembler.record_usage("s1", TokenUsage(context.raw_tokens * 3, 1))
    assert estimator.factor("s1") == factor


def test_calibration_is_per_session() -> None:
    assembler = ContextAssembler(SPEC, Source("a"))
    first = assembler.assemble("s1", history())
    assembler.assemble("s2", history())
    assembler.record_usage("s1", TokenUsage(first.raw_tokens * 3, 1))
    other = assembler.assemble("s2", history())
    assert other.estimated_tokens == other.raw_tokens


def test_estimate_text_is_used_for_the_prefix_text() -> None:
    context = ContextAssembler(SPEC, Source()).assemble("s1", [])
    assert estimate_text(context.prefix.system_message.content) > 0
