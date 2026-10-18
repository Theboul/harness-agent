"""Comprehensive test suite for provider wire-format converters (AC-01 / Sp1-40 / Sp1-42).

Validates lossless bidirectional conversion (round-trip) between HARNESS canonical
models and standard vendor schemas (OpenAI Chat Completions v1 and Anthropic Messages v1).
Asserts against independent schema expectations and validates fail-closed error handling.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from harness_agent.adapters.converters import (
    AnthropicConverter,
    ConversionError,
    OpenAIConverter,
    from_anthropic_payload,
    from_anthropic_response,
    from_openai_messages,
    from_openai_response,
    to_anthropic_payload,
    to_openai_messages,
    to_openai_tools,
)
from harness_agent.core.entities import (
    Message,
    Role,
    ToolCall,
    ToolResult,
)
from harness_agent.core.interfaces.provider import ToolDefinition

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

# ============================================================================
# Scenario 1 & 2: All Roles, Multi-Turn and External Data Flag
# ============================================================================


def test_openai_conversion_all_roles_and_multi_turn() -> None:
    """Validate all four roles in a multi-turn conversation for OpenAI format."""
    canonical_messages = [
        Message(role=Role.SYSTEM, content="You are a helpful assistant."),
        Message(role=Role.USER, content="Please list files in repo.", is_external=True),
        Message(
            role=Role.ASSISTANT,
            content="I will execute the shell tool.",
            tool_calls=(ToolCall(id="call_001", name="shell", arguments={"cmd": "ls -la"}),),
        ),
        Message(
            role=Role.TOOL,
            content="file1.py\nfile2.py",
            tool_result=ToolResult(
                call_id="call_001", content="file1.py\nfile2.py", is_error=False
            ),
        ),
    ]

    # Convert to OpenAI wire format
    wire_msgs = to_openai_messages(canonical_messages)

    # Independent assertions on OpenAI wire format structure
    assert len(wire_msgs) == 4
    assert wire_msgs[0] == {"role": "system", "content": "You are a helpful assistant."}
    assert wire_msgs[1] == {"role": "user", "content": "Please list files in repo."}
    assert "is_external" not in wire_msgs[1]  # Must NOT leak local metadata to wire
    assert wire_msgs[2]["role"] == "assistant"
    assert wire_msgs[2]["content"] == "I will execute the shell tool."
    assert len(wire_msgs[2]["tool_calls"]) == 1
    assert wire_msgs[2]["tool_calls"][0]["id"] == "call_001"
    assert wire_msgs[2]["tool_calls"][0]["type"] == "function"
    assert wire_msgs[2]["tool_calls"][0]["function"]["name"] == "shell"
    assert json.loads(wire_msgs[2]["tool_calls"][0]["function"]["arguments"]) == {"cmd": "ls -la"}
    assert wire_msgs[3] == {
        "role": "tool",
        "tool_call_id": "call_001",
        "content": "file1.py\nfile2.py",
    }

    # Reconstruct from wire format back to canonical
    reconstructed = from_openai_messages(wire_msgs)
    assert len(reconstructed) == len(canonical_messages)
    assert reconstructed[0] == canonical_messages[0]
    assert reconstructed[1].role == Role.USER
    assert reconstructed[1].content == canonical_messages[1].content
    assert reconstructed[2].role == Role.ASSISTANT
    assert reconstructed[2].tool_calls == canonical_messages[2].tool_calls
    assert reconstructed[3].role == Role.TOOL
    assert reconstructed[3].tool_result == canonical_messages[3].tool_result


def test_anthropic_conversion_all_roles_and_system_extraction() -> None:
    """Validate system prompt extraction and multi-turn message handling for Anthropic."""
    canonical_messages = [
        Message(role=Role.SYSTEM, content="Primary system instructions."),
        Message(role=Role.USER, content="Analyze test coverage."),
        Message(
            role=Role.ASSISTANT,
            content="Running pytest.",
            tool_calls=(ToolCall(id="toolu_abc", name="shell", arguments={"cmd": "pytest"}),),
        ),
        Message(
            role=Role.TOOL,
            content="10 passed",
            tool_result=ToolResult(call_id="toolu_abc", content="10 passed", is_error=False),
        ),
    ]

    payload = to_anthropic_payload(canonical_messages)

    # Independent assertions on Anthropic wire schema
    assert payload["system"] == "Primary system instructions."
    assert len(payload["messages"]) == 3  # system is extracted out of messages
    assert payload["messages"][0] == {"role": "user", "content": "Analyze test coverage."}

    assistant_msg = payload["messages"][1]
    assert assistant_msg["role"] == "assistant"
    assert len(assistant_msg["content"]) == 2
    assert assistant_msg["content"][0] == {"type": "text", "text": "Running pytest."}
    assert assistant_msg["content"][1] == {
        "type": "tool_use",
        "id": "toolu_abc",
        "name": "shell",
        "input": {"cmd": "pytest"},
    }

    tool_msg = payload["messages"][2]
    assert tool_msg["role"] == "user"  # Anthropic tool results are user-turn blocks
    assert len(tool_msg["content"]) == 1
    assert tool_msg["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "toolu_abc",
        "content": "10 passed",
        "is_error": False,
    }

    # Reconstruct from Anthropic payload
    reconstructed = from_anthropic_payload(payload)
    assert len(reconstructed) == len(canonical_messages)
    assert reconstructed[0].role == Role.SYSTEM
    assert reconstructed[0].content == "Primary system instructions."
    assert reconstructed[1] == canonical_messages[1]
    assert reconstructed[2].tool_calls == canonical_messages[2].tool_calls
    assert reconstructed[3].tool_result == canonical_messages[3].tool_result


# ============================================================================
# Scenario 3: Empty Message Content with Tool Calls
# ============================================================================


def test_empty_content_with_tool_calls_openai() -> None:
    """Validate assistant messages that have no content string but carry tool calls."""
    canonical_messages = [
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=(ToolCall(id="call_empty", name="ping", arguments={}),),
        )
    ]

    wire = to_openai_messages(canonical_messages)
    assert wire[0]["role"] == "assistant"
    assert wire[0]["content"] is None
    assert len(wire[0]["tool_calls"]) == 1

    reconstructed = from_openai_messages(wire)
    assert reconstructed[0].content == ""
    assert len(reconstructed[0].tool_calls) == 1
    assert reconstructed[0].tool_calls[0].name == "ping"


def test_empty_content_with_tool_calls_anthropic() -> None:
    """Validate Anthropic payload omits empty text block when only tool_use is present."""
    canonical_messages = [
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=(ToolCall(id="toolu_empty", name="ping", arguments={}),),
        )
    ]

    payload = to_anthropic_payload(canonical_messages)
    content_blocks = payload["messages"][0]["content"]
    assert len(content_blocks) == 1
    assert content_blocks[0]["type"] == "tool_use"

    reconstructed = from_anthropic_payload(payload)
    assert reconstructed[0].content == ""
    assert len(reconstructed[0].tool_calls) == 1


# ============================================================================
# Scenario 4, 5 & 6: Parallel Tool Calls and Complex Nested JSON Arguments
# ============================================================================


def test_parallel_tool_calls_and_nested_json_arguments() -> None:
    """Validate multiple tool calls with deeply nested JSON arguments in both dialects."""
    complex_args_1 = {
        "query": "SELECT * FROM users WHERE active = true",
        "limits": {"page": 1, "size": 50},
        "flags": [True, False, None],
    }
    complex_args_2 = {
        "path": "src/module/service.py",
        "edits": [{"start": 10, "end": 20, "text": "return True"}],
    }

    msg = Message(
        role=Role.ASSISTANT,
        content="Executing multiple tools concurrently.",
        tool_calls=(
            ToolCall(id="call_p1", name="db_query", arguments=complex_args_1),
            ToolCall(id="call_p2", name="edit_file", arguments=complex_args_2),
        ),
    )

    # 1. OpenAI Round-trip
    openai_wire = to_openai_messages([msg])
    assert len(openai_wire[0]["tool_calls"]) == 2
    assert json.loads(openai_wire[0]["tool_calls"][0]["function"]["arguments"]) == complex_args_1
    assert json.loads(openai_wire[0]["tool_calls"][1]["function"]["arguments"]) == complex_args_2

    openai_recon = from_openai_messages(openai_wire)[0]
    assert len(openai_recon.tool_calls) == 2
    assert openai_recon.tool_calls[0].arguments == complex_args_1
    assert openai_recon.tool_calls[1].arguments == complex_args_2

    # 2. Anthropic Round-trip
    anthropic_payload = to_anthropic_payload([msg])
    anthropic_blocks = anthropic_payload["messages"][0]["content"]
    assert len(anthropic_blocks) == 3  # 1 text + 2 tool_use
    assert anthropic_blocks[1]["input"] == complex_args_1
    assert anthropic_blocks[2]["input"] == complex_args_2

    anthropic_recon = from_anthropic_payload(anthropic_payload)[0]
    assert len(anthropic_recon.tool_calls) == 2
    assert anthropic_recon.tool_calls[0].arguments == complex_args_1
    assert anthropic_recon.tool_calls[1].arguments == complex_args_2


# ============================================================================
# Scenario 7 & 8: ToolResult Correlation and Execution Error Handling
# ============================================================================


def test_tool_result_correlation_and_error_flags() -> None:
    """Validate that error flags (is_error) and call IDs are preserved faithfully."""
    res_ok = Message(
        role=Role.TOOL,
        content="Execution successful.",
        tool_result=ToolResult(call_id="call_ok", content="Execution successful.", is_error=False),
    )
    res_err = Message(
        role=Role.TOOL,
        content="FileNotFoundError: path does not exist",
        tool_result=ToolResult(
            call_id="call_err", content="FileNotFoundError: path does not exist", is_error=True
        ),
    )

    # Anthropic preserves is_error natively in tool_result blocks
    payload = to_anthropic_payload([res_ok, res_err])
    user_blocks_1 = payload["messages"][0]["content"][0]
    user_blocks_2 = payload["messages"][1]["content"][0]

    assert user_blocks_1["tool_use_id"] == "call_ok"
    assert user_blocks_1["is_error"] is False
    assert user_blocks_2["tool_use_id"] == "call_err"
    assert user_blocks_2["is_error"] is True

    recon = from_anthropic_payload(payload)
    assert recon[0].tool_result is not None
    assert recon[0].tool_result.is_error is False
    assert recon[1].tool_result is not None
    assert recon[1].tool_result.is_error is True
    assert recon[1].tool_result.call_id == "call_err"


# ============================================================================
# Scenario 9: Token Usage Conversion and Total Tokens Computation
# ============================================================================


def test_token_usage_parsing_openai() -> None:
    """Validate OpenAI token usage normalization into canonical TokenUsage."""
    raw_response: dict[str, Any] = {
        "id": "chatcmpl-123",
        "choices": [{"message": {"role": "assistant", "content": "Done"}}],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 42,
            "total_tokens": 192,
        },
    }

    resp = from_openai_response(raw_response)
    assert resp.content == "Done"
    assert resp.usage is not None
    assert resp.usage.input_tokens == 150
    assert resp.usage.output_tokens == 42
    assert resp.usage.total_tokens == 192


def test_token_usage_parsing_anthropic() -> None:
    """Validate Anthropic token usage normalization into canonical TokenUsage."""
    raw_response: dict[str, Any] = {
        "id": "msg-456",
        "content": [{"type": "text", "text": "Anthropic response."}],
        "usage": {
            "input_tokens": 200,
            "output_tokens": 75,
        },
    }

    resp = from_anthropic_response(raw_response)
    assert resp.content == "Anthropic response."
    assert resp.usage is not None
    assert resp.usage.input_tokens == 200
    assert resp.usage.output_tokens == 75
    assert resp.usage.total_tokens == 275


# ============================================================================
# Scenario 10: Tool Definitions Schema Mapping
# ============================================================================


def test_tool_definition_mapping() -> None:
    """Validate ToolDefinition mapping to OpenAI functions and Anthropic input_schema."""
    tools = [
        ToolDefinition(
            name="read_file",
            description="Reads file contents.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        )
    ]

    # OpenAI format
    openai_tools = to_openai_tools(tools)
    assert openai_tools is not None
    assert len(openai_tools) == 1
    assert openai_tools[0]["type"] == "function"
    assert openai_tools[0]["function"]["name"] == "read_file"
    assert openai_tools[0]["function"]["description"] == "Reads file contents."
    assert openai_tools[0]["function"]["parameters"]["required"] == ["path"]

    # Anthropic format
    anthropic_payload = to_anthropic_payload([], tools)
    anthropic_tools = anthropic_payload.get("tools")
    assert anthropic_tools is not None
    assert len(anthropic_tools) == 1
    assert anthropic_tools[0]["name"] == "read_file"
    assert anthropic_tools[0]["description"] == "Reads file contents."
    assert anthropic_tools[0]["input_schema"]["required"] == ["path"]


# ============================================================================
# Scenario 11: Fail-Closed Negative Tests (No Silent Losses)
# ============================================================================


def test_fail_closed_on_malformed_json_openai_arguments() -> None:
    """Verify that malformed JSON in tool call arguments raises ConversionError."""
    malformed_response: dict[str, Any] = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {"name": "test", "arguments": "{bad_json: True"},
                        }
                    ],
                }
            }
        ]
    }
    with pytest.raises(ConversionError, match="Malformed JSON"):
        from_openai_response(malformed_response)


def test_fail_closed_on_tool_message_without_tool_result() -> None:
    """Verify that a TOOL message lacking a tool_result raises ConversionError."""
    orphan_tool_msg = Message(role=Role.TOOL, content="No result object attached")
    with pytest.raises(ConversionError, match="must contain a non-null tool_result"):
        to_openai_messages([orphan_tool_msg])

    with pytest.raises(ConversionError, match="must contain a non-null tool_result"):
        to_anthropic_payload([orphan_tool_msg])


def test_fail_closed_on_unsupported_anthropic_block_type() -> None:
    """Verify that unexpected block types in Anthropic response raise ConversionError."""
    bad_anthropic_response: dict[str, Any] = {
        "content": [{"type": "future_unsupported_type", "data": "unexpected"}]
    }
    with pytest.raises(ConversionError, match="Unsupported Anthropic block type"):
        from_anthropic_response(bad_anthropic_response)


# ============================================================================
# Protocol Interface Implementations
# ============================================================================


def test_composite_converters_satisfy_protocol() -> None:
    """Ensure OpenAIConverter and AnthropicConverter comply with ProviderMessageConverter."""
    openai_conv = OpenAIConverter()
    anthropic_conv = AnthropicConverter()

    msg = Message(role=Role.USER, content="Hello")
    tool = ToolDefinition(name="echo", description="echoes", parameters={"type": "object"})

    # OpenAI
    op_payload = openai_conv.to_provider_payload([msg], [tool])
    assert "messages" in op_payload
    assert "tools" in op_payload

    # Anthropic
    ant_payload = anthropic_conv.to_provider_payload([msg], [tool])
    assert "messages" in ant_payload
    assert "tools" in ant_payload
