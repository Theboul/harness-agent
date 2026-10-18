"""Single restoration path for conversion envelopes (design D-02).

``restore_messages(envelope)`` is the only way to rebuild canonical messages WITH their local
metadata. There is no restoration without an envelope, so a missing sidecar can never default to
``is_external=False`` (trusted).
"""

from __future__ import annotations

from harness_agent.adapters.converters.anthropic_converter import restore_anthropic_messages
from harness_agent.adapters.converters.base import ConversionError
from harness_agent.adapters.converters.openai_converter import restore_openai_messages
from harness_agent.adapters.converters.sidecar import ConversionEnvelope
from harness_agent.core.entities import Message


def restore_messages(envelope: ConversionEnvelope) -> list[Message]:
    """Restore the canonical messages of ``envelope`` exactly, failing closed on any mismatch."""
    if not isinstance(envelope, ConversionEnvelope):
        raise TypeError(
            f"restore_messages() requires a ConversionEnvelope, got {type(envelope).__name__}"
        )
    if envelope.provider == "openai":
        return restore_openai_messages(envelope)
    if envelope.provider == "anthropic":
        return restore_anthropic_messages(envelope)
    raise ConversionError(f"Unknown envelope provider {envelope.provider!r}")
