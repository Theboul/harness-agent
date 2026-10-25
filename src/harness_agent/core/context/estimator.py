"""Heuristic token estimation with per-session calibration (HU-02-01, RF-2.1).

The core cannot use a third-party tokenizer, so a text costs ``ceil(characters / 4)`` tokens.
That is only an approximation: after each provider answer the reported input consumption
corrects it through a per-session factor (rule 1 of the story), kept exact with ``Fraction`` so
the same content estimated again matches the reported value.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from fractions import Fraction

from harness_agent.core.entities import Message
from harness_agent.core.interfaces.provider import ToolDefinition

CHARS_PER_TOKEN = 4
# Role markers and delimiters that every message costs regardless of its content.
MESSAGE_OVERHEAD_TOKENS = 4
MIN_FACTOR = 0.25
MAX_FACTOR = 4.0
_MIN_RATIO = Fraction(1, 4)
_MAX_RATIO = Fraction(4)


def estimate_text(text: str) -> int:
    """Estimate the tokens of ``text``: ``ceil(characters / 4)``, 0 for the empty text."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def _serialize(value: object) -> str:
    """Deterministic JSON: sorted keys, and unserializable leaves fall back to ``str``."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def estimate_message(message: Message) -> int:
    """Estimate one message: content, tool calls (name and arguments), result and overhead."""
    total = MESSAGE_OVERHEAD_TOKENS + estimate_text(message.content)
    for call in message.tool_calls:
        total += estimate_text(call.name) + estimate_text(_serialize(call.arguments))
    if message.tool_result is not None:
        total += estimate_text(message.tool_result.content)
    return total


def estimate_tool_definition(definition: ToolDefinition) -> int:
    """Estimate a tool declaration: name, description and parameter schema."""
    return (
        estimate_text(definition.name)
        + estimate_text(definition.description)
        + estimate_text(_serialize(definition.parameters))
    )


def estimate_messages(messages: Sequence[Message]) -> int:
    """Estimate a list of messages as the sum of each one."""
    return sum(estimate_message(message) for message in messages)


class TokenEstimator:
    """Keeps one calibration factor per session and applies it to raw estimates."""

    def __init__(self) -> None:
        self._ratios: dict[str, Fraction] = {}

    def factor(self, session_id: str) -> float:
        """Return the session calibration factor (1.0 until a usage is observed)."""
        return float(self._ratios.get(session_id, Fraction(1)))

    def calibrated(self, session_id: str, raw_tokens: int) -> int:
        """Apply the session factor to a raw estimate, rounding up."""
        return math.ceil(raw_tokens * self._ratios.get(session_id, Fraction(1)))

    def observe(self, session_id: str, raw_tokens: int, reported_input_tokens: int) -> None:
        """Correct the factor with what the provider reported for a call estimated at ``raw``.

        Unusable reports (zero or negative on either side) leave the factor untouched; the
        ratio is clamped to [0.25, 4.0] so an anomalous report cannot make estimates useless.
        """
        if raw_tokens <= 0 or reported_input_tokens <= 0:
            return
        ratio = Fraction(reported_input_tokens, raw_tokens)
        self._ratios[session_id] = min(_MAX_RATIO, max(_MIN_RATIO, ratio))
