"""Bidirectional wire-format converter for OpenAI Chat Completions API v1.

Provides conversion between HARNESS canonical models and OpenAI API schemas.
Enforces fail-closed error handling: any external payload that cannot be represented faithfully
raises ``ConversionError`` instead of being coerced or dropped.

Known limitation of the payload-only functions (audit defects D1/D2/D8/D9): the OpenAI wire
format has no field for ``Message.is_external``, ``ToolResult.is_error``, ``Message.usage`` or a
TOOL ``Message.content`` that differs from ``ToolResult.content``, so ``from_openai_messages``
cannot
restore them. ``to_openai_envelope`` + ``restore_messages`` (design D-02, ``sidecar.py``) keep them
in a local metadata sidecar and never write them into the payload.
"""

from __future__ import annotations

import dataclasses
import warnings
from typing import Any

from harness_agent.adapters.converters._validation import (
    ensure_json_serializable,
    ensure_strict_json_value,
    parse_tool_arguments,
    parse_usage,
    require_bool,
    require_dict,
    require_list,
    require_non_empty_str,
    require_text,
    validate_canonical_messages,
    validate_tool_correlation,
)
from harness_agent.adapters.converters.base import ConversionError
from harness_agent.adapters.converters.sidecar import (
    ConversionEnvelope,
    MessageMeta,
    WireRef,
    meta_for_message,
    verify_structure,
)
from harness_agent.core.entities import (
    Message,
    Role,
    ToolCall,
    ToolResult,
)
from harness_agent.core.interfaces.provider import ProviderResponse, ToolDefinition


