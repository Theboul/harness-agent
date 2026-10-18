"""HARNESS Core package.

Domain entities, canonical message and event definitions, and abstract
contracts for the agent harness. Contains zero third-party dependencies.
"""

from harness_agent.core.entities import (
    Message,
    Role,
    TokenUsage,
    ToolCall,
    ToolResult,
)
from harness_agent.core.events import (
    Event,
    EventType,
)
from harness_agent.core.interfaces import (
    ApprovalAction,
    ApprovalResult,
    Approver,
    AuthorizedArea,
    CompactResult,
    ContextManager,
    EventBus,
    EventHandler,
    McpClient,
    MemoryItem,
    MemoryStore,
    PermissionDecision,
    PermissionPolicy,
    Provider,
    ProviderResponse,
    RiskLevel,
    SessionStore,
    SessionSummary,
    Shell,
    ShellResult,
    SubagentResult,
    SubagentRunner,
    TaskCriteria,
    TaskCriteriaItem,
    Tool,
    ToolDefinition,
    ToolRegistry,
)

__all__ = [
    # Canonical Entities
    "Role",
    "ToolCall",
    "ToolResult",
    "TokenUsage",
    "Message",
    # Events
    "EventType",
    "Event",
    # Abstract Interfaces & Supporting Types
    "Provider",
    "ProviderResponse",
    "ToolDefinition",
    "Tool",
    "ToolRegistry",
    "RiskLevel",
    "PermissionPolicy",
    "Approver",
    "PermissionDecision",
    "ApprovalAction",
    "ApprovalResult",
    "SessionStore",
    "MemoryStore",
    "SessionSummary",
    "MemoryItem",
    "ContextManager",
    "CompactResult",
    "McpClient",
    "SubagentRunner",
    "SubagentResult",
    "Shell",
    "AuthorizedArea",
    "TaskCriteria",
    "ShellResult",
    "TaskCriteriaItem",
    "EventBus",
    "EventHandler",
]
