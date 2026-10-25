"""Token estimation and calibration (HU-02-01, Sp2-09)."""

from __future__ import annotations

import pytest

from harness_agent.core import Message, Role, ToolCall, ToolDefinition, ToolResult
from harness_agent.core.context.estimator import (
    MAX_FACTOR,
    MESSAGE_OVERHEAD_TOKENS,
    MIN_FACTOR,
    TokenEstimator,
    estimate_message,
    estimate_messages,
    estimate_text,
    estimate_tool_definition,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("", 0), ("a", 1), ("abcd", 1), ("abcde", 2), ("x" * 400, 100), ("ñ" * 5, 2)],
)
def test_estimate_text_is_ceil_of_chars_over_four(text: str, expected: int) -> None:
    assert estimate_text(text) == expected


def test_message_counts_content_plus_fixed_overhead() -> None:
    message = Message(Role.USER, "abcdefgh")
    assert estimate_message(message) == 2 + MESSAGE_OVERHEAD_TOKENS


def test_empty_message_still_costs_the_overhead() -> None:
    assert estimate_message(Message(Role.ASSISTANT, "")) == MESSAGE_OVERHEAD_TOKENS


def test_tool_calls_count_name_and_arguments_whatever_the_key_order() -> None:
    first = Message(
        Role.ASSISTANT, "", (ToolCall("c1", "leer_archivo", {"a": 1, "b": {"y": 2, "x": 3}}),)
    )
    second = Message(
        Role.ASSISTANT, "", (ToolCall("c1", "leer_archivo", {"b": {"x": 3, "y": 2}, "a": 1}),)
    )
    assert estimate_message(first) == estimate_message(second)
    assert estimate_message(first) > MESSAGE_OVERHEAD_TOKENS + estimate_text("leer_archivo")


def test_tool_result_content_is_counted() -> None:
    message = Message(Role.TOOL, "", tool_result=ToolResult("c1", "z" * 40, True))
    assert estimate_message(message) == 10 + MESSAGE_OVERHEAD_TOKENS


def test_unserializable_arguments_do_not_break_the_estimation() -> None:
    message = Message(Role.ASSISTANT, "", (ToolCall("c1", "t", {"v": object()}),))
    assert estimate_message(message) > MESSAGE_OVERHEAD_TOKENS


def test_tool_definition_counts_name_description_and_schema() -> None:
    bare = ToolDefinition("t", "d")
    rich = ToolDefinition(
        "t", "d" * 40, {"type": "object", "properties": {"path": {"type": "string"}}}
    )
    assert estimate_tool_definition(bare) >= 1
    assert estimate_tool_definition(rich) > estimate_tool_definition(bare) + 9


def test_estimate_messages_is_the_sum() -> None:
    messages = [Message(Role.USER, "abcd"), Message(Role.ASSISTANT, "abcdefgh")]
    assert estimate_messages(messages) == sum(estimate_message(m) for m in messages)
    assert estimate_messages([]) == 0


def test_a_fresh_session_has_factor_one() -> None:
    estimator = TokenEstimator()
    assert estimator.factor("s1") == 1.0
    assert estimator.calibrated("s1", 101) == 101


def test_observe_corrects_the_estimate_with_the_reported_value() -> None:
    estimator = TokenEstimator()
    estimator.observe("s1", 1000, 1500)
    assert estimator.factor("s1") == pytest.approx(1.5)
    assert abs(estimator.calibrated("s1", 1000) - 1500) <= 1


def test_the_last_observation_wins() -> None:
    estimator = TokenEstimator()
    estimator.observe("s1", 1000, 1500)
    estimator.observe("s1", 1000, 800)
    assert estimator.calibrated("s1", 1000) == 800


@pytest.mark.parametrize(("raw", "reported"), [(1000, 0), (1000, -5), (0, 100), (-3, 100)])
def test_observe_ignores_unusable_reports(raw: int, reported: int) -> None:
    estimator = TokenEstimator()
    estimator.observe("s1", 1000, 1200)
    estimator.observe("s1", raw, reported)
    assert estimator.factor("s1") == pytest.approx(1.2)


def test_the_factor_is_clamped() -> None:
    estimator = TokenEstimator()
    estimator.observe("s1", 10, 1_000_000)
    assert estimator.factor("s1") == MAX_FACTOR
    estimator.observe("s1", 1_000_000, 10)
    assert estimator.factor("s1") == MIN_FACTOR
    assert estimator.calibrated("s1", 100) == 25


def test_sessions_are_independent() -> None:
    estimator = TokenEstimator()
    estimator.observe("s1", 1000, 2000)
    assert estimator.factor("s2") == 1.0
    assert estimator.calibrated("s2", 1000) == 1000
