"""SPK-01: the same tool through LiteLLM to OpenAI and Anthropic, with no network.

This is a spike, not production code. Each test pins one observed difference between the two
providers so that HU-07-01 (canonical message format) and HU-07-02 (LiteLLM adapter) can rely
on it. LiteLLM builds the real HTTP request; the transport is replaced so the request is
captured and a canned provider-native response is returned. A socket guard fails the test if
anything tries to reach the network.

The spike needs ``litellm``, ``openai`` and ``mcp`` (LiteLLM imports ``mcp`` when completing).
They are not CI dependencies: the module is skipped when ``litellm`` is missing. To run it:
``pip install litellm mcp`` in a throwaway virtual environment (short path on Windows).
Findings: docs/decisiones/SPK-01-traduccion-herramientas-litellm.md.
"""

from __future__ import annotations

import json
import os
import socket
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest

# LiteLLM downloads its price table at import time unless told to use the bundled copy.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

litellm = pytest.importorskip("litellm")
httpx = pytest.importorskip("httpx")
openai = pytest.importorskip("openai")
http_handler = pytest.importorskip("litellm.llms.custom_httpx.http_handler")

pytestmark = pytest.mark.filterwarnings("ignore")

ANTHROPIC_MODEL = "anthropic/claude-sonnet-4-5"
OPENAI_MODEL = "openai/gpt-4o"
FAKE_KEY = "not-a-real-key"

TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a text file",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
}
FIRST_ARGS = {"path": "README.md"}
SECOND_ARGS = {"path": "docs.md"}

ANTHROPIC_CALL: dict[str, Any] = {
    "id": "msg_1",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-4-5",
    "content": [
        {"type": "text", "text": "Voy a leer."},
        {"type": "tool_use", "id": "toolu_01A", "name": "read_file", "input": FIRST_ARGS},
        {"type": "tool_use", "id": "toolu_01B", "name": "read_file", "input": SECOND_ARGS},
    ],
    "stop_reason": "tool_use",
    "usage": {"input_tokens": 20, "output_tokens": 15},
}
ANTHROPIC_FINAL: dict[str, Any] = {
    "id": "msg_2",
    "type": "message",
    "role": "assistant",
    "model": "claude-sonnet-4-5",
    "content": [{"type": "text", "text": "Listo."}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 30, "output_tokens": 5},
}
OPENAI_CALL: dict[str, Any] = {
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
                        "function": {"name": "read_file", "arguments": json.dumps(FIRST_ARGS)},
                    },
                    {
                        "id": "call_B",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps(SECOND_ARGS)},
                    },
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
    "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35},
}
OPENAI_FINAL: dict[str, Any] = {
    "id": "chatcmpl-2",
    "object": "chat.completion",
    "created": 2,
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Listo."},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 30, "completion_tokens": 5, "total_tokens": 35},
}


