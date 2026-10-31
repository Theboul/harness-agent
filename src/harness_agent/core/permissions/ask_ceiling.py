"""A ceiling of ``ASK`` for named tools (HU-08-03).

``AskCeilingPolicy`` wraps another ``PermissionPolicy`` and may change only one of its answers:
an ``ALLOW`` for a tool whose name is in ``names`` becomes ``ASK``. ``DENY`` and ``ASK`` are kept,
and so is every answer for any other tool. It can only make a decision stricter and never returns
``ALLOW`` on its own.

The module knows no tool: the composition root gives it the names (a live container, filled as the
tools of remote servers are registered). It keeps no state of its own and fails closed: an
exception, a malformed call or a value that is not a ``PermissionDecision`` is a denial.
"""

from __future__ import annotations

from collections.abc import Container

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy


class AskCeilingPolicy(PermissionPolicy):
    """Never let the wrapped policy allow a call to one of ``names`` without asking.

    Args:
        inner: The policy that decides first.
        names: Tool names that must be asked at the least. It is read on every call, so names
            added later count.
    """

    def __init__(self, inner: PermissionPolicy, names: Container[str]) -> None:
        if not isinstance(inner, PermissionPolicy):
            raise TypeError(
                f"La política envuelta debe ser un PermissionPolicy, no '{type(inner).__name__}'."
            )
        if not isinstance(names, Container) or isinstance(names, str):
            raise TypeError("Los nombres deben ser un contenedor de textos, no un texto suelto.")
        self._inner = inner
        self._names = names

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        """Keep the answer of ``inner`` unless it allows a capped tool: then ask."""
        try:
            if not isinstance(call, ToolCall):
                return PermissionDecision.DENY
            decision: object = self._inner.evaluate(call)
            if not isinstance(decision, PermissionDecision):
                return PermissionDecision.DENY
            if decision is PermissionDecision.ALLOW and call.name in self._names:
                return PermissionDecision.ASK
            return decision
        except Exception:
            return PermissionDecision.DENY
