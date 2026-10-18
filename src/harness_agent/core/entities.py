"""Canonical messaging entities for the HARNESS agent.

Defines immutable data structures representing roles, messages, tool calls,
tool execution results, and token consumption metrics, decoupled from specific
LLM provider SDKs (OpenAI, Anthropic, Gemini).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Standard conversational roles for messages in the context window.

    SYSTEM: System instructions, developer guidelines, and stable prefix.
    USER: End-user prompts and human input.
    ASSISTANT: Model responses, including conversational text and tool requests.
    TOOL: Outputs returned from tool execution.
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True)
class ToolCall:
    """Represents a model request to invoke an external tool.

    Attributes:
        id: Unique identifier for this call instance, assigned by provider.
        name: Function or tool name to be invoked (e.g. 'shell', 'leer_archivo').
        arguments: Validated dictionary of arguments to pass to the tool.
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Represents the outcome of a tool execution.

    Attributes:
        call_id: Identifier referencing the corresponding ToolCall.
        content: Formatted or trimmed textual output of the tool.
        is_error: True if the tool invocation encountered an error or failed.
    """

    call_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class TokenUsage:
    """Token consumption reported by the LLM provider API.

    Attributes:
        input_tokens: Number of prompt/context tokens consumed.
        output_tokens: Number of response/completion tokens generated.
    """

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed in the exchange."""
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class Message:
    """Atomic unit of communication within the agent context window.

    Attributes:
        role: Conversational role of the message emitter.
        content: Textual content of the message.
        tool_calls: Tuple of requested tool invocations (if role is ASSISTANT).
        tool_result: Associated tool result (if role is TOOL).
        usage: Token consumption breakdown if reported for this message.
        is_external: Flag marking untrusted data (file content, MCP, web) to prevent
            prompt injection.
    """

    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_result: ToolResult | None = None
    usage: TokenUsage | None = None
    is_external: bool = False

    def __post_init__(self) -> None:
        """Enforce immutability and normalize types."""
        if isinstance(self.role, str) and not isinstance(self.role, Role):
            object.__setattr__(self, "role", Role(self.role))
        if isinstance(self.tool_calls, list):
            object.__setattr__(self, "tool_calls", tuple(self.tool_calls))
