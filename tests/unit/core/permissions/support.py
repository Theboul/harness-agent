"""Shared helpers for the permission policy tests (HU-05-01 / T002).

Nothing here imports ``harness_agent.core.permissions``: it only builds the collaborators that the
policy receives (tools of a given risk, a registry, an area whose answers the test controls and
tool calls). ``tests/doubles`` is not modified.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, cast

from harness_agent.core import AuthorizedArea, RiskLevel, Tool, ToolCall, ToolResult
from tests.doubles import InMemoryToolRegistry

SENTINEL = "VALOR-DE-PRUEBA-123"
_counter = itertools.count(1)


class RiskTool(Tool):
    """A tool with a configurable name and risk (the risk may be an invalid value on purpose)."""

    def __init__(self, name: str, risk: object = RiskLevel.LOW) -> None:
        self._name = name
        self._risk = risk
        self.executions: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Tool of test with a configurable risk"

    @property
    def schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"path": {"type": "string"}}}

    @property
    def risk(self) -> RiskLevel:
        return cast(RiskLevel, self._risk)

    async def run(self, args: dict[str, Any]) -> ToolResult:
        self.executions.append(args)
        return ToolResult(call_id="tool-chosen-id", content="ok")


def make_call(name: str, **arguments: Any) -> ToolCall:
    """A call with a unique identifier."""
    return ToolCall(id=f"call-{next(_counter)}", name=name, arguments=dict(arguments))


def make_registry(*tools: Tool) -> InMemoryToolRegistry:
    return InMemoryToolRegistry(list(tools))


class AreaStub(AuthorizedArea):
    """An authorized area whose answers the test controls and that records every question.

    By default ``contains`` is true for the paths in ``inside``; ``result`` replaces that answer
    with any function (it can raise or return something that is not a ``bool``).
    """

    def __init__(
        self,
        inside: Iterable[str] = (),
        *,
        result: Callable[[str | Path], object] | None = None,
    ) -> None:
        self._inside = set(inside)
        self._result = result
        self.calls: list[object] = []

    @property
    def root(self) -> Path:
        return Path("/area")

    def contains(self, path: Path | str) -> bool:
        self.calls.append(path)
        if self._result is not None:
            return cast(bool, self._result(path))
        return str(path) in self._inside
