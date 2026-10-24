"""The adapter over the real LiteLLM, with the HTTP transport replaced (HU-07-02 / T010).

The library is the real one (the pinned version): it builds the real request for each provider
and maps the real failures to its own exceptions. Only the last step is replaced: no request is
sent, ``httpx.AsyncClient.send`` hands back a canned response (or raises a canned failure) and a
guard fails the test if anything tries to resolve a name or open a connection. The tests need
``litellm``; without it the module is skipped (it is an optional dependency).

Run it in an environment with a short path on Windows (see ``quickstart.md``).
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import re
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

# LiteLLM downloads its price table at import time unless told to use the bundled copy.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

litellm = pytest.importorskip("litellm")
httpx = pytest.importorskip("httpx")

from harness_agent.adapters.providers.litellm_provider import (  # noqa: E402
    ERROR_TABLE,
    LiteLLMProvider,
)
from harness_agent.config import Secret  # noqa: E402
from harness_agent.core import (  # noqa: E402
    Message,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    Role,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from tests.litellm_offline import keep_litellm_offline  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore")

SENTINEL = "VALOR-DE-PRUEBA-123"
ROOT = Path(__file__).resolve().parents[2]
READ_FILE = ToolDefinition(
    "read_file",
    "Read a text file",
    {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
)
USER = [Message(Role.USER, "lee README.md")]

ANTHROPIC_CALLS: dict[str, Any] = {
    "id": "msg_1",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-4-5",
    "content": [
        {"type": "text", "text": "Voy a leer."},
        {"type": "tool_use", "id": "toolu_01A", "name": "read_file", "input": {"path": "a.md"}},
        {"type": "tool_use", "id": "toolu_01B", "name": "read_file", "input": {"path": "b.md"}},
    ],
    "stop_reason": "tool_use",
    "usage": {"input_tokens": 20, "output_tokens": 15},
}
OPENAI_CALLS: dict[str, Any] = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "created": 1,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Voy a leer.",
                "tool_calls": [
                    {
                        "id": "call_A",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path": "a.md"}'},
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
    "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35},
}


@dataclass
class Wire:
    """What reached the transport, and what it will answer next."""

    requests: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    outcomes: list[Any] = field(default_factory=list)


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the tests must not open network connections")

    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    keep_litellm_offline(monkeypatch)


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> Wire:
    captured = Wire()

    async def fake_send(self: object, request: Any, **kwargs: object) -> Any:
        body = json.loads(request.content) if request.content else {}
        captured.requests.append((str(request.url), body))
        outcome = captured.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        status, payload = outcome
        return httpx.Response(status, json=payload, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)
    return captured


def adapter(model: str, key: str | None = "clave-de-prueba") -> LiteLLMProvider:
    return LiteLLMProvider(
        model, max_output_tokens=4096, api_key=None if key is None else Secret(key)
    )


# --- the names the table relies on ---------------------------------------------------------


def pinned_version() -> str:
    text = (ROOT / "requirements-dev.txt").read_text("utf-8")
    match = re.search(r"^litellm\[mcp\]==(\S+)$", text, re.MULTILINE)
    assert match
    return match.group(1)


def test_the_installed_library_is_the_pinned_version() -> None:
    assert importlib.metadata.version("litellm") == pinned_version()


@pytest.mark.parametrize("name", sorted(set(ERROR_TABLE) - {"ImportError", "APITimeoutError"}))
def test_every_failure_of_the_table_exists_in_the_pinned_library(name: str) -> None:
    assert isinstance(getattr(litellm.exceptions, name, None), type), name


def mro_names(kind: type) -> set[str]:
    return {parent.__name__ for parent in kind.__mro__}


def test_the_inheritance_the_table_relies_on_is_still_true() -> None:
    """The adapter matches by class name along the MRO, so names are what must hold."""
    exceptions = litellm.exceptions

    assert {"APITimeoutError", "APIConnectionError"} <= mro_names(exceptions.Timeout)
    assert "BadRequestError" in mro_names(exceptions.PaymentRequiredError)
    for name in ("RateLimitError", "ServiceUnavailableError", "BadGatewayError"):
        assert "APIStatusError" in mro_names(getattr(exceptions, name)), name
    assert "APIStatusError" in mro_names(exceptions.InternalServerError)


# --- the request the library really builds --------------------------------------------------


class TestAnthropicRequestAndAnswer:
    async def test_the_cap_is_ours_and_the_tool_has_its_native_shape(self, wire: Wire) -> None:
        wire.outcomes = [(200, ANTHROPIC_CALLS)]

        await adapter("anthropic/claude-sonnet-4-5").complete(list(USER), [READ_FILE])

        (url, body) = wire.requests[0]
        assert url == "https://api.anthropic.com/v1/messages"
        assert body["max_tokens"] == 4096
        (tool,) = body["tools"]
        assert tool["name"] == "read_file"
        assert tool["input_schema"] == READ_FILE.parameters
        assert "provider_specific_fields" not in json.dumps(body)

    async def test_two_calls_arrive_in_order_with_opaque_ids_and_the_usage(
        self, wire: Wire
    ) -> None:
        wire.outcomes = [(200, ANTHROPIC_CALLS)]

        response = await adapter("anthropic/claude-sonnet-4-5").complete(list(USER), [READ_FILE])

        assert response.content == "Voy a leer."
        assert response.tool_calls == [
            ToolCall("toolu_01A", "read_file", {"path": "a.md"}),
            ToolCall("toolu_01B", "read_file", {"path": "b.md"}),
        ]
        assert response.usage is not None
        assert (response.usage.input_tokens, response.usage.output_tokens) == (20, 15)

    async def test_the_next_request_carries_the_results_and_the_error_tag(self, wire: Wire) -> None:
        final = {**ANTHROPIC_CALLS, "content": [{"type": "text", "text": "Listo."}]}
        final["stop_reason"] = "end_turn"
        wire.outcomes = [(200, ANTHROPIC_CALLS), (200, final)]
        provider = adapter("anthropic/claude-sonnet-4-5")
        first = await provider.complete(list(USER), [READ_FILE])
        history = [
            *USER,
            Message(Role.ASSISTANT, first.content, tool_calls=tuple(first.tool_calls)),
            Message(Role.TOOL, "contenido", tool_result=ToolResult("toolu_01A", "contenido")),
            Message(
                Role.TOOL,
                "no se pudo",
                tool_result=ToolResult("toolu_01B", "no se pudo", is_error=True),
            ),
        ]

        second = await provider.complete(history, [READ_FILE])

        body = wire.requests[1][1]
        text = json.dumps(body, ensure_ascii=False)
        assert second.content == "Listo."
        assert body["max_tokens"] == 4096
        assert "toolu_01A" in text and "toolu_01B" in text
        assert "[tool_error] no se pudo" in text
        assert "provider_specific_fields" not in text


class TestTheSameAdapterForOtherProviders:
    @pytest.mark.parametrize(
        ("model", "url"),
        [
            ("openai/gpt-4o", "https://api.openai.com/v1/chat/completions"),
            ("openrouter/openai/gpt-4o", "https://openrouter.ai/api/v1/chat/completions"),
        ],
    )
    async def test_only_the_prefix_changes_the_destination(
        self, wire: Wire, model: str, url: str
    ) -> None:
        wire.outcomes = [(200, OPENAI_CALLS)]

        response = await adapter(model).complete(list(USER), [READ_FILE])

        (sent_url, body) = wire.requests[0]
        assert sent_url == url
        assert body["max_tokens"] == 4096
        assert {"model", "messages", "tools"} <= set(body)
        assert "provider_specific_fields" not in json.dumps(body)
        assert response.tool_calls == [ToolCall("call_A", "read_file", {"path": "a.md"})]

    async def test_a_local_provider_without_a_key_goes_to_the_default_local_server(
        self, wire: Wire
    ) -> None:
        wire.outcomes = [httpx.ConnectError("sin servidor")]

        with pytest.raises(ProviderUnavailable) as raised:
            await adapter("ollama/modelo-local", key=None).complete(list(USER))

        assert "localhost:11434" in wire.requests[0][0]
        assert "no está disponible" in str(raised.value)


# --- the failures the library really raises -------------------------------------------------


def failure_body(message: str) -> dict[str, Any]:
    return {"type": "error", "error": {"type": "api_error", "message": message}}


class TestRealFailures:
    @pytest.mark.parametrize(
        ("status", "canonical", "fragment"),
        [
            (429, QuotaExceeded, "límite de tasa"),
            (402, QuotaExceeded, "cuota o el crédito"),
            (503, ProviderUnavailable, "no está disponible"),
            (502, ProviderUnavailable, "no está disponible"),
            (500, ProviderUnavailable, "no está disponible"),
            (401, ProviderError, "devolvió un error"),
            (400, ProviderError, "devolvió un error"),
            (404, ProviderError, "devolvió un error"),
        ],
    )
    async def test_each_status_becomes_its_canonical_type(
        self, wire: Wire, status: int, canonical: type[ProviderError], fragment: str
    ) -> None:
        wire.outcomes = [(status, failure_body("fallo del proveedor"))]

        with pytest.raises(ProviderError) as raised:
            await adapter("anthropic/claude-sonnet-4-5").complete(list(USER))

        assert type(raised.value) is canonical
        assert fragment in str(raised.value)
        assert raised.value.__cause__ is not None
        assert len(wire.requests) == 1

    async def test_a_slow_provider_is_a_timeout(self, wire: Wire) -> None:
        wire.outcomes = [httpx.ReadTimeout("lento")]

        with pytest.raises(ProviderTimeout):
            await adapter("anthropic/claude-sonnet-4-5").complete(list(USER))

    @pytest.mark.parametrize("status", [401, 429, 500])
    async def test_a_provider_that_repeats_the_key_leaves_no_trace(
        self, wire: Wire, status: int
    ) -> None:
        wire.outcomes = [(status, failure_body(f"clave incorrecta: {SENTINEL}"))]

        with pytest.raises(ProviderError) as raised:
            await adapter("anthropic/claude-sonnet-4-5", key=SENTINEL).complete(list(USER))

        for text in (str(raised.value), repr(raised.value), *map(str, raised.value.args)):
            assert SENTINEL not in text
