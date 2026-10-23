"""Permission policy of HARNESS (HU-05-01): rules and the default policy.

Only the standard library and ``harness_agent.core`` are used here; the configuration is read
outside the core and arrives as an immutable ``PermissionRules``.
"""

from harness_agent.core.permissions.policy import DefaultPermissionPolicy
from harness_agent.core.permissions.rules import PermissionRules

__all__ = ["DefaultPermissionPolicy", "PermissionRules"]