def to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert canonical Message list to OpenAI chat completion message dicts.

    Preserves local security metadata (is_external) in memory without sending
    unsupported vendor fields to the network API.

    The canonical sequence is validated first: SYSTEM messages must form a contiguous prefix and
    ``tool_calls`` / ``tool_result`` must sit on ASSISTANT / TOOL messages (``ConversionError``
    otherwise), so nothing is dropped or reordered silently.
    """
    validate_canonical_messages(messages)
    openai_msgs: list[dict[str, Any]] = []

    for msg in messages:
        if msg.role == Role.SYSTEM:
            openai_msgs.append({"role": "system", "content": msg.content})
        elif msg.role == Role.USER:
            openai_msgs.append({"role": "user", "content": msg.content})
        elif msg.role == Role.ASSISTANT:
            assistant_entry: dict[str, Any] = {
                "role": "assistant",
                "content": msg.content if msg.content else None,
            }
            if msg.tool_calls:
                tool_calls_payload: list[dict[str, Any]] = []
                for tc in msg.tool_calls:
                    if not isinstance(tc.arguments, dict):
                        raise ConversionError(
                            f"ToolCall arguments must be dict, got {type(tc.arguments)}"
                        )
                    tool_calls_payload.append(
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": ensure_json_serializable(tc.arguments, tc.id, tc.name),
                            },
                        }
                    )
                assistant_entry["tool_calls"] = tool_calls_payload
            openai_msgs.append(assistant_entry)
        elif msg.role == Role.TOOL:
            if msg.tool_result is None:  # unreachable after validation; narrows the type
                raise ConversionError("Message with role TOOL must contain a non-null tool_result.")
            openai_msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_result.call_id,
                    "content": msg.tool_result.content,
                }
            )
        else:
            raise ConversionError(f"Unsupported canonical role: {msg.role}")

    return openai_msgs


def to_openai_tools(tools: list[ToolDefinition] | None) -> list[dict[str, Any]] | None:
    """Convert canonical ToolDefinitions to OpenAI tools payload."""
    if tools is None:
        return None
    if not tools:
        return []

    openai_tools: list[dict[str, Any]] = []
    for td in tools:
        if not isinstance(td.parameters, dict):
            raise ConversionError(
                f"ToolDefinition parameters must be dict, got {type(td.parameters)}"
            )
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": td.name,
                    "description": td.description,
                    "parameters": td.parameters,
                },
            }
        )
    return openai_tools


def _parse_tool_calls(raw_tool_calls: object, where: str) -> list[ToolCall]:
    """Validate and convert a raw OpenAI ``tool_calls`` list."""
    if raw_tool_calls is None:
        return []
    calls: list[ToolCall] = []
    for index, raw_tc in enumerate(require_list(raw_tool_calls, f"{where} tool_calls")):
        tc_where = f"{where} tool_calls[{index}]"
        tc = require_dict(raw_tc, tc_where)
        tc_id = require_non_empty_str(tc.get("id"), f"{tc_where}.id")
        func = require_dict(tc.get("function"), f"{tc_where}.function")
        name = require_non_empty_str(func.get("name"), f"{tc_where}.function.name")
        arguments = parse_tool_arguments(func.get("arguments", "{}"), tc_id, name)
        calls.append(ToolCall(id=tc_id, name=name, arguments=arguments))
    return calls


def from_openai_response(response_dict: dict[str, Any]) -> ProviderResponse:
    """Reconstruct canonical ProviderResponse from an OpenAI completion response."""
    response = require_dict(response_dict, "OpenAI response")
    choices = response.get("choices")
    if not choices or not isinstance(choices, list):
        raise ConversionError("OpenAI response payload missing 'choices' list.")

    first_choice = require_dict(choices[0], "OpenAI choices[0]")
    message_data = first_choice.get("message")
    if not isinstance(message_data, dict):
        raise ConversionError("OpenAI choice missing 'message' dict.")

    content = require_text(
        message_data.get("content"), "OpenAI message.content", none_as_empty=True
    )
    tool_calls = _parse_tool_calls(message_data.get("tool_calls"), "OpenAI message")
    usage = parse_usage(response.get("usage"), "prompt_tokens", "completion_tokens", "OpenAI")

    return ProviderResponse(content=content, tool_calls=tool_calls, usage=usage)


def from_openai_messages(raw_messages: list[dict[str, Any]]) -> list[Message]:
    """Reconstruct canonical Message list from OpenAI message dicts.

    Deprecated (D-02, T024): use ``to_openai_envelope`` and ``restore_messages``.
    """
    warnings.warn(
        "from_openai_messages() interprets a bare payload and cannot recover is_external, "
        "is_error, "
        "usage or a differing TOOL content (it defaults to trusted); use "
        "to_openai_envelope() and restore_messages(envelope)"
        " instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    canonical: list[Message] = []
    for index, item in enumerate(require_list(raw_messages, "OpenAI messages")):
        where = f"OpenAI messages[{index}]"
        raw = require_dict(item, where)

        role_value = raw.get("role")
        if not isinstance(role_value, str) or not role_value:
            raise ConversionError(f"{where} is missing a valid 'role': {role_value!r}")
        try:
            role = Role(role_value)
        except ValueError as exc:
            raise ConversionError(f"{where} has unsupported role {role_value!r}") from exc

        content = require_text(raw.get("content"), f"{where}.content", none_as_empty=True)
        tool_calls = _parse_tool_calls(raw.get("tool_calls"), where)

        tool_result: ToolResult | None = None
        if role == Role.TOOL:
            call_id = require_non_empty_str(raw.get("tool_call_id"), f"{where}.tool_call_id")
            is_error = require_bool(raw.get("is_error"), f"{where}.is_error")
            tool_result = ToolResult(call_id=call_id, content=content, is_error=is_error)

        canonical.append(
            Message(
                role=role,
                content=content,
                tool_calls=tuple(tool_calls),
                tool_result=tool_result,
            )
        )
    validate_canonical_messages(canonical)
    return canonical


def to_openai_envelope(
    messages: list[Message],
    tools: list[ToolDefinition] | None = None,
    *,
    partial_window: bool = False,
) -> ConversionEnvelope:
    """Convert to an OpenAI payload plus the local metadata needed to restore it exactly.

    The payload is identical to ``OpenAIConverter.to_provider_payload``; local attributes
    (``is_external``, ``is_error``, ``usage``, TOOL ``content``) live only in the envelope.
    """
    validate_canonical_messages(messages)
    validate_tool_correlation(messages, partial_window=partial_window)
    for msg in messages:
        for call in msg.tool_calls:
            ensure_strict_json_value(call.arguments, f"Arguments of tool call {call.id!r}")
    wire_messages = to_openai_messages(messages)
    payload: dict[str, Any] = {"messages": wire_messages}
    tools_payload = to_openai_tools(tools)
    if tools_payload is not None:
        payload["tools"] = tools_payload
    entries = tuple(
        meta_for_message(
            index,
            msg,
            (WireRef(kind="message", message_index=index),),
            [wire_messages[index]],
        )
        for index, msg in enumerate(messages)
    )
    return ConversionEnvelope._create(
        provider="openai", payload=payload, entries=entries, partial_window=partial_window
    )


def _restore_openai_entry(entry: MessageMeta, element: object, where: str) -> Message:
    raw = require_dict(element, where)
    if raw.get("role") != entry.role.value:
        raise ConversionError(
            f"{where} has role {raw.get('role')!r}, incompatible with canonical "
            f"{entry.role.value!r}"
        )
    if entry.role != Role.TOOL and (
        entry.tool_call_id is not None
        or entry.tool_is_error is not None
        or entry.tool_message_content is not None
    ):
        raise ConversionError(f"{where}: tool metadata on a non-TOOL entry")

    if entry.role == Role.TOOL:
        call_id = require_non_empty_str(raw.get("tool_call_id"), f"{where}.tool_call_id")
        if call_id != entry.tool_call_id:
            raise ConversionError(
                f"{where}.tool_call_id {call_id!r} does not match the sidecar "
                f"{entry.tool_call_id!r}"
            )
        if not isinstance(entry.tool_is_error, bool):
            raise ConversionError(f"{where}: sidecar lacks the tool result error flag")
        content = require_text(raw.get("content"), f"{where}.content")
        message = Message(
            role=Role.TOOL,
            content=entry.tool_message_content
            if entry.tool_message_content is not None
            else content,
            tool_result=ToolResult(call_id=call_id, content=content, is_error=entry.tool_is_error),
        )
    elif entry.role == Role.ASSISTANT:
        content = require_text(raw.get("content"), f"{where}.content", none_as_empty=True)
        message = Message(
            role=Role.ASSISTANT,
            content=content,
            tool_calls=tuple(_parse_tool_calls(raw.get("tool_calls"), where)),
        )
    else:
        content = require_text(raw.get("content"), f"{where}.content")
        message = Message(role=entry.role, content=content)
    # is_external and usage come ONLY from the sidecar; payload fields cannot set them.
    return dataclasses.replace(message, is_external=entry.is_external, usage=entry.usage)


def restore_openai_messages(envelope: ConversionEnvelope) -> list[Message]:
    """Restore canonical messages (with local metadata) from an OpenAI envelope."""
    payload = verify_structure(envelope, "openai")
    raw_messages = payload["messages"]
    restored: list[Message] = []
    for entry in envelope.entries:
        if any(ref.kind != "message" for ref in entry.refs) or len(entry.refs) != 1:
            raise ConversionError(f"OpenAI entry {entry.index} must reference exactly one message")
        index = entry.refs[0].message_index
        if index is None:
            raise ConversionError(f"OpenAI entry {entry.index} lacks a message index")
        restored.append(
            _restore_openai_entry(entry, raw_messages[index], f"OpenAI messages[{index}]")
        )
    validate_canonical_messages(restored)
    validate_tool_correlation(restored, partial_window=envelope.partial_window)
    return restored


class OpenAIConverter:
    """Composite converter implementing ProviderMessageConverter for OpenAI."""

    def to_provider_envelope(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        *,
        partial_window: bool = False,
    ) -> ConversionEnvelope:
        return to_openai_envelope(messages, tools, partial_window=partial_window)

    def to_provider_payload(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messages": to_openai_messages(messages),
        }
        tools_payload = to_openai_tools(tools)
        if tools_payload is not None:
            payload["tools"] = tools_payload
        return payload

    def to_canonical_response(
        self,
        raw_response: dict[str, Any],
    ) -> ProviderResponse:
        return from_openai_response(raw_response)
