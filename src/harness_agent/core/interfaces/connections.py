"""External connection and delegation interfaces for HARNESS.

Defines client interfaces for Model Context Protocol (MCP) servers (RF-8.1, RF-8.2)
and isolated subagent execution runners (RF-9.1, RF-9.4, V-06).
Firmas asíncronas son provisionales sujetas a SPK-02.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from harness_agent.core.entities import Message, ToolResult
from harness_agent.core.interfaces.tool import Tool


@dataclass(frozen=True)
class SubagentResult:
    """Outcome produced by an isolated subagent execution.

    Attributes:
        session_id: Identifier of the child session spawned for the subagent.
        output: Structured result payload conforming to the requested schema.
        is_error: True if the subagent failed, timed out, or crashed.
    """

    session_id: str
    output: dict[str, Any] = field(default_factory=dict)
    is_error: bool = False


class McpClient(ABC):
    """Abstract Base Class for Model Context Protocol (MCP) tool integrations.

    Connects to external MCP servers via stdio transport and exposes discovered tools.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish stdio connection with the configured MCP server process."""
        ...

    @abstractmethod
    async def list_tools(self) -> list[Tool]:
        """Discover tools exposed by the MCP server and adapt them to Tool instances."""
        ...

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a remote tool call on the MCP server and return structured output."""
        ...


class SubagentRunner(ABC):
    """Abstract Base Class for executing task delegation to specialized subagents."""

    @abstractmethod
    async def execute(
        self,
        profile: str,
        goal: str,
        context: list[Message],
        output_schema: dict[str, Any],
    ) -> SubagentResult:
        """Spawn a child session and execute a delegated subagent task.

        Args:
            profile: Name of the subagent persona/profile to invoke.
            goal: Specific target objective for the child agent.
            context: Filtered or focused message history relevant to the delegation.
            output_schema: JSON Schema that the subagent result must conform to.

        Returns:
            SubagentResult containing structured output and child session ID.
        """
        ...
