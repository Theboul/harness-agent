"""Test double: FakeProvider, the scripted provider of HU-00-03 (V-14).

Replays an ordered script, one step per call, with no network, clock or randomness. A step is
either a ``ProviderResponse`` or a canonical ``ProviderError`` that the call raises at once
(quota, timeout or unavailable), without waiting. It is the
official double for new stories; ``ScriptedProvider`` (HU-01-01) and ``DummyProvider`` stay as they
are. Every call receives its own copy of the step, and the script is copied when the provider is
built, so two instances of the same script never share state.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence

from harness_agent.core.entities import Message
from harness_agent.core.interfaces.provider import (
    Provider,
    ProviderError,
    ProviderResponse,
    ToolDefinition,
)
from tests.doubles.scripted_provider import ScriptExhausted

Step = ProviderResponse | ProviderError


class FakeProvider(Provider):
    """Provider that replays a finite script of steps, one per ``complete`` call."""

    def __init__(self, script: Sequence[Step]) -> None:
        steps = list(script)
        self._validate(steps)
        self._script: list[Step] = copy.deepcopy(steps)
        self.received: list[list[Message]] = []
        self.received_tools: list[list[ToolDefinition] | None] = []
        self.call_count = 0
        self.exhausted = False

    @staticmethod
    def _validate(steps: list[Step]) -> None:
        """Reject an invalid script when the provider is built, not in the middle of a test."""
        if not steps:
            raise ValueError("El guion está vacío; dale al menos un paso.")
        seen: set[str] = set()
        for index, step in enumerate(steps):
            if isinstance(step, ProviderError):
                continue
            if not isinstance(step, ProviderResponse):
                raise ValueError(
                    f"El paso {index} del guion es de tipo {type(step).__name__}, "
                    "no una ProviderResponse ni una instancia de ProviderError."
                )
            for call in step.tool_calls:
                if not call.id:
                    raise ValueError(
                        f"El paso {index} del guion tiene una llamada a herramienta sin id."
                    )
                if call.id in seen:
                    raise ValueError(
                        f"El paso {index} del guion repite el id de una llamada a herramienta; "
                        "los ids deben ser únicos en todo el guion."
                    )
                seen.add(call.id)

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        """Record copies of the arguments and replay the next step of the script."""
        self.received.append(copy.deepcopy(list(messages)))
        self.received_tools.append(None if tools is None else copy.deepcopy(list(tools)))
        index = self.call_count
        self.call_count += 1
        if index >= len(self._script):
            self.exhausted = True
            raise ScriptExhausted(f"El guion se agotó en la llamada {index + 1} al proveedor.")
        step = copy.deepcopy(self._script[index])
        if isinstance(step, ProviderError):
            raise step
        return step
