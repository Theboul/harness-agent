"""How the adapter reads the answer of the model (HU-07-02 / FR-005, FR-007, FR-008, FR-011).

The response is translated with the converters of HU-07-01. Tool arguments that cannot be read
never break the turn: the call carries a marker field that the loop rejects as
``[invalid_arguments]`` (research.md, section 3).
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from harness_agent.core import (
    Message,
    ProviderError,
    ProviderResponse,
    Role,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from tests.unit.adapters.providers.support import SENTINEL, make_provider, reply, wire_call

MARKER = "arguments_not_valid_json"
USER = [Message(Role.USER, "haz algo")]
FREE_FORM = ToolDefinition(
    "libre", "acepta campos adicionales", {"type": "object", "additionalProperties": True}
)
STRICT = ToolDefinition(
    "estricta", "no acepta campos adicionales", {"type": "object", "additionalProperties": False}
)


async def answer(outcome: Any, tools: list[ToolDefinition] | None = None) -> ProviderResponse:
    provider, _ = make_provider(outcome)
    return await provider.complete(list(USER), tools)


class TestAnAnswerWithText:
    async def test_only_text(self) -> None:
        response = await answer(reply("hola"))

        assert response == ProviderResponse(content="hola", tool_calls=[], usage=None)

    async def test_the_usage_becomes_token_usage(self) -> None:
        usage = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}

        response = await answer(reply("hola", usage=usage))

        assert response.usage == TokenUsage(input_tokens=3, output_tokens=2)

    async def test_a_counter_that_is_none_counts_as_zero(self) -> None:
        response = await answer(
            reply("hola", usage={"prompt_tokens": None, "completion_tokens": 7})
        )

        assert response.usage == TokenUsage(input_tokens=0, output_tokens=7)

    async def test_a_response_without_usage_has_none(self) -> None:
        assert (await answer(reply("hola"))).usage is None

    async def test_an_object_with_model_dump_is_read_like_a_dictionary(self) -> None:
        class Response:
            def model_dump(self) -> dict[str, Any]:
                return reply("desde un objeto")

        assert (await answer(Response())).content == "desde un objeto"


class TestAnAnswerWithToolCalls:
    @pytest.mark.parametrize("indexes", [(1, 1), (None, None), (0, 5), (7, 2)])
    async def test_the_order_of_the_list_wins_over_the_index(
        self, indexes: tuple[int | None, int | None]
    ) -> None:
        calls = [
            wire_call("toolu_01A", "read_file", {"path": "a.md"}, indexes[0]),
            wire_call("toolu_01B", "read_file", {"path": "b.md"}, indexes[1]),
        ]

        response = await answer(reply("Voy a leer.", calls))

        assert response.content == "Voy a leer."
        assert response.tool_calls == [
            ToolCall("toolu_01A", "read_file", {"path": "a.md"}),
            ToolCall("toolu_01B", "read_file", {"path": "b.md"}),
        ]

    async def test_no_text_with_calls_gives_an_empty_text(self) -> None:
        response = await answer(reply(None, [wire_call("call_A", "read_file", {"path": "a"})]))

        assert response.content == ""
        assert [call.id for call in response.tool_calls] == ["call_A"]

    @pytest.mark.parametrize("call_id", ["x", "toolu_01A", "call_A", "7", "a" * 200, "ñandú-ü"])
    async def test_the_identifier_is_opaque(self, call_id: str) -> None:
        response = await answer(reply("", [wire_call(call_id, "read_file", {})]))

        assert response.tool_calls[0].id == call_id

    async def test_two_calls_with_the_same_id_are_let_through_for_the_loop_to_judge(self) -> None:
        calls = [wire_call("dup", "read_file", {}), wire_call("dup", "read_file", {})]

        response = await answer(reply("", calls))

        assert [call.id for call in response.tool_calls] == ["dup", "dup"]


class TestToolArguments:
    async def test_a_json_object_becomes_a_dictionary(self) -> None:
        response = await answer(reply("", [wire_call("c", "t", {"a": 1, "b": [True, None]})]))

        assert response.tool_calls[0].arguments == {"a": 1, "b": [True, None]}

    async def test_a_dictionary_already_parsed_is_accepted(self) -> None:
        raw = {"id": "c", "function": {"name": "t", "arguments": {"a": 1}}}

        response = await answer(reply("", [raw]))

        assert response.tool_calls[0].arguments == {"a": 1}

    async def test_a_call_without_the_arguments_field_has_no_arguments(self) -> None:
        raw = {"id": "c", "function": {"name": "t"}}

        response = await answer(reply("", [raw]))

        assert response.tool_calls[0].arguments == {}

    @pytest.mark.parametrize("blank", ["", "   ", "\n"])
    async def test_blank_arguments_are_an_empty_object(self, blank: str) -> None:
        response = await answer(reply("", [wire_call("c", "t", blank)]))

        assert response.tool_calls[0].arguments == {}

    @pytest.mark.parametrize(
        "raw", ["{no es json", "[1, 2]", "5", "null", '"texto"', "true", "{'a': 1}", None, 7, [1]]
    )
    async def test_unreadable_arguments_carry_the_marker_with_the_received_text(
        self, raw: Any
    ) -> None:
        response = await answer(reply("", [wire_call("c", "t", raw)]))

        text = raw if isinstance(raw, str) else str(raw)
        assert response.tool_calls[0].arguments == {MARKER: text}
        assert response.tool_calls[0].id == "c"
        assert response.tool_calls[0].name == "t"

    async def test_the_received_text_is_clipped_to_200_characters(self) -> None:
        response = await answer(reply("", [wire_call("c", "t", "{" + "x" * 500)]))

        (preview,) = response.tool_calls[0].arguments.values()
        assert len(preview) == 200

    async def test_only_the_unreadable_call_among_valid_ones_carries_the_marker(self) -> None:
        calls = [
            wire_call("a", "t", {"k": 1}),
            wire_call("b", "t", "{roto"),
            wire_call("c", "t", {"k": 3}),
        ]

        response = await answer(reply("", calls))

        assert [call.id for call in response.tool_calls] == ["a", "b", "c"]
        assert [call.arguments for call in response.tool_calls] == [
            {"k": 1},
            {MARKER: "{roto"},
            {"k": 3},
        ]


class TestAToolThatAcceptsFreeFormFields:
    async def test_unreadable_arguments_fail_closed_without_the_received_text(self) -> None:
        raw = "{roto " + SENTINEL

        with pytest.raises(ProviderError) as raised:
            await answer(reply("", [wire_call("c", "libre", raw)]), [FREE_FORM])

        assert "libre" in str(raised.value)
        assert SENTINEL not in str(raised.value)

    async def test_readable_arguments_pass_for_the_same_tool(self) -> None:
        response = await answer(reply("", [wire_call("c", "libre", {"a": 1})]), [FREE_FORM])

        assert response.tool_calls[0].arguments == {"a": 1}

    async def test_a_strict_tool_gets_the_marker_instead(self) -> None:
        response = await answer(reply("", [wire_call("c", "estricta", "{roto")]), [STRICT])

        assert response.tool_calls[0].arguments == {MARKER: "{roto"}

    async def test_a_name_that_is_not_declared_gets_the_marker(self) -> None:
        response = await answer(reply("", [wire_call("c", "otra", "{roto")]), [FREE_FORM])

        assert response.tool_calls[0].arguments == {MARKER: "{roto"}

    async def test_a_name_that_is_not_text_is_an_unusable_answer(self) -> None:
        raw = {"id": "c", "function": {"name": ["x"], "arguments": "{roto"}}

        with pytest.raises(ProviderError):
            await answer(reply("", [raw]), [FREE_FORM])


class TestAnUnusableAnswer:
    @pytest.mark.parametrize(
        "outcome",
        [
            {},
            {"choices": []},
            {"choices": "no es una lista"},
            {"choices": [5]},
            {"choices": [{"message": "no es un dict"}]},
            reply(""),
            reply(None),
            reply("", []),
            {"choices": [{"message": {"content": 123}}]},
            reply("x", [{"id": "", "function": {"name": SENTINEL, "arguments": "{}"}}]),
            reply("x", [{"id": "c", "function": {"name": "", "arguments": "{}"}}]),
            reply("x", [{"id": "c"}]),
            {"choices": [{"message": {"content": "x", "tool_calls": "no es una lista"}}]},
            reply("x", usage={"prompt_tokens": -1, "completion_tokens": 1}),
            "texto",
            5,
            None,
            [],
        ],
        ids=lambda value: type(value).__name__ + ":" + str(value)[:40],
    )
    async def test_it_fails_as_a_provider_error_with_a_fixed_message(self, outcome: Any) -> None:
        with pytest.raises(ProviderError) as raised:
            await answer(outcome)

        assert type(raised.value) is ProviderError
        assert SENTINEL not in str(raised.value)
        assert str(raised.value)


class TestComplete:
    async def test_it_calls_the_function_once_with_the_built_request(self) -> None:
        provider, completion = make_provider(reply("hola"))
        tools = [STRICT]

        await provider.complete(list(USER), tools)

        assert completion.calls == [provider.build_request(USER, tools)]

    async def test_it_modifies_neither_the_messages_nor_the_tools(self) -> None:
        provider, _ = make_provider(reply("hola"))
        messages = list(USER)
        tools = [STRICT]
        before = (copy.deepcopy(messages), copy.deepcopy(tools))

        await provider.complete(messages, tools)

        assert (messages, tools) == before

    async def test_the_answer_of_the_function_is_not_modified(self) -> None:
        outcome = reply("", [wire_call("c", "t", "{roto")])
        before = copy.deepcopy(outcome)

        await answer(outcome)

        assert outcome == before

    async def test_each_call_is_independent(self) -> None:
        provider, completion = make_provider(reply("uno"), reply("dos"))

        first = await provider.complete(list(USER))
        second = await provider.complete(list(USER))

        assert (first.content, second.content) == ("uno", "dos")
        assert len(completion.calls) == 2
