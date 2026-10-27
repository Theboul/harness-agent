"""The converters take a compacted history as it is (HU-02-03, decision D4 of the analysis).

After a compaction the history is ``[SYSTEM..., USER request, USER external summary, recent...]``:
two ``USER`` messages in a row. Every converter must accept it, keep every message and its order,
and restore it exactly. The converters are not touched; this only proves they already cope.
"""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.adapters.converters import (
    AnthropicConverter,
    ConversionEnvelope,
    OpenAIConverter,
    restore_messages,
    to_anthropic_envelope,
    to_anthropic_payload,
    to_openai_envelope,
    to_openai_messages,
)
from harness_agent.core import (
    Message,
    Role,
    ToolCall,
    ToolDefinition,
    ToolResult,
    frame_summary,
)

TOOLS = [ToolDefinition("leer_archivo", "Lee un archivo.", {"type": "object", "properties": {}})]


def compacted_history() -> list[Message]:
    return [
        Message(Role.SYSTEM, "entorno del sistema"),
        Message(Role.SYSTEM, "instrucciones de git"),
        Message(Role.USER, "petición inicial"),
        frame_summary("Se migró el módulo."),
        Message(
            Role.ASSISTANT, "miro el archivo", (ToolCall("c1", "leer_archivo", {"path": "a"}),)
        ),
        Message(Role.TOOL, "datos", tool_result=ToolResult("c1", "datos"), is_external=True),
        Message(Role.ASSISTANT, "", (ToolCall("c2", "leer_archivo", {"path": "b"}),)),
        Message(Role.TOOL, "otros", tool_result=ToolResult("c2", "otros", True), is_external=True),
        Message(Role.ASSISTANT, "listo"),
        Message(Role.USER, "siguiente tarea"),
    ]


def texts_in_order(node: Any) -> list[str]:
    """Every text of a payload, in the order it appears."""
    found: list[str] = []
    if isinstance(node, str):
        found.append(node)
    elif isinstance(node, dict):
        for key, value in node.items():
            if key in ("tools", "input", "arguments", "function"):
                continue
            found.extend(texts_in_order(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(texts_in_order(item))
    return found


def assert_order_kept(payload: dict[str, Any], history: list[Message]) -> None:
    ordered = texts_in_order(payload.get("system", [])) + texts_in_order(payload["messages"])
    joined = chr(0).join(ordered)
    position = -1
    system = [m for m in history if m.role is Role.SYSTEM]
    for message in [*system, *(m for m in history if m.role is not Role.SYSTEM)]:
        if not message.content:
            continue
        found = joined.find(message.content, position + 1)
        assert found > position, f"{message.content!r} is missing or out of order"
        position = found


def envelope_for(provider: str, messages: list[Message]) -> ConversionEnvelope:
    if provider == "openai":
        return to_openai_envelope(messages, TOOLS)
    return to_anthropic_envelope(messages, TOOLS)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_a_compacted_history_converts_and_restores_exactly(provider: str) -> None:
    history = compacted_history()

    envelope = envelope_for(provider, history)
    restored = restore_messages(envelope)

    assert restored == history  # nothing lost, nothing reordered
    assert [m.is_external for m in restored] == [m.is_external for m in history]
    assert envelope.provider == provider
    assert_order_kept(envelope.payload, history)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_the_summary_is_never_promoted_to_a_trusted_message(provider: str) -> None:
    restored = restore_messages(envelope_for(provider, compacted_history()))

    summary = restored[3]
    assert summary.role is Role.USER and summary.is_external
    assert not restored[2].is_external


def test_the_plain_payloads_keep_the_two_user_messages() -> None:
    history = compacted_history()

    openai = OpenAIConverter().to_provider_payload(history, TOOLS)
    anthropic = AnthropicConverter().to_provider_payload(history, TOOLS)

    assert_order_kept(openai, history)
    assert_order_kept(anthropic, history)
    assert len(to_openai_messages(history)) == len(history)
    assert "petición inicial" in str(anthropic) and "Se migró el módulo." in str(anthropic)
    assert anthropic == to_anthropic_payload(history, TOOLS)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_a_history_with_a_summary_and_nothing_else_after_the_request_converts(
    provider: str,
) -> None:
    history = [
        Message(Role.SYSTEM, "entorno"),
        Message(Role.USER, "petición"),
        frame_summary("resumen"),
        Message(Role.ASSISTANT, "ok"),
    ]

    assert restore_messages(envelope_for(provider, history)) == history
