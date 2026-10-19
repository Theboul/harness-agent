"""Test double: InMemoryToolRegistry (HU-01-01, T003).

A minimal ToolRegistry for loop tests. It is NOT HU-01-02 (owned by C): it only mimics
the contract so the loop can be exercised, including argument normalization and the
failure modes the loop must treat as fail-closed.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from harness_agent.core.interfaces.tool import Tool, ToolRegistry


class InMemoryToolRegistry(ToolRegistry):
    """Registry test double with configurable ``validate_args`` behavior."""

    def __init__(
        self,
        tools: list[Tool] | None = None,
        *,
        normalizer: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        validate_error: Exception | None = None,
        validate_return: Any = None,
        get_error: Exception | None = None,
    ) -> None:
        self._tools: dict[str, Tool] = {}
        self._normalizer = normalizer
        self.validate_error = validate_error
        self.validate_return = validate_return
        self.get_error = get_error
        self.validate_inputs: list[dict[str, Any]] = []
        self.returned_dicts: list[dict[str, Any]] = []
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        if self.get_error is not None:
            raise self.get_error
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def validate_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Record the input, then fail, return a non-dict, or return normalized args."""
        self.validate_inputs.append(args)
        if self.validate_error is not None:
            raise self.validate_error
        if self.validate_return is not None:
            returned: dict[str, Any] = self.validate_return
            return returned
        result = (
            self._normalizer(name, copy.deepcopy(args))
            if self._normalizer is not None
            else copy.deepcopy(args)
        )
        self.returned_dicts.append(result)
        return result
