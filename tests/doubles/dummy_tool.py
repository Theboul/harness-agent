"""Test double: DummyTool implementing the Tool abstract contract."""

from __future__ import annotations

from typing import Any

from harness_agent.core.entities import ToolResult
from harness_agent.core.interfaces.tool import RiskLevel, Tool


class DummyTool(Tool):
    """In-memory test double for the Tool interface."""

    def __init__(
        self,
        name: str = "dummy_tool",
        description: str = "Dummy tool for contract verification",
        risk: RiskLevel = RiskLevel.LOW,
        canned_result: ToolResult | None = None,
        schema: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._description = description
        self._risk = risk
        self._canned_result = canned_result
        self._schema = schema
        self.recorded_executions: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def schema(self) -> dict[str, Any]:
        """Return the given schema object itself (uncopied), or a fresh default schema."""
        if self._schema is not None:
            return self._schema
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
                "call_id": {"type": "string"},
            },
        }

    @property
    def risk(self) -> RiskLevel:
        return self._risk

    async def run(self, args: dict[str, Any]) -> ToolResult:
        """Record execution arguments and return result."""
        self.recorded_executions.append(args)
        if self._canned_result is not None:
            return self._canned_result
        call_id = args.get("call_id", "call_dummy_default")
        return ToolResult(call_id=call_id, content=f"Executed {self._name} with args: {args}")
