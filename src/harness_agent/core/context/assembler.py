"""Per-session context assembler: frozen stable prefix first, variable content after (HU-02-01).

It is the pure building block the future ``ContextManager`` (HU-02-03, HU-02-06.1) will compose:
it owns no history, store or provider. The caller passes the history of the turn and gets back
the messages and tool definitions to send plus a calibrated token estimate.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from harness_agent.core.context.errors import ContextConfigError
from harness_agent.core.context.estimator import (
    TokenEstimator,
    estimate_messages,
    estimate_tool_definition,
)
from harness_agent.core.context.prefix import PrefixSpec, StablePrefix, build_prefix
from harness_agent.core.entities import Message, TokenUsage
from harness_agent.core.interfaces.provider import ToolDefinition


@dataclass(frozen=True)
class AssembledContext:
    """What one model call receives, plus its token estimate.

    Attributes:
        prefix: Stable prefix of the session (identical in every turn).
        history: Copy of the variable messages, in order.
        raw_tokens: Heuristic estimate of everything sent, before calibration.
        estimated_tokens: ``raw_tokens`` corrected with the session calibration factor.
    """

    prefix: StablePrefix
    history: tuple[Message, ...]
    raw_tokens: int
    estimated_tokens: int

    @property
    def tools(self) -> tuple[ToolDefinition, ...]:
        """Tool definitions to send, sorted by name."""
        return self.prefix.tools

    def provider_messages(self) -> list[Message]:
        """Messages for ``Provider.complete``: the system prefix first, then the history."""
        return [self.prefix.system_message, *self.history]


class ContextAssembler:
    """Builds the context of each turn and corrects its estimate with the reported usage."""

    def __init__(
        self,
        spec: PrefixSpec,
        definitions: Callable[[], Sequence[ToolDefinition]],
        estimator: TokenEstimator | None = None,
    ) -> None:
        self._spec = spec
        self._definitions = definitions
        self._estimator = estimator if estimator is not None else TokenEstimator()
        self._prefixes: dict[str, StablePrefix] = {}
        self._last_raw: dict[str, int] = {}

    def assemble(self, session_id: str, history: Sequence[Message]) -> AssembledContext:
        """Assemble the context of a turn; the session prefix is built once and then reused."""
        if not session_id.strip():
            raise ContextConfigError("El identificador de sesión no puede estar vacío.")
        prefix = self._prefixes.get(session_id)
        if prefix is None:
            prefix = build_prefix(self._spec, self._definitions())
            self._prefixes[session_id] = prefix
        messages = tuple(copy.deepcopy(message) for message in history)
        raw = estimate_messages([prefix.system_message, *messages]) + sum(
            estimate_tool_definition(tool) for tool in prefix.tools
        )
        self._last_raw[session_id] = raw
        return AssembledContext(prefix, messages, raw, self._estimator.calibrated(session_id, raw))

    def record_usage(self, session_id: str, usage: TokenUsage | None) -> None:
        """Correct the estimate with the input tokens the provider reported for the last call."""
        raw = self._last_raw.pop(session_id, None)
        if raw is None or usage is None:
            return
        self._estimator.observe(session_id, raw, usage.input_tokens)
