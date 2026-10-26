"""AC-01 and AC-02 of HU-02-01 with real pieces: assembler, scripted provider and usage.

``AgentLoop`` is protected (area A) and does not take the assembler yet, so the turn loop here is
written by hand around ``Provider.complete``: it shows the integration point the findings
describe (assemble, call, record usage).
"""

from __future__ import annotations

import harness_agent.core as core
from harness_agent.core import (
    ContextAssembler,
    Message,
    PrefixSpec,
    ProviderResponse,
    Role,
    TokenUsage,
    ToolDefinition,
)
from tests.doubles import ScriptedProvider

SESSION = "session-1"
EXPORTED = {
    "AssembledContext",
    "ContextAssembler",
    "ContextConfigError",
    "PrefixSpec",
    "StablePrefix",
    "TokenEstimator",
    "build_prefix",
    "estimate_message",
    "estimate_messages",
    "estimate_text",
    "estimate_tool_definition",
}


def test_the_public_api_is_exported_from_core() -> None:
    assert EXPORTED <= set(core.__all__)
    for name in EXPORTED:
        assert getattr(core, name) is not None


async def test_prefix_is_stable_and_estimate_converges_to_the_reported_usage() -> None:
    definitions = [ToolDefinition("leer_archivo", "Read a file.", {"type": "object"})]
    assembler = ContextAssembler(
        PrefixSpec("Be precise.", ("Ask first.",), "Windows 11", "PowerShell"),
        lambda: definitions,
    )
    reported = [120, 150, 190]
    provider = ScriptedProvider(
        [ProviderResponse(f"answer {i}", usage=TokenUsage(r, 20)) for i, r in enumerate(reported)]
    )
    history: list[Message] = []
    estimates: list[int] = []
    for turn in range(3):
        history.append(Message(Role.USER, f"question {turn}"))
        context = assembler.assemble(SESSION, history)
        estimates.append(context.estimated_tokens)
        response = await provider.complete(context.provider_messages(), list(context.tools))
        assembler.record_usage(SESSION, response.usage)
        history.append(Message(Role.ASSISTANT, response.content))

    prefixes = [messages[0] for messages in provider.received]
    assert prefixes[0].role is Role.SYSTEM
    assert prefixes[0] == prefixes[1] == prefixes[2]
    assert provider.received_tools[0] == provider.received_tools[2]
    # The same content estimated again matches what the provider reported (AC-02).
    again = assembler.assemble(SESSION, history[:-1])
    assert estimates[0] != reported[0]
    assert again.estimated_tokens == reported[2]
