"""Shared validation helpers for provider wire-format converters.

Every helper raises ``ConversionError`` for invalid EXTERNAL data. Only the exceptions raised by
the standard library while decoding or encoding JSON are translated; any other exception is a
programming error and is deliberately allowed to propagate.
"""

from __future__ import annotations

import json
from typing import Any

from harness_agent.adapters.converters.base import ConversionError
from harness_agent.core.entities import Message, Role, TokenUsage

_MAX_REPR = 80


def short_repr(value: object, limit: int = _MAX_REPR) -> str:
    """Return a bounded ``repr`` so diagnostics never embed arbitrarily large payloads."""
    text = repr(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... (+{len(text) - limit} chars)"


def parse_tool_arguments(raw: object, call_id: str, name: str) -> dict[str, Any]:
    """Decode tool-call arguments into a JSON object (``dict``).

    Accepts a JSON string holding an object, an empty/blank string (``{}``) or a ready dict.
    Rejects lists, scalars, ``null`` and any other Python type.
    """
    where = f"tool call '{call_id}' ({name})"
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConversionError(
                f"Malformed JSON in arguments of {where}: {short_repr(raw)}: {exc.msg}"
            ) from exc
        if not isinstance(parsed, dict):
            raise ConversionError(
                f"Arguments of {where} must be a JSON object, "
                f"got {type(parsed).__name__}: {short_repr(raw)}"
            )
        return parsed
    raise ConversionError(
        f"Arguments of {where} must be a JSON object string or dict, "
        f"got {type(raw).__name__}: {short_repr(raw)}"
    )


def ensure_json_serializable(arguments: dict[str, Any], call_id: str, name: str) -> str:
    """Serialize arguments to strict JSON or fail closed (no silent coercion, no NaN)."""
    try:
        return json.dumps(arguments, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ConversionError(
            f"Arguments of tool call '{call_id}' ({name}) are not JSON-serializable: {exc}"
        ) from exc


def require_dict(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConversionError(f"{where} must be an object, got {type(value).__name__}")
    return value


def require_list(value: object, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise ConversionError(f"{where} must be a list, got {type(value).__name__}")
    return value


def require_non_empty_str(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConversionError(f"{where} must be a non-empty string, got {short_repr(value)}")
    return value


def require_text(value: object, where: str, *, none_as_empty: bool = False) -> str:
    """Return ``value`` when it is text; optionally map ``None`` to the empty string."""
    if value is None and none_as_empty:
        return ""
    if not isinstance(value, str):
        raise ConversionError(
            f"{where} must be text (str), got {type(value).__name__}: {short_repr(value)}"
        )
    return value


def require_bool(value: object, where: str, *, default: bool = False) -> bool:
    """Return a real ``bool``; an absent value (``None``) yields ``default``."""
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ConversionError(f"{where} must be a boolean, got {short_repr(value)}")
    return value


def parse_token_count(value: object, where: str) -> int:
    """Return a non-negative ``int``; ``None`` is treated as 0 (provider omitted the field)."""
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConversionError(f"{where} must be an integer, got {short_repr(value)}")
    if value < 0:
        raise ConversionError(f"{where} must be non-negative, got {value}")
    return value


def parse_usage(
    usage_data: object, input_key: str, output_key: str, where: str
) -> TokenUsage | None:
    """Build ``TokenUsage`` from a provider usage object (``None`` means not reported)."""
    if usage_data is None:
        return None
    usage = require_dict(usage_data, f"{where} usage")
    return TokenUsage(
        input_tokens=parse_token_count(usage.get(input_key), f"{where} usage.{input_key}"),
        output_tokens=parse_token_count(usage.get(output_key), f"{where} usage.{output_key}"),
    )


def validate_canonical_messages(messages: list[Message]) -> None:
    """Reject canonical sequences that no converter may translate without losing data.

    Rules (both providers, both directions):

    * SYSTEM messages are valid only as a contiguous prefix at the start of the conversation
      (Product Owner decision of 2026-10-18, HU-07-01 / AC-01). A SYSTEM message after any
      USER, ASSISTANT or TOOL message is rejected; nothing is reordered or normalized.
    * ``tool_calls`` belong to ASSISTANT messages only and ``tool_result`` to TOOL messages only;
      a TOOL message requires its ``tool_result``. Converters would otherwise drop these fields
      silently (audit defect D10).

    ``Message.content`` of a TOOL message is deliberately NOT compared with
    ``ToolResult.content``: that difference is defect D9, handled by the pending design D-02.
    """
    for position, msg in enumerate(messages):
        where = f"Invalid canonical message at position {position} (role {msg.role.name})"
        if msg.role == Role.SYSTEM and position > 0 and messages[position - 1].role != Role.SYSTEM:
            previous = messages[position - 1]
            raise ConversionError(
                f"{where}: SYSTEM messages are only valid as a contiguous prefix at the start "
                f"of the conversation, but this one follows a {previous.role.value} message "
                f"at position {position - 1}."
            )
        if msg.tool_calls and msg.role != Role.ASSISTANT:
            raise ConversionError(
                f"{where}: field 'tool_calls' is only valid on ASSISTANT messages and would "
                f"be dropped by the conversion ({len(msg.tool_calls)} call(s))."
            )
        if msg.tool_result is not None and msg.role != Role.TOOL:
            raise ConversionError(
                f"{where}: field 'tool_result' is only valid on TOOL messages and would be "
                "dropped by the conversion."
            )
        if msg.role == Role.TOOL and msg.tool_result is None:
            raise ConversionError(f"{where}: a TOOL message must contain a non-null tool_result.")


def validate_tool_correlation(messages: list[Message], *, partial_window: bool = False) -> None:
    """Check that tool calls and results correlate unambiguously (design D-02, section 4.7).

    Always rejected: empty or duplicate ``ToolCall`` ids, empty or duplicated ``ToolResult``
    ``call_id`` and a result placed before its call. A result whose call is not in the window is
    rejected unless ``partial_window`` is True (trimmed or resumed windows). A call without a
    result is allowed (the loop may be mid-turn).
    """
    call_positions: dict[str, int] = {}
    for position, msg in enumerate(messages):
        for call in msg.tool_calls:
            if not call.id:
                raise ConversionError(f"Tool call at message {position} has an empty id.")
            if call.id in call_positions:
                raise ConversionError(
                    f"Duplicate tool call id {call.id!r} at messages "
                    f"{call_positions[call.id]} and {position}; correlation would be ambiguous."
                )
            call_positions[call.id] = position

    seen_results: set[str] = set()
    for position, msg in enumerate(messages):
        if msg.tool_result is None:
            continue
        call_id = msg.tool_result.call_id
        if not call_id:
            raise ConversionError(f"Tool result at message {position} has an empty call_id.")
        if call_id in seen_results:
            raise ConversionError(
                f"More than one tool result for call id {call_id!r} (message {position})."
            )
        seen_results.add(call_id)
        call_position = call_positions.get(call_id)
        if call_position is None:
            if not partial_window:
                raise ConversionError(
                    f"Tool result at message {position} references call id {call_id!r}, which is "
                    "not in the window; pass partial_window=True for trimmed windows."
                )
        elif call_position > position:
            raise ConversionError(
                f"Tool result for {call_id!r} at message {position} appears before its call "
                f"(message {call_position})."
            )


def ensure_strict_json_value(value: object, where: str) -> None:
    """Fail closed when ``value`` would be silently coerced by a JSON round trip."""
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ConversionError(f"{where} is not strict JSON: {exc}") from exc
    if decoded != value:
        raise ConversionError(
            f"{where} would be altered by a JSON round trip (non-string keys or tuples)."
        )
