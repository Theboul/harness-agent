"""Tests of the switchable provider (HU-06-06 / T002 / FR-003).

``ModelSwitch`` is a ``Provider`` that delegates to the active one; ``select`` builds (once) the
provider of an alias with an injected function and never copies the text of a failure.
"""

from __future__ import annotations

import pytest

from harness_agent.adapters.providers.model_switch import (
    DEFAULT_ALIAS,
    ModelSwitch,
    ModelUnavailable,
    UnknownModelAlias,
)
from harness_agent.core import Message, Provider, ProviderResponse, Role
from tests.doubles import FakeProvider

MESSAGES = [Message(role=Role.USER, content="hi")]
SENTINEL = "VALOR-DE-PRUEBA-123"


def answer(text: str) -> FakeProvider:
    return FakeProvider([ProviderResponse(content=text)] * 5)


class Builder:
    def __init__(self, failure: Exception | None = None) -> None:
        self.built: list[str] = []
        self.failure = failure

    def __call__(self, alias: str) -> Provider:
        self.built.append(alias)
        if self.failure is not None:
            raise self.failure
        return answer(f"from {alias}")


def make(builder: Builder | None = None) -> tuple[ModelSwitch, Builder]:
    chosen = builder if builder is not None else Builder()
    switch = ModelSwitch(
        "groq/base", answer("from default"), {"plan": "gemini/p", "build": "groq/b"}, chosen
    )
    return switch, chosen


class TestState:
    def test_starts_on_the_default_model(self) -> None:
        switch, _ = make()
        assert (switch.model, switch.alias) == ("groq/base", None)

    def test_lists_the_aliases_in_order(self) -> None:
        switch, _ = make()
        assert switch.aliases == (("plan", "gemini/p"), ("build", "groq/b"))

    def test_knows_which_aliases_exist(self) -> None:
        switch, _ = make()
        assert switch.has("plan") and not switch.has("other")
        assert not switch.has(DEFAULT_ALIAS)


class TestSelect:
    async def test_delegates_to_the_default_at_first(self) -> None:
        switch, _ = make()
        assert (await switch.complete(MESSAGES)).content == "from default"

    async def test_select_switches_the_provider_and_the_model(self) -> None:
        switch, builder = make()
        assert switch.select("plan") == "gemini/p"
        assert (switch.model, switch.alias) == ("gemini/p", "plan")
        assert (await switch.complete(MESSAGES)).content == "from plan"
        assert builder.built == ["plan"]

    async def test_the_name_is_matched_ignoring_case_and_spaces(self) -> None:
        switch, _ = make()
        switch.select("  PLAN ")
        assert switch.alias == "plan"

    async def test_a_provider_is_built_once(self) -> None:
        switch, builder = make()
        switch.select("plan")
        switch.select("build")
        switch.select("plan")
        assert builder.built == ["plan", "build"]

    async def test_the_default_word_goes_back_without_building(self) -> None:
        switch, builder = make()
        switch.select("plan")
        assert switch.select(DEFAULT_ALIAS) == "groq/base"
        assert (switch.model, switch.alias) == ("groq/base", None)
        assert (await switch.complete(MESSAGES)).content == "from default"
        assert builder.built == ["plan"]

    def test_an_unknown_alias_changes_nothing(self) -> None:
        switch, _ = make()
        switch.select("plan")
        with pytest.raises(UnknownModelAlias):
            switch.select("nope")
        assert switch.alias == "plan"

    @pytest.mark.parametrize(
        "failure", [ModelUnavailable("missing_key", "GEMINI_API_KEY"), RuntimeError(SENTINEL)]
    )
    def test_a_failing_build_changes_nothing_and_is_retried_later(self, failure: Exception) -> None:
        builder = Builder(failure)
        switch, _ = make(builder)
        with pytest.raises(ModelUnavailable) as caught:
            switch.select("plan")
        assert (switch.model, switch.alias) == ("groq/base", None)
        assert SENTINEL not in str(caught.value) and SENTINEL not in repr(caught.value)
        assert caught.value.code == (
            "missing_key" if isinstance(failure, ModelUnavailable) else "failed"
        )
        with pytest.raises(ModelUnavailable):
            switch.select("plan")
        assert builder.built == ["plan", "plan"]

    def test_the_missing_key_error_names_the_variable(self) -> None:
        error = ModelUnavailable("missing_key", "GEMINI_API_KEY")
        assert error.variable == "GEMINI_API_KEY"
        assert ModelUnavailable("failed").variable is None
