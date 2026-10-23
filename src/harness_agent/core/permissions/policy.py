"""The default permission policy of HARNESS (HU-05-01).

``DefaultPermissionPolicy`` implements the ``PermissionPolicy`` port. Given a call it decides, in
this order: a call that is badly formed is denied; a tool in the ``deny`` list is denied; a tool in
the ``ask`` list is asked; a tool that is not registered, has no valid risk or has a high risk is
asked. There are two rules to allow, both bounded to the authorized area: a tool of medium risk
(a write) and a tool of low risk that carries a ``path`` (a read, an assumption pending the
confirmation of the PO that can be turned off). Every ALLOW goes through ``AuthorizedArea.contains``
with the ``path`` of the call; there is no allow without that condition. It fails closed: an error
while evaluating is a denial, and what no rule foresees is asked.

The policy only sees the call (name and arguments): it never reads messages, history, results or
the content of files, and it keeps no state between calls.
"""

from __future__ import annotations

from typing import Any

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy
from harness_agent.core.interfaces.system import AuthorizedArea
from harness_agent.core.interfaces.tool import RiskLevel, ToolRegistry

from .rules import PermissionRules


class DefaultPermissionPolicy(PermissionPolicy):
    """Deny, ask and allow rules with a fail-closed default (see the module documentation)."""

    def __init__(
        self,
        registry: ToolRegistry,
        area: AuthorizedArea | None = None,
        rules: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
        *,
        allow_reads_in_area: bool = True,
    ) -> None:
        if not isinstance(registry, ToolRegistry):
            raise TypeError(
                "El registro de herramientas debe ser un ToolRegistry, "
                f"no '{type(registry).__name__}'."
            )
        if area is not None and not isinstance(area, AuthorizedArea):
            raise TypeError(
                f"El área autorizada debe ser un AuthorizedArea o None, no '{type(area).__name__}'."
            )
        if not isinstance(rules, PermissionRules):
            raise TypeError(
                f"Las reglas deben ser un PermissionRules, no '{type(rules).__name__}'."
            )
        self._registry = registry
        self._area = area
        self._deny = frozenset(rules.deny)
        self._ask = frozenset(rules.ask)
        self._allow_reads = allow_reads_in_area

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        """Decide the call; an ordinary exception while evaluating is a denial (fail closed)."""
        try:
            return self._decide(call)
        except Exception:
            return PermissionDecision.DENY

    def _decide(self, call: ToolCall) -> PermissionDecision:
        if (
            not isinstance(call, ToolCall)
            or not isinstance(call.name, str)
            or not call.name
            or not isinstance(call.arguments, dict)
        ):
            return PermissionDecision.DENY
        name = call.name
        if name in self._deny:
            return PermissionDecision.DENY
        if name in self._ask:
            return PermissionDecision.ASK
        tool = self._registry.get(name)
        risk = None if tool is None else tool.risk
        if not isinstance(risk, RiskLevel) or risk is RiskLevel.HIGH:
            return PermissionDecision.ASK
        if risk is RiskLevel.MEDIUM:  # a write: allowed only inside the authorized area
            return self._inside_area(call.arguments)
        # Low risk: a read of a file (it carries ``path``) is allowed only inside the area too
        # (assumption pending the confirmation of the PO); anything else was not foreseen.
        if self._allow_reads and "path" in call.arguments:
            return self._inside_area(call.arguments)
        return PermissionDecision.ASK

    def _inside_area(self, arguments: dict[str, Any]) -> PermissionDecision:
        """The two rules to allow (write and read), both bounded to the authorized area.

        Every path that returns ALLOW goes through ``AuthorizedArea.contains`` with the ``path``
        of the call, unmodified, and only when it answers exactly ``True``. A ``path`` that cannot
        be checked is denied; without an area, or outside it, the decision is to ask.
        """
        path = arguments.get("path")
        if not isinstance(path, str) or not path.strip() or "\x00" in path:
            return PermissionDecision.DENY
        if self._area is None:
            return PermissionDecision.ASK
        if self._area.contains(path) is True:
            return PermissionDecision.ALLOW
        return PermissionDecision.ASK
