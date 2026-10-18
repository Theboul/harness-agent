"""Bidirectional wire-format converter for Anthropic Messages API v1.

Provides conversion between HARNESS canonical models and Anthropic API schemas.
Enforces fail-closed error handling: any external payload that cannot be represented faithfully
raises ``ConversionError`` instead of being coerced, merged or dropped.

Design notes (audit defects D4-D6):

* Text blocks of one message are joined with ``"\\n"``. This is the approved textual
  representation of multi-block text; boundaries between adjacent text blocks are normalized.
* A user message that mixes ``tool_result`` blocks with any other block is rejected: the
  canonical model carries one ``TOOL`` message per result and cannot record the grouping, so
  converting it would silently lose data. Local correlation metadata would be needed.
* In an assistant message, text must precede ``tool_use`` blocks (canonical order).
* The top-level ``system`` parameter is a plain string for a single leading system message and a
  list of text blocks for several, which keeps their boundaries and order. SYSTEM messages are
  valid only as a contiguous prefix (Product Owner decision of 2026-10-18); a SYSTEM message after
  a non-system message is an invalid canonical sequence and is rejected by
  ``validate_canonical_messages`` (no silent hoisting or reordering).
* ``tool_calls`` / ``tool_result`` on a role that cannot carry them are rejected, not dropped.

Known limitation of the payload-only functions (audit defects D1/D8/D9): ``Message.is_external``,
``Message.usage`` and a TOOL ``Message.content`` that differs from ``ToolResult.content`` have no
wire representation. ``to_anthropic_envelope`` + ``restore_messages`` (design D-02,
``sidecar.py``) keep
them in a local sidecar. An empty SYSTEM message cannot be represented in the ``system`` parameter:
the payload-only function rejects it, the envelope path omits it from the payload and records its
existence, content and position in the sidecar (Product Owner decision, 2026-10-18).
"""

from __future__ import annotations

import dataclasses
import warnings
from typing import Any

from harness_agent.adapters.converters._validation import (
    ensure_json_serializable,
    ensure_strict_json_value,
    parse_usage,
    require_bool,
    require_dict,
    require_list,
    require_non_empty_str,
    require_text,
    short_repr,
    validate_canonical_messages,
    validate_tool_correlation,
)
from harness_agent.adapters.converters.base import ConversionError
from harness_agent.adapters.converters.sidecar import (
    ConversionEnvelope,
    MessageMeta,
    WireRef,
    meta_for_message,
    resolve_ref,
    verify_structure,
)
from harness_agent.core.entities import (
    Message,
    Role,
    ToolCall,
    ToolResult,
)
from harness_agent.core.interfaces.provider import ProviderResponse, ToolDefinition

_KNOWN_BLOCK_TYPES = ("text", "tool_use", "tool_result")


def _system_param(
    messages: list[Message], *, omit_empty: bool = False
) -> tuple[str | list[dict[str, str]] | None, int, list[tuple[WireRef, ...]]]:
    """Extract leading system messages into the ``system`` parameter.

    Returns the parameter (or ``None``), the index of the first non-system message and, per system
    message, the wire references it maps to (empty tuple for an omitted empty message). Empty
    messages are rejected unless ``omit_empty`` is set (envelope path, recorded in the sidecar).
    """
    leading: list[str] = []
    index = 0
    while index < len(messages) and messages[index].role == Role.SYSTEM:
        content = messages[index].content
        if content:
            leading.append(content)
        elif not omit_empty:
            raise ConversionError(
                f"System message at position {index} is empty and cannot be represented "
                "in the Anthropic 'system' parameter."
            )
        index += 1

    refs: list[tuple[WireRef, ...]] = []
    block = 0
    for position in range(index):
        if not messages[position].content:
            refs.append(())
        elif len(leading) == 1:
            refs.append((WireRef(kind="system"),))
        else:
            refs.append((WireRef(kind="system_block", block_index=block),))
            block += 1

    if not leading:
        return None, index, refs
    if len(leading) == 1:
        return leading[0], index, refs
    return [{"type": "text", "text": text} for text in leading], index, refs


