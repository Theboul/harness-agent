"""Consolidated exports of all abstract interfaces and contracts for HARNESS.

Provides unified imports for core interfaces: Provider, Tool, ToolRegistry,
PermissionPolicy, Approver, SessionStore, MemoryStore, ContextManager,
McpClient, SubagentRunner, Shell, AuthorizedArea, TaskCriteria, and EventBus.
"""

from harness_agent.core.interfaces.connections import (
    McpClient,
    SubagentResult,
    SubagentRunner,
)
from harness_agent.core.interfaces.context import (
    CompactResult,
    ContextManager,
)
from harness_agent.core.interfaces.event_bus import (
    EventBus,
    EventHandler,
)
from harness_agent.core.interfaces.provider import (
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    ToolDefinition,
)
from harness_agent.core.interfaces.security import (
    ApprovalAction,
    ApprovalResult,
    Approver,
    PermissionDecision,
    PermissionPolicy,
)
from harness_agent.core.interfaces.storage import (
    MemoryItem,
    MemoryStore,
    SessionStore,
    SessionSummary,
)
from harness_agent.core.interfaces.system import (
    AuthorizedArea,
    Shell,
    ShellResult,
    TaskCriteria,
    TaskCriteriaItem,
)
from harness_agent.core.interfaces.tool import (
    RiskLevel,
    Tool,
    ToolRegistry,
)

__all__ = [
    # 1. Provider
    "Provider",
    "ProviderResponse",
    "ToolDefinition",
    "ProviderError",
    "QuotaExceeded",
    "ProviderTimeout",
    "ProviderUnavailable",
    # 2. Tool
    "Tool",
    "ToolRegistry",
    "RiskLevel",
    # 3. Security
    "PermissionPolicy",
    "Approver",
    "PermissionDecision",
    "ApprovalAction",
    "ApprovalResult",
    # 4. Storage & Context
    "SessionStore",
    "MemoryStore",
    "SessionSummary",
    "MemoryItem",
    "ContextManager",
    "CompactResult",
    # 5. Connections
    "McpClient",
    "SubagentRunner",
    "SubagentResult",
    # 6. System
    "Shell",
    "AuthorizedArea",
    "TaskCriteria",
    "ShellResult",
    "TaskCriteriaItem",
    # 7. Event Bus
    "EventBus",
    "EventHandler",
]
