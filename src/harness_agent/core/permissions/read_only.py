"""Read-only mode: deny everything that is not a read (HU-05-07).

``ReadOnlyPolicy`` wraps another ``PermissionPolicy`` and can only make its answers stricter. A call
is passed to the wrapped policy only if its tool is one of the ``read_tools`` it was given, or if it
is a call to the command tool and the injected classifier says, with an exact ``True``, that the
command is a read. Everything else is denied: writes, tools nobody told it about (MCP tools
included), commands that are not reads and commands it cannot classify.

The module knows no tool and no shell: the composition root gives it the names and the classifier
(for git, ``only_git_reads``). It keeps no state and fails closed: an exception, a malformed call or
a value that is not a ``PermissionDecision`` is a denial. It never returns ``ALLOW`` by itself, so
the mode only restricts; the answer for a read still comes from the policy inside.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy


def _is_name(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


class ReadOnlyPolicy(PermissionPolicy):
    """Deny every call that is not a known read; let ``inner`` decide the reads.

    Args:
        inner: The policy that decides the reads (its ``DENY`` and ``ASK`` are kept).
        read_tools: Names of the tools that only read.
        command_tool: Name of the tool whose argument is a command, if there is one.
        command_argument: Name of the argument that holds the command.
        is_read_command: Says whether a command only reads; only an exact ``True`` counts.
    """

    def __init__(
        self,
        inner: PermissionPolicy,
        read_tools: Iterable[str],
        *,
        command_tool: str | None = None,
        command_argument: str | None = None,
        is_read_command: Callable[[str], bool] | None = None,
    ) -> None:
        if not isinstance(inner, PermissionPolicy):
            raise TypeError(
                f"La política envuelta debe ser un PermissionPolicy, no '{type(inner).__name__}'."
            )
        if isinstance(read_tools, str) or not all(_is_name(name) for name in read_tools):
            raise TypeError("Las herramientas de lectura deben ser una secuencia de nombres.")
        if (command_tool is None) != (command_argument is None):
            raise TypeError("La herramienta de comandos y su argumento van juntos.")
        if command_tool is not None and not (_is_name(command_tool) and _is_name(command_argument)):
            raise TypeError("La herramienta de comandos y su argumento deben ser nombres.")
        if is_read_command is not None and not callable(is_read_command):
            raise TypeError("El clasificador de comandos debe ser invocable.")
        self._inner = inner
        self._read_tools = frozenset(read_tools)
        self._command_tool = command_tool
        self._command_argument = command_argument
        self._is_read_command = is_read_command

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        """Deny unless the call is a known read; then the wrapped policy decides."""
        try:
            if not isinstance(call, ToolCall) or not isinstance(call.arguments, dict):
                return PermissionDecision.DENY
            if call.name in self._read_tools or self._is_read(call):
                decision: object = self._inner.evaluate(call)
                if isinstance(decision, PermissionDecision):
                    return decision
            return PermissionDecision.DENY
        except Exception:
            return PermissionDecision.DENY

    def _is_read(self, call: ToolCall) -> bool:
        """Whether the call is a command that the classifier says only reads."""
        if call.name != self._command_tool or self._is_read_command is None:
            return False
        command = call.arguments.get(self._command_argument or "")
        return isinstance(command, str) and self._is_read_command(command) is True
