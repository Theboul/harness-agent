"""How the adapter builds the call to the model (HU-07-02 / FR-005, FR-006, FR-007, FR-009).

The request is built from canonical messages with the converters of HU-07-01; the cap of output
tokens is always sent; nothing of a previous LiteLLM response travels back.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from harness_agent.adapters.converters import to_openai_messages, to_openai_tools
from harness_agent.adapters.providers.litellm_provider import LiteLLMProvider
from harness_agent.config import Secret
from harness_agent.core import (
    Message,
    ProviderError,
    Role,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from tests.unit.adapters.providers.support import (
    MAX_OUTPUT_TOKENS,
    MODEL,
    SENTINEL,
    make_provider,
    noop_completion,
)

READ_FILE = ToolDefinition(
    name="read_file",
    description="Read a text file",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
)
USER = Message(Role.USER, "lee README.md")
KEY = Secret(SENTINEL)


def request_of(
    messages: list[Message],
    tools: list[ToolDefinition] | None = None,
    **options: Any,
) -> dict[str, Any]:
    provider, _ = make_provider(**options)
    return provider.build_request(messages, tools)


def tool_round(call_id: str, content: str, *, is_error: bool) -> list[Message]:
    call = ToolCall(id=call_id, name="read_file", arguments={"path": "README.md"})
    return [
        USER,
        Message(Role.ASSISTANT, "voy", tool_calls=(call,)),
        Message(Role.TOOL, content, tool_result=ToolResult(call_id, content, is_error)),
    ]


class TestConstruction:
    @pytest.mark.parametrize("model", ["", "sin-barra", "a/", "/b", " /b", "a/ ", 5, None])
    def test_a_model_without_the_provider_slash_model_form_is_rejected(self, model: Any) -> None:
        with pytest.raises(ValueError, match="proveedor"):
            LiteLLMProvider(model, max_output_tokens=10, completion=noop_completion)

    def test_the_rejection_never_reproduces_the_received_value(self) -> None:
        with pytest.raises(ValueError) as raised:
            LiteLLMProvider(SENTINEL, max_output_tokens=10, completion=noop_completion)

        assert SENTINEL not in str(raised.value)

    @pytest.mark.parametrize("value", [0, -1, True, False, "4096", 1.5, None])
    def test_the_cap_must_be_an_integer_greater_than_zero(self, value: Any) -> None:
        with pytest.raises(ValueError, match="max_output_tokens"):
            LiteLLMProvider(MODEL, max_output_tokens=value, completion=noop_completion)

    def test_any_provider_prefix_is_accepted_without_a_branch(self) -> None:
        for model in ("anthropic/x", "groq/y", "ollama/z", "algo-nuevo/modelo/con/barras"):
            provider, _ = make_provider(model=model)

            assert provider.model == model

    def test_the_representation_hides_the_key_and_shows_model_and_cap(self) -> None:
        provider, _ = make_provider(api_key=KEY)

        for text in (repr(provider), str(provider), f"{provider}", format(provider, "")):
            assert SENTINEL not in text
            assert str(len(SENTINEL)) not in text
            assert MODEL in text
            assert str(MAX_OUTPUT_TOKENS) in text
            assert "<oculta>" in text

    def test_the_representation_without_a_key_says_so(self) -> None:
        provider, _ = make_provider()

        assert "<oculta>" not in repr(provider)
        assert "api_key=None" in repr(provider)


class TestTheCall:
    def test_it_has_exactly_the_expected_fields_without_tools_or_key(self) -> None:
        request = request_of([USER])

        assert set(request) == {"model", "messages", "max_tokens", "num_retries"}
        assert request["model"] == MODEL

    @pytest.mark.parametrize("tools", [None, [], [READ_FILE]])
    def test_the_cap_of_output_tokens_is_always_sent(
        self, tools: list[ToolDefinition] | None
    ) -> None:
        assert request_of([USER], tools)["max_tokens"] == MAX_OUTPUT_TOKENS

    @pytest.mark.parametrize("cap", [1, 512, 8192])
    def test_the_cap_is_the_configured_one(self, cap: int) -> None:
        assert request_of([USER], max_output_tokens=cap)["max_tokens"] == cap

    def test_there_are_no_hidden_retries(self) -> None:
        assert request_of([USER])["num_retries"] == 0

    @pytest.mark.parametrize("tools", [None, []])
    def test_the_tools_field_is_left_out_when_there_are_no_tools(
        self, tools: list[ToolDefinition] | None
    ) -> None:
        assert "tools" not in request_of([USER], tools)

    def test_the_tools_are_translated_by_the_converter(self) -> None:
        request = request_of([USER], [READ_FILE])

        assert request["tools"] == to_openai_tools([READ_FILE])

    def test_the_key_is_sent_only_when_there_is_one(self) -> None:
        assert "api_key" not in request_of([USER])
        assert request_of([USER], api_key=KEY)["api_key"] == SENTINEL

    def test_the_messages_come_from_the_converter_with_no_extra_fields(self) -> None:
        messages = tool_round("call_A", "contenido", is_error=False)

        request = request_of(messages)

        assert request["messages"] == to_openai_messages(messages)
        for wire in request["messages"]:
            assert "provider_specific_fields" not in wire
            assert "refusal" not in wire

    def test_no_tool_choice_and_no_streaming(self) -> None:
        request = request_of([USER], [READ_FILE])

        assert "tool_choice" not in request
        assert "stream" not in request

    def test_the_arguments_are_not_modified(self) -> None:
        messages = tool_round("call_A", "boom", is_error=True)
        tools = [READ_FILE]
        before = (copy.deepcopy(messages), copy.deepcopy(tools))

        request_of(messages, tools)

        assert (messages, tools) == before


class TestAToolErrorTravelsInTheContent:
    def test_an_error_without_a_tag_gets_the_generic_one(self) -> None:
        request = request_of(tool_round("call_A", "no se pudo leer", is_error=True))

        assert request["messages"][2]["content"] == "[tool_error] no se pudo leer"

    @pytest.mark.parametrize(
        "content",
        [
            "[invalid_arguments] Arguments were rejected",
            "[permission_denied] denied",
            "  [fuera_del_area] ruta fuera",
            "[tool_exception]",
        ],
    )
    def test_an_error_that_already_has_a_tag_is_left_as_it_is(self, content: str) -> None:
        request = request_of(tool_round("call_A", content, is_error=True))

        assert request["messages"][2]["content"] == content

    def test_text_that_only_looks_like_a_tag_still_gets_one(self) -> None:
        for content in ("[Not-A-Tag] x", "[ ] x", "[]", "x [tag]"):
            request = request_of(tool_round("call_A", content, is_error=True))

            assert request["messages"][2]["content"] == f"[tool_error] {content}"

    def test_a_result_that_is_not_an_error_is_not_touched(self) -> None:
        request = request_of(tool_round("call_A", "contenido", is_error=False))

        assert request["messages"][2]["content"] == "contenido"

    def test_the_canonical_history_keeps_its_original_content(self) -> None:
        messages = tool_round("call_A", "no se pudo leer", is_error=True)

        request_of(messages)

        assert messages[2].tool_result is not None
        assert messages[2].tool_result.content == "no se pudo leer"
        assert messages[2].tool_result.is_error is True

    def test_the_error_flag_itself_does_not_travel(self) -> None:
        request = request_of(tool_round("call_A", "x", is_error=True))

        assert "is_error" not in request["messages"][2]


class TestCallIdentifiersAreOpaque:
    @pytest.mark.parametrize(
        "call_id", ["x", "toolu_01A", "call_A", "id con espacios", "7", "a" * 200, "ñandú-ü"]
    )
    def test_the_id_travels_unchanged_to_the_call_and_to_its_result(self, call_id: str) -> None:
        request = request_of(tool_round(call_id, "contenido", is_error=False))

        assert request["messages"][1]["tool_calls"][0]["id"] == call_id
        assert request["messages"][2]["tool_call_id"] == call_id


class TestAnUnrepresentableHistory:
    def test_it_fails_as_a_provider_error_in_spanish_without_the_content(self) -> None:
        history = [USER, Message(Role.SYSTEM, SENTINEL)]

        with pytest.raises(ProviderError) as raised:
            request_of(history)

        assert SENTINEL not in str(raised.value)
        assert "historial" in str(raised.value)

    def test_a_tool_definition_the_converter_rejects_fails_the_same_way(self) -> None:
        broken = ToolDefinition("t", "d", parameters=SENTINEL)  # type: ignore[arg-type]

        with pytest.raises(ProviderError) as raised:
            request_of([USER], [broken])

        assert SENTINEL not in str(raised.value)
