"""T024: payload-only restoration functions are deprecated in favor of ``restore_messages``."""

from __future__ import annotations

import warnings

import pytest

from harness_agent.adapters.converters import (
    ConversionError,
    from_anthropic_payload,
    from_openai_messages,
)
from harness_agent.core.entities import Message, Role


def test_from_openai_messages_warns_and_keeps_its_behavior() -> None:
    with pytest.warns(DeprecationWarning, match="restore_messages"):
        result = from_openai_messages([{"role": "user", "content": "hi"}])
    assert result == [Message(Role.USER, "hi")]


def test_from_anthropic_payload_warns_and_keeps_its_behavior() -> None:
    with pytest.warns(DeprecationWarning, match="restore_messages"):
        result = from_anthropic_payload({"messages": [{"role": "user", "content": "hi"}]})
    assert result == [Message(Role.USER, "hi")]


def test_deprecated_functions_still_fail_closed() -> None:
    with pytest.warns(DeprecationWarning), pytest.raises(ConversionError):
        from_openai_messages([{"role": "bogus", "content": "x"}])
    with pytest.warns(DeprecationWarning), pytest.raises(ConversionError):
        from_anthropic_payload({"messages": [{"role": "system", "content": "x"}]})


def test_warning_points_to_the_caller() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from_openai_messages([])
    assert caught
    assert caught[0].filename == __file__


def test_response_parsers_are_not_deprecated() -> None:
    from harness_agent.adapters.converters import from_openai_response

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        from_openai_response({"choices": [{"message": {"role": "assistant", "content": "x"}}]})
