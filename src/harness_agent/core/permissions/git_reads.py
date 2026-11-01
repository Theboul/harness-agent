"""Whether a shell command is nothing but git reads (HU-05-07).

``only_git_reads`` is the classifier that the composition root hands to ``ReadOnlyPolicy`` for the
command tool. It does not add a table: it asks ``GitPolicy`` (HU-11-02), which allows a command only
when every part is a git read from its table and the whole command was understood.
"""

from __future__ import annotations

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy
from harness_agent.core.permissions.command_parser import Dialect
from harness_agent.core.permissions.git_rules import GitPolicy

_PLACEHOLDER = "-"


class _NeverAllows(PermissionPolicy):
    """The policy inside the judge: whatever ``GitPolicy`` does not decide itself is denied."""

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        return PermissionDecision.DENY


def only_git_reads(command: str, dialect: Dialect) -> bool:
    """Whether ``command`` is nothing but git reads, all of it understood.

    A command with any other program, any write, any text that runs, a redirection or a ``GIT_*``
    assignment is not a read. It fails closed: ``GitPolicy`` allows only a pure read, and what it
    cannot analyse asks or goes to the denying policy inside, so the answer is ``False``.
    """
    judge = GitPolicy(_NeverAllows(), dialect=dialect, tool=_PLACEHOLDER, argument=_PLACEHOLDER)
    call = ToolCall(id=_PLACEHOLDER, name=_PLACEHOLDER, arguments={_PLACEHOLDER: command})
    return judge.evaluate(call) is PermissionDecision.ALLOW
