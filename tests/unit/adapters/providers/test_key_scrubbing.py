"""The key never leaves a text that the adapter builds (HU-07-02 / FR-015, US4).

Before the canonical error, or any other text, is built, the value of the key is replaced by a
marker. The original exception keeps its message in ``__cause__`` (it is the developer's view);
what the loop, the events and the model see is only what the adapter wrote.
"""

from __future__ import annotations

import pytest

from harness_agent.adapters.providers.errors import RateLimited
from harness_agent.config import Secret
from harness_agent.core import Message, ProviderError, Role, ToolDefinition
from tests.unit.adapters.providers.support import SENTINEL, make_provider, reply, wire_call

HIDDEN = "<secreto oculto>"
KEY = Secret(SENTINEL)
MARKER = "arguments_not_valid_json"
USER = [Message(Role.USER, "haz algo")]


def texts_of(error: BaseException) -> list[str]:
    """Every text a caller can get out of an error: str, repr, args and the attributes."""
    values = [str(error), repr(error), *(str(arg) for arg in error.args)]
    values.extend(str(value) for value in vars(error).values())
    return values


async def failure_with_key(error: BaseException) -> ProviderError:
    provider, _ = make_provider(error, api_key=KEY)
    with pytest.raises(ProviderError) as raised:
        await provider.complete(list(USER))
    return raised.value


class TestAnErrorThatRepeatsTheKey:
    async def test_the_message_of_the_exception_leaves_no_trace(self) -> None:
        original = RuntimeError(f"Incorrect API key provided: {SENTINEL}")

        error = await failure_with_key(original)

        for text in texts_of(error):
            assert SENTINEL not in text
        assert SENTINEL in str(error.__cause__)
        assert error.__cause__ is original

    async def test_the_name_of_the_class_is_cleaned_too(self) -> None:
        weird = type(SENTINEL, (RuntimeError,), {})

        error = await failure_with_key(weird("x"))

        for text in texts_of(error):
            assert SENTINEL not in text
        assert HIDDEN in str(error)

    async def test_a_listed_failure_keeps_its_type_and_still_hides_the_key(self) -> None:
        rate_limit = type("RateLimitError", (Exception,), {})
        weird = type(SENTINEL, (rate_limit,), {})

        error = await failure_with_key(weird(f"clave {SENTINEL}"))

        assert type(error) is RateLimited
        for text in texts_of(error):
            assert SENTINEL not in text

    async def test_a_key_that_is_part_of_the_message_is_hidden_wherever_it_appears(self) -> None:
        error = await failure_with_key(ValueError(f"{SENTINEL} {SENTINEL}"))

        for text in texts_of(error):
            assert SENTINEL not in text


class TestUnreadableArgumentsThatRepeatTheKey:
    async def test_the_text_kept_in_the_marker_is_cleaned(self) -> None:
        raw = "{roto " + SENTINEL
        provider, _ = make_provider(reply("", [wire_call("c", "t", raw)]), api_key=KEY)

        response = await provider.complete(list(USER))

        (preview,) = response.tool_calls[0].arguments.values()
        assert list(response.tool_calls[0].arguments) == [MARKER]
        assert SENTINEL not in preview
        assert HIDDEN in preview

    async def test_the_message_about_a_free_form_tool_is_cleaned_too(self) -> None:
        tool = ToolDefinition(SENTINEL, "d", {"type": "object", "additionalProperties": True})
        provider, _ = make_provider(reply("", [wire_call("c", SENTINEL, "{roto")]), api_key=KEY)

        with pytest.raises(ProviderError) as raised:
            await provider.complete(list(USER), [tool])

        for text in texts_of(raised.value):
            assert SENTINEL not in text

    async def test_without_a_key_the_received_text_is_kept(self) -> None:
        provider, _ = make_provider(reply("", [wire_call("c", "t", "{roto " + SENTINEL)]))

        response = await provider.complete(list(USER))

        assert SENTINEL in next(iter(response.tool_calls[0].arguments.values()))


class TestTheKeyIsNeverAnArtifactOfTheAdapter:
    async def test_the_representation_of_the_adapter_hides_it(self) -> None:
        provider, _ = make_provider(api_key=KEY)

        assert SENTINEL not in repr(provider)
        assert SENTINEL not in str(provider)

    async def test_an_empty_key_does_not_garble_the_messages(self) -> None:
        provider, _ = make_provider(RuntimeError("fallo"), api_key=Secret(""))

        with pytest.raises(ProviderError) as raised:
            await provider.complete(list(USER))

        assert str(raised.value) == "El proveedor devolvió un error (RuntimeError)."
