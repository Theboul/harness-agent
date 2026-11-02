"""The opt-in debug detail of a failed provider call (HU-06-07 / FR-001).

With a ``debug`` function injected, the adapter hands it the text of the original exception, cleaned
of the key and capped. Without it nothing changes: the canonical message never copies the text.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from harness_agent.adapters.providers.litellm_provider import (
    DEBUG_MAX_CHARS,
    LiteLLMProvider,
)
from harness_agent.config import Secret
from harness_agent.core import Message, ProviderError, Role
from tests.unit.adapters.providers.support import (
    MAX_OUTPUT_TOKENS,
    MODEL,
    SENTINEL,
    RecordingCompletion,
)

USER = [Message(Role.USER, "haz algo")]


def provider_with(
    error: BaseException, debug: object, key: Secret | None = None
) -> LiteLLMProvider:
    return LiteLLMProvider(
        MODEL,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        api_key=key,
        completion=RecordingCompletion(error),
        debug=debug,  # type: ignore[arg-type]
    )


async def test_the_detail_reaches_the_debug_function_without_the_key() -> None:
    seen: list[str] = []
    error = RuntimeError(f"400 bad request, key {SENTINEL} was sent")

    with pytest.raises(ProviderError) as raised:
        await provider_with(error, seen.append, Secret(SENTINEL)).complete(list(USER))

    assert len(seen) == 1
    assert "400 bad request" in seen[0]
    assert SENTINEL not in seen[0]
    assert SENTINEL not in str(raised.value)


async def test_the_detail_is_capped() -> None:
    seen: list[str] = []

    with pytest.raises(ProviderError):
        await provider_with(RuntimeError("x" * 10_000), seen.append).complete(list(USER))

    assert len(seen[0]) == DEBUG_MAX_CHARS


async def test_the_canonical_message_does_not_copy_the_text_with_or_without_debug() -> None:
    texts = []
    collected: list[str] = []
    sinks: list[Callable[[str], None] | None] = [None, collected.append]
    for debug in sinks:
        with pytest.raises(ProviderError) as raised:
            await provider_with(RuntimeError("TEXTO-ORIGINAL"), debug).complete(list(USER))
        texts.append(str(raised.value))

    assert texts[0] == texts[1]
    assert "TEXTO-ORIGINAL" not in texts[0]


async def test_a_debug_function_that_fails_does_not_change_the_error() -> None:
    def broken(text: str) -> None:
        raise OSError("closed stream")

    with pytest.raises(ProviderError) as raised:
        await provider_with(RuntimeError("fallo"), broken).complete(list(USER))

    assert "OSError" not in str(raised.value)


async def test_a_canonical_error_raised_by_the_completion_is_not_reported() -> None:
    seen: list[str] = []

    with pytest.raises(ProviderError):
        await provider_with(ProviderError("ya canónico"), seen.append).complete(list(USER))

    assert seen == []
