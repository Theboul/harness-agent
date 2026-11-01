"""Permission policy of HARNESS: rules and the default policy (HU-05-01), protection (HU-11-01),
exact declared calls (HU-11-03).

Only the standard library and ``harness_agent.core`` are used here; the configuration is read
outside the core and arrives as an immutable ``PermissionRules``.
"""

from harness_agent.core.permissions.approvals import (
    MAX_REASON_CHARS,
    MAX_REJECTION_CHARS,
    REJECTED_MARK,
    ApprovalGate,
    ApprovalOutcome,
    clean_reason,
    rejection_message,
)
from harness_agent.core.permissions.ask_ceiling import AskCeilingPolicy
from harness_agent.core.permissions.command_parser import (
    CommandPart,
    Dialect,
    ParsedCommand,
    parse_command,
)
from harness_agent.core.permissions.command_policy import CommandPolicy
from harness_agent.core.permissions.command_rules import (
    CompiledRule,
    DenyList,
    RuleError,
    RuleKind,
    compile_rule,
)
from harness_agent.core.permissions.exact_calls import AllowedCall, ExactCallPolicy
from harness_agent.core.permissions.git_reads import only_git_reads
from harness_agent.core.permissions.git_rules import (
    GitClass,
    GitPolicy,
    classify_git,
    git_instructions,
)
from harness_agent.core.permissions.open_tools import OpenToolsPolicy
from harness_agent.core.permissions.policy import DefaultPermissionPolicy
from harness_agent.core.permissions.protected import ProtectedPolicy
from harness_agent.core.permissions.read_only import ReadOnlyPolicy
from harness_agent.core.permissions.rules import PermissionRules

__all__ = [
    "AllowedCall",
    "AskCeilingPolicy",
    "ApprovalGate",
    "ApprovalOutcome",
    "MAX_REASON_CHARS",
    "MAX_REJECTION_CHARS",
    "REJECTED_MARK",
    "clean_reason",
    "rejection_message",
    "CommandPart",
    "CommandPolicy",
    "CompiledRule",
    "DenyList",
    "Dialect",
    "ParsedCommand",
    "RuleError",
    "RuleKind",
    "compile_rule",
    "parse_command",
    "DefaultPermissionPolicy",
    "ExactCallPolicy",
    "GitClass",
    "GitPolicy",
    "classify_git",
    "git_instructions",
    "only_git_reads",
    "OpenToolsPolicy",
    "PermissionRules",
    "ProtectedPolicy",
    "ReadOnlyPolicy",
]
