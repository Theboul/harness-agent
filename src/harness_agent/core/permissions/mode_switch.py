"""Switch of the read-only mode while the session runs (HU-06-06).

``ReadOnlyPolicy`` (HU-05-07) is fixed when the system is composed. The ``/plan`` and
``/implementar`` commands need to turn the mode on and off, so the composition root hands this
module two policies, the restricted one (the read-only wrapper) and the open one (the plain chain),
and a ``ReadOnlySwitch`` that says which one answers.

``SwitchablePolicy`` never decides by itself: it forwards to one of the two policies it was given.
It fails closed: an exception or an answer that is not a ``PermissionDecision`` is a denial. A
switch created ``locked`` (the mode was fixed at the start by the command line or the
configuration) can never be turned off.
"""

from __future__ import annotations

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy


class ReadOnlySwitch:
    """Whether the read-only mode is on; a locked one cannot be turned off.

    Args:
        enabled: Starts on.
        locked: The mode was fixed at the start: it is on and stays on.
    """

    def __init__(self, *, enabled: bool = False, locked: bool = False) -> None:
        self._locked = locked
        self._enabled = enabled or locked

    @property
    def enabled(self) -> bool:
        """Whether the restricted policy answers."""
        return self._enabled

    @property
    def locked(self) -> bool:
        """Whether the mode was fixed at the start."""
        return self._locked

    def enable(self) -> None:
        """Turn the mode on."""
        self._enabled = True

    def disable(self) -> bool:
        """Turn the mode off; returns ``False`` (and leaves it on) when it is locked."""
        if self._locked:
            return False
        self._enabled = False
        return True


class SwitchablePolicy(PermissionPolicy):
    """Ask ``restricted`` while the switch is on and ``unrestricted`` while it is off."""

    def __init__(
        self,
        restricted: PermissionPolicy,
        unrestricted: PermissionPolicy,
        switch: ReadOnlySwitch,
    ) -> None:
        if not isinstance(restricted, PermissionPolicy) or not isinstance(
            unrestricted, PermissionPolicy
        ):
            raise TypeError("Las dos políticas deben ser un PermissionPolicy.")
        if not isinstance(switch, ReadOnlySwitch):
            raise TypeError("El conmutador debe ser un ReadOnlySwitch.")
        self._restricted = restricted
        self._unrestricted = unrestricted
        self._switch = switch

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        """The answer of the policy the switch points to; a failure is a denial."""
        try:
            policy = self._restricted if self._switch.enabled else self._unrestricted
            decision: object = policy.evaluate(call)
        except Exception:
            return PermissionDecision.DENY
        return decision if isinstance(decision, PermissionDecision) else PermissionDecision.DENY
