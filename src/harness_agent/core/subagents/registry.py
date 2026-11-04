"""The registry a subagent sees (HU-09-04): the orchestrator's one without the delegation.

Only one level of nesting is allowed. The subagent works with a *view* of the registry of the
orchestrator that hides the delegation tool: it is not offered to the model and, if it is called
anyway, the loop answers that the tool is not registered. The view is live, so a tool that the
orchestrator registers later (the ones of the MCP servers) reaches the subagent as well.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from harness_agent.core.interfaces.tool import Tool, ToolRegistry
from harness_agent.core.tools.errors import UnknownToolError

DELEGATE_TOOL_NAME = "delegar"


class RegistryView(ToolRegistry):
    """A read-only view of ``inner`` that leaves out the tools named in ``hidden``.

    Args:
        inner: The registry of the orchestrator.
        hidden: Names the view does not offer; copied, later changes to the argument are ignored.
    """

    def __init__(self, inner: ToolRegistry, hidden: Iterable[str]) -> None:
        self._inner = inner
        self._hidden = frozenset(hidden)

    def register(self, tool: Tool) -> None:
        """A view never registers: tools are registered in the registry of the orchestrator."""
        raise TypeError("La vista del registro de un subagente no admite registrar herramientas.")

    def get(self, name: str) -> Tool | None:
        """The tool called ``name`` unless it is hidden or unknown."""
        if not isinstance(name, str) or name in self._hidden:
            return None
        return self._inner.get(name)

    def list(self) -> list[Tool]:
        """The tools of the registry in its order, without the hidden ones."""
        return [tool for tool in self._inner.list() if tool.name not in self._hidden]

    def validate_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Validate as the registry does; a hidden or non-text name is an unknown tool."""
        if not isinstance(name, str) or name in self._hidden:
            raise UnknownToolError(str(name))
        return self._inner.validate_args(name, args)
