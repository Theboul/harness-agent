"""Permission policy of HARNESS: rules and the default policy (HU-05-01), protection (HU-11-01).

Only the standard library and ``harness_agent.core`` are used here; the configuration is read
outside the core and arrives as an immutable ``PermissionRules``.
"""

from harness_agent.core.permissions.policy import DefaultPermissionPolicy
from harness_agent.core.permissions.protected import ProtectedPolicy
from harness_agent.core.permissions.rules import PermissionRules

__all__ = ["DefaultPermissionPolicy", "PermissionRules", "ProtectedPolicy"]