def _build_anthropic(
    messages: list[Message],
    tools: list[ToolDefinition] | None,
    *,
    omit_empty_system: bool,
) -> tuple[dict[str, Any], list[tuple[WireRef, ...]]]:
    """Build the payload and, per canonical message, the wire references it maps to."""
    validate_canonical_messages(messages)
    system_param, first_other, refs = _system_param(messages, omit_empty=omit_empty_system)
    anthropic_msgs: list[dict[str, Any]] = []

    for msg in messages[first_other:]:
        refs.append((WireRef(kind="message", message_index=len(anthropic_msgs)),))
        if msg.role == Role.USER:
            anthropic_msgs.append({"role": "user", "content": msg.content})
        elif msg.role == Role.ASSISTANT:
            if msg.tool_calls:
                blocks: list[dict[str, Any]] = []
                if msg.content:
                    blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    if not isinstance(tc.arguments, dict):
                        raise ConversionError(
                            f"ToolCall arguments must be dict, got {type(tc.arguments)}"
                        )
                    ensure_json_serializable(tc.arguments, tc.id, tc.name)
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        }
                    )
                anthropic_msgs.append({"role": "assistant", "content": blocks})
            else:
                anthropic_msgs.append({"role": "assistant", "content": msg.content})
        elif msg.role == Role.TOOL:
            if msg.tool_result is None:  # unreachable after validation; narrows the type
                raise ConversionError("Message with role TOOL must contain a non-null tool_result.")
            # In Anthropic API, tool results are represented as tool_result
            # content blocks inside a user message
            result_block: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": msg.tool_result.call_id,
                "content": msg.tool_result.content,
                "is_error": msg.tool_result.is_error,
            }
            anthropic_msgs.append(
                {
                    "role": "user",
                    "content": [result_block],
                }
            )
        else:
            raise ConversionError(f"Unsupported canonical role: {msg.role}")

    payload: dict[str, Any] = {
        "messages": anthropic_msgs,
    }

    if system_param is not None:
        payload["system"] = system_param

    if tools is not None:
        if not tools:
            payload["tools"] = []
        else:
            anthropic_tools: list[dict[str, Any]] = []
            for td in tools:
                if not isinstance(td.parameters, dict):
                    raise ConversionError(
                        f"ToolDefinition parameters must be dict, got {type(td.parameters)}"
                    )
                anthropic_tools.append(
                    {
                        "name": td.name,
                        "description": td.description,
                        "input_schema": td.parameters,
                    }
                )
            payload["tools"] = anthropic_tools

    return payload, refs


def to_anthropic_payload(
    messages: list[Message],
    tools: list[ToolDefinition] | None = None,
) -> dict[str, Any]:
    """Convert canonical messages and tools to Anthropic Messages API v1 payload."""
    payload, _ = _build_anthropic(messages, tools, omit_empty_system=False)
    return payload


def to_anthropic_envelope(
    messages: list[Message],
    tools: list[ToolDefinition] | None = None,
    *,
    partial_window: bool = False,
) -> ConversionEnvelope:
    """Convert to an Anthropic payload plus the local metadata needed to restore it exactly.

    Empty SYSTEM messages are omitted from the payload (the ``system`` parameter cannot represent
    them) and kept in the sidecar. Everything else in the payload equals ``to_anthropic_payload``.
    """
    validate_canonical_messages(messages)
    validate_tool_correlation(messages, partial_window=partial_window)
    for msg in messages:
        for call in msg.tool_calls:
            ensure_strict_json_value(call.arguments, f"Arguments of tool call {call.id!r}")
    payload, refs = _build_anthropic(messages, tools, omit_empty_system=True)
    snapshot = ConversionEnvelope._create(provider="anthropic", payload=payload, entries=()).payload
    entries = tuple(
        meta_for_message(
            index,
            msg,
            refs[index],
            [resolve_ref(snapshot, ref) for ref in refs[index]],
            omitted=not refs[index],
        )
        for index, msg in enumerate(messages)
    )
    return ConversionEnvelope._create(
        provider="anthropic", payload=payload, entries=entries, partial_window=partial_window
    )


