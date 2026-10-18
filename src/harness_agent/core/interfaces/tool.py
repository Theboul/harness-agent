"""Abstract Tool and ToolRegistry interfaces for HARNESS.

Unified contract for all execution tools (file operations, shell commands,
MCP tools, and subagents).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from harness_agent.core.entities import ToolResult


class RiskLevel(str, Enum):
    """Execution risk level used by permission policies.

    LOW: Read-only or idempotent operations (e.g. read_file, list_dir).
    MEDIUM: Modifying operations constrained to the workspace (e.g. write_file).
    HIGH: Arbitrary code or OS execution, external network calls (e.g. shell).
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Tool(ABC):
    """Abstract Base Class for all tools available to the agent.

    Subclasses define functional metadata and execute actions via run().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the tool (e.g. 'shell', 'read_file')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human- and LLM-readable description of tool purpose and usage."""
        ...

    @property
    @abstractmethod
    def schema(self) -> dict[str, Any]:
        """JSON Schema defining and validating the arguments accepted by this tool."""
        ...

    @property
    @abstractmethod
    def risk(self) -> RiskLevel:
        """Risk classification evaluated by the permission policy."""
        ...

    @abstractmethod
    async def run(self, args: dict[str, Any]) -> ToolResult:
        """Execute the tool asynchronously with validated arguments.

        Args:
            args: Dictionary of arguments conforming to schema.

        Returns:
            ToolResult containing textual output, call_id, and error status.
        """
        ...


class ToolRegistry(ABC):
    """Abstract Base Class for the tool catalog and validation registry."""

    @abstractmethod
    def register(self, tool: Tool) -> None:
        """Register a new tool instance. Raises ValueError on name collision."""
        ...

    @abstractmethod
    def get(self, name: str) -> Tool | None:
        """Retrieve a registered tool by its unique name, or None if not found."""
        ...

    @abstractmethod
    def list(self) -> list[Tool]:
        """Return a list of all currently registered tools."""
        ...

    @abstractmethod
    def validate_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Validate arguments against tool schema. Raises ValueError if invalid."""
        ...
