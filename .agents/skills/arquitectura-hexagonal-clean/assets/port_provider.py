# Formato real de un puerto: src/harness_agent/core/interfaces/provider.py (extracto, HU-00-01).
# Un puerto nuevo sigue el mismo molde: ABC, tipos del dominio, docstring con errores de dominio,
# reexportado en core/interfaces/__init__.py y core/__init__.py. Cambiarlo exige acuerdo de A, B y C.
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from harness_agent.core.entities import Message, TokenUsage, ToolCall


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage | None = None


class Provider(ABC):
    """Abstract Base Class for LLM providers."""

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        """Execute a completion call against the language model."""
        ...