@dataclass
class Wire:
    """Requests LiteLLM put on the wire, per provider, in order."""

    anthropic: list[dict[str, Any]] = field(default_factory=list)
    openai: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Round:
    """Both turns of one tool round: the model asks for tools, then answers the results."""

    asked: Any
    answered: Any


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the spike must not open network connections")

    # Not ``socket.connect``: asyncio builds its self-pipe with ``socketpair`` (a loopback
    # connect on Windows). Name resolution and ``create_connection`` are how real traffic leaves.
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> Iterator[Wire]:
    captured = Wire()
    anthropic_replies = [ANTHROPIC_CALL, ANTHROPIC_FINAL]

    def fake_post(self: object, url: str, data: str | None = None, **kwargs: object) -> Any:
        assert data is not None
        captured.anthropic.append(json.loads(data))
        return httpx.Response(
            200, json=anthropic_replies.pop(0), request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(http_handler.HTTPHandler, "post", fake_post)
    yield captured


def openai_client(wire: Wire) -> Any:
    replies = [OPENAI_CALL, OPENAI_FINAL]

    def handler(request: Any) -> Any:
        wire.openai.append(json.loads(request.content))
        return httpx.Response(200, json=replies.pop(0))

    return openai.OpenAI(
        api_key=FAKE_KEY, http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def tool_round(model: str, wire: Wire, **result_extras: Any) -> Round:
    """Ask, answer every requested call with a tool message, and ask again."""
    options: dict[str, Any] = (
        {"client": openai_client(wire)} if model == OPENAI_MODEL else {"api_key": FAKE_KEY}
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": "lee README.md"}]
    asked = litellm.completion(model=model, messages=messages, tools=[TOOL], **options)
    assistant = asked.choices[0].message
    messages.append(assistant.model_dump(exclude_none=True))
    for call in assistant.tool_calls:
        messages.append(
            {"role": "tool", "tool_call_id": call.id, "content": "contenido", **result_extras}
        )
    answered = litellm.completion(model=model, messages=messages, tools=[TOOL], **options)
    return Round(asked=asked, answered=answered)


def calls_of(response: Any) -> list[Any]:
    calls: list[Any] = response.choices[0].message.tool_calls
    return calls


# --- Request side: one tool definition, two wire formats -------------------------------------


def test_the_same_tool_reaches_each_provider_in_its_native_shape(wire: Wire) -> None:
    tool_round(ANTHROPIC_MODEL, wire)
    tool_round(OPENAI_MODEL, wire)

    assert wire.openai[0]["tools"] == [TOOL]
    (anthropic_tool,) = wire.anthropic[0]["tools"]
    assert anthropic_tool == {
        "name": "read_file",
        "description": "Read a text file",
        "input_schema": TOOL["function"]["parameters"],
        "type": "custom",
    }


def test_litellm_fills_max_tokens_for_anthropic_only(wire: Wire) -> None:
    tool_round(ANTHROPIC_MODEL, wire)
    tool_round(OPENAI_MODEL, wire)

    assert wire.anthropic[0]["max_tokens"] == 64000
    assert "max_tokens" not in wire.openai[0]


# --- Response side: what LiteLLM normalizes and what it does not -------------------------------


def test_both_providers_yield_equivalent_calls(wire: Wire) -> None:
    anthropic = tool_round(ANTHROPIC_MODEL, wire).asked
    openai_round = tool_round(OPENAI_MODEL, wire).asked

    for response in (anthropic, openai_round):
        assert response.choices[0].finish_reason == "tool_calls"
        assert response.choices[0].message.content == "Voy a leer."
        assert [c.function.name for c in calls_of(response)] == ["read_file", "read_file"]
        assert [json.loads(c.function.arguments) for c in calls_of(response)] == [
            FIRST_ARGS,
            SECOND_ARGS,
        ]
        assert (response.usage.prompt_tokens, response.usage.completion_tokens) == (20, 15)


def test_call_identifiers_keep_the_provider_format_and_travel_back_unchanged(
    wire: Wire,
) -> None:
    anthropic = tool_round(ANTHROPIC_MODEL, wire)
    openai_round = tool_round(OPENAI_MODEL, wire)

    assert [c.id for c in calls_of(anthropic.asked)] == ["toolu_01A", "toolu_01B"]
    assert [c.id for c in calls_of(openai_round.asked)] == ["call_A", "call_B"]
    sent_back = wire.anthropic[1]["messages"][2]["content"]
    assert [block["tool_use_id"] for block in sent_back] == ["toolu_01A", "toolu_01B"]
    assert [m["tool_call_id"] for m in wire.openai[1]["messages"][2:]] == ["call_A", "call_B"]


def test_litellm_numbers_anthropic_calls_but_not_openai_calls(wire: Wire) -> None:
    anthropic = tool_round(ANTHROPIC_MODEL, wire).asked
    openai_round = tool_round(OPENAI_MODEL, wire).asked

    assert [c.index for c in calls_of(anthropic)] == [1, 2]
    assert [getattr(c, "index", None) for c in calls_of(openai_round)] == [None, None]


# --- Tool results: one message each versus one merged message --------------------------------


def test_results_are_one_tool_message_each_for_openai_and_one_user_message_for_anthropic(
    wire: Wire,
) -> None:
    tool_round(ANTHROPIC_MODEL, wire)
    tool_round(OPENAI_MODEL, wire)

    openai_results = wire.openai[1]["messages"][2:]
    assert [m["role"] for m in openai_results] == ["tool", "tool"]
    anthropic_messages = wire.anthropic[1]["messages"]
    assert [m["role"] for m in anthropic_messages] == ["user", "assistant", "user"]
    assert [b["type"] for b in anthropic_messages[2]["content"]] == ["tool_result", "tool_result"]
    assert [b["content"] for b in anthropic_messages[2]["content"]] == ["contenido", "contenido"]


def test_the_assistant_turn_keeps_its_text_next_to_the_calls(wire: Wire) -> None:
    tool_round(ANTHROPIC_MODEL, wire)
    tool_round(OPENAI_MODEL, wire)

    anthropic_turn = wire.anthropic[1]["messages"][1]["content"]
    assert [b["type"] for b in anthropic_turn] == ["text", "tool_use", "tool_use"]
    openai_turn = wire.openai[1]["messages"][1]
    assert openai_turn["content"] == "Voy a leer."
    assert len(openai_turn["tool_calls"]) == 2


def test_the_error_flag_is_dropped_for_anthropic_and_forwarded_untyped_to_openai(
    wire: Wire,
) -> None:
    tool_round(ANTHROPIC_MODEL, wire, is_error=True)
    tool_round(OPENAI_MODEL, wire, is_error=True)

    anthropic_results = wire.anthropic[1]["messages"][2]["content"]
    assert all("is_error" not in block for block in anthropic_results)
    openai_results = wire.openai[1]["messages"][2:]
    assert all(message["is_error"] is True for message in openai_results)


def test_litellm_message_objects_carry_provider_specific_fields_that_leak_back(
    wire: Wire,
) -> None:
    tool_round(OPENAI_MODEL, wire)

    assert wire.openai[1]["messages"][1]["provider_specific_fields"] == {"refusal": None}


def test_final_answers_are_equivalent(wire: Wire) -> None:
    anthropic = tool_round(ANTHROPIC_MODEL, wire).answered
    openai_round = tool_round(OPENAI_MODEL, wire).answered

    for response in (anthropic, openai_round):
        assert response.choices[0].finish_reason == "stop"
        assert response.choices[0].message.content == "Listo."


def test_the_network_guard_blocks_real_connections() -> None:
    with pytest.raises(AssertionError):
        socket.getaddrinfo("api.openai.com", 443)
