"""Provider wire-format converters for HARNESS adapters.

Isolates vendor-specific schemas (OpenAI, Anthropic, Gemini) from the pure core domain.
"""

from __future__ import annotations

from harness_agent.adapters.converters.anthropic_converter import (
    AnthropicConverter,
    from_anthropic_payload,
    from_anthropic_response,
    to_anthropic_envelope,
    to_anthropic_payload,
)
from harness_agent.adapters.converters.base import (
    ConversionError,
    EnvelopeConverter,
    ProviderMessageConverter,
)
from harness_agent.adapters.converters.openai_converter import (
    OpenAIConverter,
    from_openai_messages,
    from_openai_response,
    to_openai_envelope,
    to_openai_messages,
    to_openai_tools,
)
from harness_agent.adapters.converters.restore import restore_messages
from harness_agent.adapters.converters.sidecar import (
    ConversionEnvelope,
    MessageMeta,
    WireRef,
)

__all__ = [
    "AnthropicConverter",
    "ConversionEnvelope",
    "ConversionError",
    "EnvelopeConverter",
    "MessageMeta",
    "OpenAIConverter",
    "ProviderMessageConverter",
    "WireRef",
    "from_anthropic_payload",
    "from_anthropic_response",
    "from_openai_messages",
    "from_openai_response",
    "restore_messages",
    "to_anthropic_envelope",
    "to_anthropic_payload",
    "to_openai_envelope",
    "to_openai_messages",
    "to_openai_tools",
]
