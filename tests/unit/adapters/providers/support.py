"""Shared builders for the LiteLLM adapter tests (HU-07-02).

``RecordingCompletion`` stands in for ``litellm.acompletion``: it records a copy of the keyword
arguments of every call and replays scripted outcomes (a response, or an exception to raise).
Nothing here needs ``litellm`` or the network.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from harness_agent.adapters.providers.litellm_provider import LiteLLMProvider
from harness_agent.config import Secret

SENTINEL = "VALOR-DE-PRUEBA-123"
MODEL = "proveedor/modelo"
MAX_OUTPUT_TOKENS = 4096


async def noop_completion(**kwargs: Any) -> Any:
    """A completion function that must never be needed (for tests that only build the adapter)."""
    raise AssertionError("the completion function was not expected to be called")


class RecordingCompletion:
    """An injectable completion function that records calls and replays outcomes."""

    def __init__(self, *outcomes: Any) -> None:
        self.calls: list[dict[str, Any]] = []
        self._outcomes = list(outcomes)

    async def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(copy.deepcopy(kwargs))
        outcome = self._outcomes.pop(0) if self._outcomes else reply("listo")
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def reply(
    content: str | None = "",
    calls: list[dict[str, Any]] | None = None,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A response in the common wire shape (what LiteLLM returns, as a plain dictionary)."""
    message: dict[str, Any] = {"role": "assistant", "content": content}
    if calls is not None:
        message["tool_calls"] = calls
    response: dict[str, Any] = {"choices": [{"index": 0, "message": message}]}
    if usage is not None:
        response["usage"] = usage
    return response


def wire_call(call_id: str, name: str, arguments: Any, index: int | None = None) -> dict[str, Any]:
    """A tool call as the wire carries it: ``arguments`` is a JSON string unless told otherwise."""
    function = {
        "name": name,
        "arguments": json.dumps(arguments) if isinstance(arguments, dict) else arguments,
    }
    call: dict[str, Any] = {"id": call_id, "type": "function", "function": function}
    if index is not None:
        call["index"] = index
    return call


def make_provider(
    *outcomes: Any,
    model: str = MODEL,
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    api_key: Secret | None = None,
) -> tuple[LiteLLMProvider, RecordingCompletion]:
    """An adapter wired to a recording completion function."""
    completion = RecordingCompletion(*outcomes)
    provider = LiteLLMProvider(
        model, max_output_tokens=max_output_tokens, api_key=api_key, completion=completion
    )
    return provider, completion
