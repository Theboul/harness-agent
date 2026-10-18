"""Base protocol and domain exceptions for provider message converters.

Maintains strict separation between external provider schemas and HARNESS core models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from harness_agent.core.entities import Message
from harness_agent.core.interfaces.provider import ProviderResponse, ToolDefinition

if TYPE_CHECKING:
    from harness_agent.adapters.converters.sidecar import ConversionEnvelope


class ConversionError(ValueError):
    """Raised when a canonical structure cannot be converted to/from a provider wire format."""


class ProviderMessageConverter(Protocol):
    """Contract for provider-specific wire format converters."""

    def to_provider_payload(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> dict[str, Any]:
        """Convert canonical messages and tools into provider API request payload."""
        ...

    def to_canonical_response(
        self,
        raw_response: dict[str, Any],
    ) -> ProviderResponse:
        """Parse raw provider API response payload into canonical ProviderResponse."""
        ...


class EnvelopeConverter(Protocol):
    """Additional contract for converters that can also produce a restorable envelope.

    Kept separate from ``ProviderMessageConverter`` so existing implementations are unaffected.
    """

    def to_provider_envelope(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        *,
        partial_window: bool = False,
    ) -> ConversionEnvelope:
        """Convert and keep the local metadata needed for an exact restoration."""
        ...