def _block_type(block: dict[str, Any], where: str) -> str:
    """Return the block type, rejecting types outside the supported set."""
    block_type = block.get("type")
    if block_type not in _KNOWN_BLOCK_TYPES:
        raise ConversionError(f"Unsupported Anthropic block type in {where}: {block_type!r}")
    return str(block_type)


def _text_of(block: dict[str, Any], where: str) -> str:
    return require_text(block.get("text"), f"{where}.text")


def _parse_tool_use(block: dict[str, Any], where: str) -> ToolCall:
    tc_id = require_non_empty_str(block.get("id"), f"{where}.id")
    name = require_non_empty_str(block.get("name"), f"{where}.name")
    raw_input = block.get("input")
    if not isinstance(raw_input, dict):
        raise ConversionError(
            f"tool_use input of '{tc_id}' ({name}) must be a JSON object, "
            f"got {type(raw_input).__name__}: {short_repr(raw_input)}"
        )
    return ToolCall(id=tc_id, name=name, arguments=raw_input)


def _tool_result_text(content: object, where: str) -> str:
    """Return the textual form of a ``tool_result`` content.

    Approved representation: ``str`` as is; a list made only of ``text`` blocks joined with
    newlines; absent content is empty text. Anything else is rejected.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for index, item in enumerate(content):
            item_where = f"{where}.content[{index}]"
            block = require_dict(item, item_where)
            if block.get("type") != "text":
                raise ConversionError(
                    f"{item_where} has block type {block.get('type')!r}; only text blocks "
                    "can be converted to ToolResult.content"
                )
            parts.append(_text_of(block, item_where))
        return "\n".join(parts)
    raise ConversionError(
        f"{where}.content must be text or a list of text blocks, got {type(content).__name__}"
    )


def _parse_tool_result(block: dict[str, Any], where: str) -> ToolResult:
    call_id = require_non_empty_str(block.get("tool_use_id"), f"{where}.tool_use_id")
    content = _tool_result_text(block.get("content"), where)
    is_error = require_bool(block.get("is_error"), f"{where}.is_error")
    return ToolResult(call_id=call_id, content=content, is_error=is_error)


def from_anthropic_response(response_dict: dict[str, Any]) -> ProviderResponse:
    """Reconstruct canonical ProviderResponse from an Anthropic completion response."""
    response = require_dict(response_dict, "Anthropic response")
    raw_content = response.get("content")
    if raw_content is None:
        raise ConversionError("Anthropic response missing 'content'.")

    text_parts: list[str] = []
    canonical_tool_calls: list[ToolCall] = []

    if isinstance(raw_content, str):
        text_parts.append(raw_content)
    elif isinstance(raw_content, list):
        for index, item in enumerate(raw_content):
            where = f"Anthropic content[{index}]"
            block = require_dict(item, where)
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(_text_of(block, where))
            elif block_type == "tool_use":
                canonical_tool_calls.append(_parse_tool_use(block, where))
            else:
                # Disallow unknown block types silently disappearing
                raise ConversionError(f"Unsupported Anthropic block type: {block_type}")
    else:
        raise ConversionError(f"Unexpected Anthropic content type: {type(raw_content)}")

    usage = parse_usage(response.get("usage"), "input_tokens", "output_tokens", "Anthropic")

    return ProviderResponse(
        content="\n".join(text_parts),
        tool_calls=canonical_tool_calls,
        usage=usage,
    )


def _system_messages(system: object) -> list[Message]:
    """Convert the top-level ``system`` parameter into one SYSTEM message per block."""
    if system is None:
        return []
    if isinstance(system, str):
        # An empty system string carries no instruction, so nothing is lost by omitting it.
        return [Message(role=Role.SYSTEM, content=system)] if system else []
    if isinstance(system, list):
        messages: list[Message] = []
        for index, item in enumerate(system):
            where = f"Anthropic system[{index}]"
            block = require_dict(item, where)
            if block.get("type") != "text":
                raise ConversionError(
                    f"Unsupported Anthropic block type in {where}: {block.get('type')!r}"
                )
            text = _text_of(block, where)
            if not text:
                raise ConversionError(f"{where} is empty and cannot be reconstructed")
            messages.append(Message(role=Role.SYSTEM, content=text))
        return messages
    raise ConversionError(
        f"Anthropic 'system' must be a string or a list of text blocks, got {type(system).__name__}"
    )


def _convert_block_message(role: str, blocks: list[Any], where: str) -> list[Message]:
    """Convert one message whose content is a list of blocks."""
    if not blocks:
        raise ConversionError(f"{where} has an empty content list")

    parsed: list[tuple[str, dict[str, Any], str]] = []
    for index, item in enumerate(blocks):
        block_where = f"{where}.content[{index}]"
        block = require_dict(item, block_where)
        parsed.append((_block_type(block, block_where), block, block_where))

    kinds = {kind for kind, _, _ in parsed}

    if "tool_result" in kinds:
        if kinds != {"tool_result"}:
            raise ConversionError(
                f"{where} mixes tool_result blocks with other blocks "
                f"({sorted(kinds - {'tool_result'})}); the canonical model cannot keep that "
                "grouping without local correlation metadata"
            )
        if role != "user":
            raise ConversionError(f"{where}: tool_result blocks are only valid in user messages")
        results = [_parse_tool_result(block, block_where) for _, block, block_where in parsed]
        return [Message(role=Role.TOOL, content=r.content, tool_result=r) for r in results]

    if "tool_use" in kinds:
        if role != "assistant":
            raise ConversionError(f"{where}: tool_use blocks are only valid in assistant messages")
        seen_tool_use = False
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for kind, block, block_where in parsed:
            if kind == "tool_use":
                seen_tool_use = True
                tool_calls.append(_parse_tool_use(block, block_where))
            else:
                if seen_tool_use:
                    raise ConversionError(
                        f"{block_where}: text after a tool_use block cannot be represented in "
                        "canonical order (text precedes tool calls)"
                    )
                text_parts.append(_text_of(block, block_where))
        return [
            Message(
                role=Role.ASSISTANT,
                content="\n".join(text_parts),
                tool_calls=tuple(tool_calls),
            )
        ]

    text = "\n".join(_text_of(block, block_where) for _, block, block_where in parsed)
    return [Message(role=Role(role), content=text)]


def from_anthropic_payload(payload: dict[str, Any]) -> list[Message]:
    """Reconstruct canonical Message list from an Anthropic request payload.

    Deprecated (D-02, T024): use ``to_anthropic_envelope`` and ``restore_messages``.
    """
    warnings.warn(
        "from_anthropic_payload() interprets a bare payload and cannot recover is_external, "
        "is_error, "
        "usage or a differing TOOL content (it defaults to trusted); use "
        "to_anthropic_envelope() and restore_messages(envelope)"
        " instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    request = require_dict(payload, "Anthropic payload")
    canonical = _system_messages(request.get("system"))

    raw_msgs = request.get("messages")
    if raw_msgs is None:
        return canonical
    for index, item in enumerate(require_list(raw_msgs, "Anthropic messages")):
        where = f"Anthropic messages[{index}]"
        raw = require_dict(item, where)

        role = raw.get("role")
        if role not in ("user", "assistant"):
            raise ConversionError(f"{where} has unsupported role {role!r}")

        raw_content = raw.get("content")
        if isinstance(raw_content, str):
            canonical.append(Message(role=Role(role), content=raw_content))
        elif isinstance(raw_content, list):
            canonical.extend(_convert_block_message(role, raw_content, where))
        else:
            raise ConversionError(
                f"{where}.content must be text or a list of blocks, "
                f"got {type(raw_content).__name__}"
            )

    validate_canonical_messages(canonical)
    return canonical


def _restore_anthropic_entry(entry: MessageMeta, elements: list[Any], where: str) -> Message:
    if entry.role != Role.TOOL and (
        entry.tool_call_id is not None
        or entry.tool_is_error is not None
        or entry.tool_message_content is not None
    ):
        raise ConversionError(f"{where}: tool metadata on a non-TOOL entry")

    if entry.omitted:
        omitted = Message(role=Role.SYSTEM, content="")
        return dataclasses.replace(omitted, is_external=entry.is_external, usage=entry.usage)
    if len(entry.refs) != 1:
        raise ConversionError(f"{where}: expected exactly one payload reference")
    ref = entry.refs[0]
    element = elements[0]

    if entry.role == Role.SYSTEM:
        if ref.kind == "system":
            text = require_text(element, f"{where} system")
        elif ref.kind == "system_block":
            block = require_dict(element, where)
            if block.get("type") != "text":
                raise ConversionError(f"{where} is not a text block")
            text = _text_of(block, where)
        else:
            raise ConversionError(f"{where}: SYSTEM entries map to the 'system' parameter")
        if not text:
            raise ConversionError(f"{where} is empty and cannot be a system block")
        message = Message(role=Role.SYSTEM, content=text)
    elif ref.kind not in ("message", "message_block"):
        raise ConversionError(f"{where}: {entry.role.value} entries map to messages")
    elif entry.role == Role.TOOL:
        if ref.kind == "message":
            raw = require_dict(element, where)
            if raw.get("role") != "user":
                raise ConversionError(f"{where}: a TOOL message is carried by a 'user' message")
            blocks = raw.get("content")
            if not isinstance(blocks, list) or len(blocks) != 1:
                raise ConversionError(f"{where}: expected exactly one tool_result block")
            block = require_dict(blocks[0], f"{where}.content[0]")
        else:
            block = require_dict(element, where)
        if block.get("type") != "tool_result":
            raise ConversionError(f"{where}: TOOL entries require a tool_result block")
        result = _parse_tool_result(block, where)
        if result.call_id != entry.tool_call_id:
            raise ConversionError(
                f"{where}: tool_use_id {result.call_id!r} does not match the sidecar "
                f"{entry.tool_call_id!r}"
            )
        if not isinstance(entry.tool_is_error, bool) or result.is_error != entry.tool_is_error:
            raise ConversionError(f"{where}: is_error differs from the sidecar")
        message = Message(
            role=Role.TOOL,
            content=entry.tool_message_content
            if entry.tool_message_content is not None
            else result.content,
            tool_result=result,
        )
    else:
        raw = require_dict(element, where)
        if raw.get("role") != entry.role.value:
            raise ConversionError(
                f"{where} has role {raw.get('role')!r}, incompatible with canonical "
                f"{entry.role.value!r}"
            )
        content = raw.get("content")
        if isinstance(content, str):
            message = Message(role=entry.role, content=content)
        elif isinstance(content, list):
            converted = _convert_block_message(entry.role.value, content, where)
            if len(converted) != 1 or converted[0].role != entry.role:
                raise ConversionError(
                    f"{where} does not map to exactly one canonical {entry.role.value} message"
                )
            message = converted[0]
        else:
            raise ConversionError(f"{where}.content must be text or a list of blocks")
    # is_external and usage come ONLY from the sidecar; payload fields cannot set them.
    return dataclasses.replace(message, is_external=entry.is_external, usage=entry.usage)


def restore_anthropic_messages(envelope: ConversionEnvelope) -> list[Message]:
    """Restore canonical messages (with local metadata) from an Anthropic envelope."""
    payload = verify_structure(envelope, "anthropic")
    restored: list[Message] = []
    for entry in envelope.entries:
        elements = [resolve_ref(payload, ref) for ref in entry.refs]
        restored.append(_restore_anthropic_entry(entry, elements, f"Anthropic entry {entry.index}"))
    validate_canonical_messages(restored)
    validate_tool_correlation(restored, partial_window=envelope.partial_window)
    return restored


class AnthropicConverter:
    """Composite converter implementing ProviderMessageConverter for Anthropic."""

    def to_provider_envelope(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        *,
        partial_window: bool = False,
    ) -> ConversionEnvelope:
        return to_anthropic_envelope(messages, tools, partial_window=partial_window)

    def to_provider_payload(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> dict[str, Any]:
        return to_anthropic_payload(messages, tools)

    def to_canonical_response(
        self,
        raw_response: dict[str, Any],
    ) -> ProviderResponse:
        return from_anthropic_response(raw_response)
