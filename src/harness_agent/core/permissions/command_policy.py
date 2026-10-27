"""Policy that hardens the decisions about the shell with the deny list (HU-05-02).

``CommandPolicy`` wraps another ``PermissionPolicy`` and may only make its answer stricter:

* a call to the shell whose command contains a denied command (in any part, in a substitution, in
  the text of another interpreter or as a redirection target) is denied **before** the wrapped
  policy is asked, so no rule inside it (the exact commands of a task, HU-11-03) and no approval
  can let it run (V-02);
* a command that is not fully understood is never allowed: an ``ALLOW`` of the wrapped policy
  becomes ``ASK`` (V-17);
* anything else keeps the decision of the wrapped policy.

It knows no tool by name: the tool and its argument come by constructor. It fails closed: a
malformed call, an exception or a value that is not a decision of the wrapped policy is a denial,
and an exception while analyzing the command counts as "not understood".
"""

from __future__ import annotations

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy
from harness_agent.core.permissions.command_parser import parse_command
from harness_agent.core.permissions.command_rules import DenyList


def _is_name(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


class CommandPolicy(PermissionPolicy):
    """Deny the commands of the list and ask what is not understood; delegate the rest.

    Args:
        inner: The policy that decides every call this one does not harden.
        deny_list: The deny list in use (base of the platform plus the configuration).
        tool: Name of the tool whose argument is a command.
        argument: Name of the argument that holds the command.
    """

    def __init__(
        self,
        inner: PermissionPolicy,
        deny_list: DenyList,
        *,
        tool: str,
        argument: str,
    ) -> None:
        if not isinstance(inner, PermissionPolicy):
            raise TypeError(
                f"La política envuelta debe ser un PermissionPolicy, no '{type(inner).__name__}'."
            )
        if not isinstance(deny_list, DenyList):
            raise TypeError("La lista de comandos denegados debe ser un DenyList.")
        if not _is_name(tool) or not _is_name(argument):
            raise TypeError("La herramienta y su argumento deben ser nombres.")
        self._inner = inner
        self._deny_list = deny_list
        self._tool = tool
        self._argument = argument

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        """Deny a listed command; never allow one that is not understood; else delegate."""
        try:
            if (
                not isinstance(call, ToolCall)
                or not isinstance(call.name, str)
                or not isinstance(call.arguments, dict)
            ):
                return PermissionDecision.DENY
            understood = True
            if call.name == self._tool:
                verdict = self._analyze(call.arguments.get(self._argument))
                if verdict is None:
                    return PermissionDecision.DENY
                understood = verdict
            decision: object = self._inner.evaluate(call)
            if not isinstance(decision, PermissionDecision):
                return PermissionDecision.DENY
            if not understood and decision is PermissionDecision.ALLOW:
                return PermissionDecision.ASK
            return decision
        except Exception:
            return PermissionDecision.DENY

    def _analyze(self, command: object) -> bool | None:
        """``None`` if the command is denied; otherwise whether it was fully understood."""
        if not isinstance(command, str):
            return False
        deny_list = self._deny_list
        try:
            parsed = parse_command(
                command,
                deny_list.dialect,
                aliases=deny_list.aliases,
                synonyms=deny_list.synonyms,
            )
            if deny_list.denies(parsed, command):
                return None
        except Exception:
            return False
        return parsed.understood
