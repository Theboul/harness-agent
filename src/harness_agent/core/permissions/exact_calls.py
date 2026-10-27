"""Permission for exact, declared calls (HU-11-03).

``ExactCallPolicy`` wraps another ``PermissionPolicy`` and may change only one of its answers:
an ``ASK`` becomes ``ALLOW`` when the call is identical to one of the declared ``AllowedCall``
rules. Identical means: the same tool, only the declared arguments, the same text in the declared
argument (only outer spaces are ignored; case and inner spaces count) and a time limit that does
not exceed the declared one (without one, ``default_limit`` counts). A ``DENY`` of the wrapped
policy, or a tool in ``ask_names``, is never turned into ``ALLOW``: deny > ask > allow holds.

The rules are generic: this module knows no tool. The composition root builds them from the
commands of the task and the names of the tool that runs them. Commands are not interpreted:
a chained or altered command is simply not identical (the analysis of commands is HU-05-02).

It fails closed: an exception or a value that is not a ``PermissionDecision`` is a denial.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy


def _is_name(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_positive_number(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


@dataclass(frozen=True)
class AllowedCall:
    """One call that may run without asking.

    Attributes:
        tool: Name of the tool.
        argument: Argument that must hold exactly ``value``.
        value: The exact text, kept without outer spaces.
        limit_argument: Argument with the time limit of the call.
        limit: Largest time limit allowed.
        default_limit: Time limit the tool applies when the call has none.
    """

    tool: str
    argument: str
    value: str
    limit_argument: str
    limit: int | float
    default_limit: int | float

    def __post_init__(self) -> None:
        if not all(_is_name(name) for name in (self.tool, self.argument, self.limit_argument)):
            raise ValueError("La herramienta y los argumentos de la regla deben ser nombres.")
        if self.limit_argument == self.argument:
            raise ValueError("El argumento del tiempo debe ser distinto del argumento del texto.")
        if not _is_name(self.value):
            raise ValueError("El texto permitido no puede estar vacío.")
        if not _is_positive_number(self.limit) or not _is_positive_number(self.default_limit):
            raise ValueError("Los tiempos de la regla deben ser números finitos mayores que 0.")
        object.__setattr__(self, "value", self.value.strip())

    def matches(self, call: ToolCall) -> bool:
        """Whether ``call`` is exactly this one, within its time limit."""
        if not isinstance(call, ToolCall) or call.name != self.tool:
            return False
        arguments = call.arguments
        if not isinstance(arguments, dict):
            return False
        if not set(arguments.keys()) <= {self.argument, self.limit_argument}:
            return False
        text = arguments.get(self.argument)
        if not isinstance(text, str) or text.strip() != self.value:
            return False
        seconds = arguments.get(self.limit_argument, self.default_limit)
        return _is_positive_number(seconds) and seconds <= self.limit


class ExactCallPolicy(PermissionPolicy):
    """Turn the ``ASK`` of ``inner`` into ``ALLOW`` for the declared calls only.

    Args:
        inner: The policy that decides first; its ``DENY`` and ``ALLOW`` are kept.
        allowed: The calls that may run without asking.
        ask_names: Tools that must always be asked (the ``ask`` list of the configuration).
    """

    def __init__(
        self,
        inner: PermissionPolicy,
        allowed: Sequence[AllowedCall],
        *,
        ask_names: Sequence[str] = (),
    ) -> None:
        if not isinstance(inner, PermissionPolicy):
            raise TypeError(
                f"La política envuelta debe ser un PermissionPolicy, no '{type(inner).__name__}'."
            )
        if (
            isinstance(allowed, str)
            or not isinstance(allowed, Sequence)
            or not all(isinstance(rule, AllowedCall) for rule in allowed)
        ):
            raise TypeError("Las llamadas permitidas deben ser una secuencia de AllowedCall.")
        if (
            isinstance(ask_names, str)
            or not isinstance(ask_names, Sequence)
            or not all(_is_name(name) for name in ask_names)
        ):
            raise TypeError("Las herramientas que se preguntan deben ser una secuencia de nombres.")
        self._inner = inner
        self._allowed = tuple(allowed)
        self._ask_names = frozenset(ask_names)

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        """Keep the answer of ``inner`` unless it asks about a declared, exact call."""
        try:
            decision: object = self._inner.evaluate(call)
            if not isinstance(decision, PermissionDecision):
                return PermissionDecision.DENY
            if decision is not PermissionDecision.ASK:
                return decision
            if call.name in self._ask_names:
                return PermissionDecision.ASK
            if self._matches(call) is True:
                return PermissionDecision.ALLOW
            return PermissionDecision.ASK
        except Exception:
            return PermissionDecision.DENY

    def _matches(self, call: ToolCall) -> bool:
        return any(rule.matches(call) for rule in self._allowed)
