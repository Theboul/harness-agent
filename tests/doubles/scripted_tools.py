"""Test doubles: tools used to exercise the agentic loop (HU-01-01, T004)."""

from __future__ import annotations

import asyncio
from typing import Any

from harness_agent.core.entities import ToolResult
from harness_agent.core.interfaces.tool import RiskLevel, Tool


class RecordingTool(Tool):
    """Tool that records every execution (exact args) and returns a configurable result.

    ``result_call_id`` overrides the ``call_id`` of the returned ToolResult to test that
    the loop forces the id of the originating call. ``raw_result`` returns an arbitrary
    object (not a ToolResult) to test the invalid-result path.
    """

    def __init__(
        self,
        name: str = "recording_tool",
        *,
        content: str = "ok",
        is_error: bool = False,
        result_call_id: str | None = None,
        raw_result: Any = None,
        raises: Exception | None = None,
        description: str = "Recording test tool",
        schema: dict[str, Any] | None = None,
    ) -> None:
        self._name = name
        self._content = content
        self._is_error = is_error
        self._result_call_id = result_call_id
        self._raw_result = raw_result
        self._raises = raises
        self._description = description
        self._schema = schema if schema is not None else {"type": "object", "properties": {}}
        self.executions: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def schema(self) -> dict[str, Any]:
        return self._schema

    @property
    def risk(self) -> RiskLevel:
        return RiskLevel.LOW

    async def run(self, args: dict[str, Any]) -> ToolResult:
        self.executions.append(args)
        if self._raises is not None:
            raise self._raises
        if self._raw_result is not None:
            raw: ToolResult = self._raw_result
            return raw
        return ToolResult(
            call_id=self._result_call_id or "tool-chosen-id",
            content=self._content,
            is_error=self._is_error,
        )


class FailingTool(RecordingTool):
    """Tool that reports a failure through ToolResult(is_error=True)."""

    def __init__(self, name: str = "failing_tool", content: str = "file not found") -> None:
        super().__init__(name, content=content, is_error=True)


class RaisingTool(RecordingTool):
    """Tool whose run() raises an ordinary exception."""

    def __init__(self, name: str = "raising_tool", error: Exception | None = None) -> None:
        super().__init__(name, raises=error or RuntimeError("boom"))


class BlockingTool(RecordingTool):
    """Tool that waits until cancelled, to test cancellation during execution."""

    def __init__(self, name: str = "blocking_tool") -> None:
        super().__init__(name)
        self.started = asyncio.Event()

    async def run(self, args: dict[str, Any]) -> ToolResult:
        self.executions.append(args)
        self.started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable: the task must be cancelled")  # pragma: no cover
