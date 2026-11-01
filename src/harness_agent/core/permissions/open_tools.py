"""A short list of tools that are never asked (HU-06-02).

``OpenToolsPolicy`` wraps another ``PermissionPolicy`` and may change only one of its answers: an
``ASK`` for a tool whose name is in ``names`` becomes ``ALLOW``. ``DENY`` is kept, and so is every
answer for any other tool. A name that the configuration lists in ``ask_names`` is never opened.

It exists for a tool that executes nothing, such as the one that asks the person a question:
asking permission to ask would be absurd. The module knows no tool: the composition root gives it
the names. It keeps no state and fails closed: an exception, a malformed call or a value that is
not a ``PermissionDecision`` is a denial.
"""

from __future__ import annotations

from collections.abc import Container, Iterable

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy


class OpenToolsPolicy(PermissionPolicy):
    """Allow without asking the calls to ``names`` that the wrapped policy would ask.

    Args:
        inner: The policy that decides first (``DENY`` always prevails).
        names: Tool names that are opened.
        ask_names: Tools the user wants always asked; they are never opened.
    """

    def __init__(
        self, inner: PermissionPolicy, names: Container[str], *, ask_names: Iterable[str] = ()
    ) -> None:
        if not isinstance(inner, PermissionPolicy):
            raise TypeError(
                f"La política envuelta debe ser un PermissionPolicy, no '{type(inner).__name__}'."
            )
        if not isinstance(names, Container) or isinstance(names, str):
            raise TypeError("Los nombres deben ser un contenedor de textos, no un texto suelto.")
        if isinstance(ask_names, str):
            raise TypeError("La lista de preguntar debe ser un iterable de textos.")
        self._inner = inner
        self._names = names
        self._ask_names = frozenset(ask_names)

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        """Keep the answer of ``inner`` unless it asks an open tool: then allow."""
        try:
            if not isinstance(call, ToolCall):
                return PermissionDecision.DENY
            decision: object = self._inner.evaluate(call)
            if not isinstance(decision, PermissionDecision):
                return PermissionDecision.DENY
            if (
                decision is PermissionDecision.ASK
                and call.name in self._names
                and call.name not in self._ask_names
            ):
                return PermissionDecision.ALLOW
            return decision
        except Exception:
            return PermissionDecision.DENY
