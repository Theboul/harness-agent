"""``FailoverProvider``: switch to the next model after an eligible failure (HU-07-05 / T003).

The inner provider is a double that plays a script *per model* and asks the switch which model is
active when it is called, so the tests see what a real ``ModelSwitch`` would do: the repeated call
goes to the new model. Nothing waits, nothing leaves the machine.
"""

from __future__ import annotations

import asyncio

import pytest

from harness_agent.adapters.providers.errors import FailoverExhausted, RateLimited
from harness_agent.adapters.providers.failover_provider import FailoverProvider, Switched
from harness_agent.adapters.providers.model_switch import (
    DEFAULT_ALIAS,
    ModelUnavailable,
    UnknownModelAlias,
)
from harness_agent.core import (
    Message,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    Role,
    ToolDefinition,
)
from tests.doubles import FakeProvider

SENTINEL = "VALOR-DE-PRUEBA-123"
DEFAULT_MODEL = "openai/base"
MODELS = {"uno": "gemini/uno", "dos": "groq/dos", "tres": "ollama/tres"}
USER = [Message(Role.USER, "haz algo")]
TOOLS = [ToolDefinition("herramienta", "Hace algo.", {"type": "object", "properties": {}})]
OK = ProviderResponse(content="listo")


class FakeSwitch:
    """The surface of ``ModelSwitch`` that the failover uses, recording every ``select``."""

    def __init__(
        self, unavailable: set[str] | None = None, unknown: set[str] | None = None
    ) -> None:
        self.alias: str | None = None
        self.model = DEFAULT_MODEL
        self.selected: list[str] = []
        self._unavailable = unavailable or set()
        self._unknown = unknown or set()

    def select(self, name: str) -> str:
        self.selected.append(name)
        if name in self._unavailable:
            raise ModelUnavailable("missing_key", "VARIABLE_DE_PRUEBA")
        if name in self._unknown:
            raise UnknownModelAlias(name)
        if name == DEFAULT_ALIAS:
            self.alias, self.model = None, DEFAULT_MODEL
        else:
            self.alias, self.model = name, MODELS[name]
        return self.model


class PerModel(Provider):
    """Plays the script of the active model of the switch and remembers every call."""

    def __init__(self, switch: FakeSwitch, scripts: dict[str, FakeProvider]) -> None:
        self._switch = switch
        self._scripts = scripts
        self.calls: list[tuple[str, list[Message], list[ToolDefinition] | None]] = []

    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        self.calls.append((self._switch.model, messages, tools))
        return await self._scripts[self._switch.model].complete(messages, tools)

    @property
    def models_called(self) -> list[str]:
        return [model for model, _, _ in self.calls]


def script(*steps: ProviderResponse | ProviderError) -> FakeProvider:
    return FakeProvider(list(steps))


class Seen:
    def __init__(self) -> None:
        self.switches: list[Switched] = []
        self.warnings: list[str] = []

    def observe(self, change: Switched) -> None:
        self.switches.append(change)

    def warn(self, text: str) -> None:
        self.warnings.append(text)


def build(
    scripts: dict[str, FakeProvider],
    aliases: tuple[str, ...] = ("uno", "dos"),
    *,
    switch: FakeSwitch | None = None,
    seen: Seen | None = None,
) -> tuple[FailoverProvider, PerModel, FakeSwitch, Seen]:
    chosen = switch if switch is not None else FakeSwitch()
    watcher = seen if seen is not None else Seen()
    inner = PerModel(chosen, scripts)
    provider = FailoverProvider(inner, chosen, aliases, observer=watcher.observe, warn=watcher.warn)
    return provider, inner, chosen, watcher


def default_failing(error: ProviderError, then: ProviderResponse = OK) -> dict[str, FakeProvider]:
    return {
        DEFAULT_MODEL: script(error),
        MODELS["uno"]: script(then),
        MODELS["dos"]: script(OK),
        MODELS["tres"]: script(OK),
    }


# --- success and the switch ---------------------------------------------------------------------


async def test_a_good_answer_passes_through_and_touches_nothing() -> None:
    provider, inner, switch, seen = build({DEFAULT_MODEL: script(OK)})

    response = await provider.complete(USER, TOOLS)

    assert response.content == "listo"
    assert inner.models_called == [DEFAULT_MODEL]
    assert switch.selected == []
    assert seen.switches == [] and seen.warnings == []


async def test_an_eligible_error_switches_and_repeats_the_same_call() -> None:
    provider, inner, switch, seen = build(default_failing(ProviderTimeout(SENTINEL)))

    response = await provider.complete(USER, TOOLS)

    assert response.content == "listo"
    assert switch.selected == ["uno"]
    assert inner.models_called == [DEFAULT_MODEL, MODELS["uno"]]
    (_, first_messages, first_tools), (_, second_messages, second_tools) = inner.calls
    assert first_messages == second_messages == USER
    assert first_tools == second_tools == TOOLS
    assert seen.switches == [Switched(DEFAULT_MODEL, MODELS["uno"], "ProviderTimeout")]


@pytest.mark.parametrize(
    "error",
    [
        QuotaExceeded(SENTINEL),
        RateLimited(SENTINEL),
        ProviderTimeout(SENTINEL),
        ProviderUnavailable(SENTINEL),
    ],
    ids=["quota", "rate-limit", "timeout", "unavailable"],
)
async def test_each_eligible_kind_switches(error: ProviderError) -> None:
    provider, inner, switch, seen = build(default_failing(error))

    response = await provider.complete(USER)

    assert response.content == "listo"
    assert switch.selected == ["uno"]
    assert seen.switches[0].error_type == type(error).__name__


class _Boom(Provider):
    """An inner provider that raises what it was given, as it is."""

    def __init__(self, error: BaseException) -> None:
        self._error = error
        self.calls = 0

    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        self.calls += 1
        raise self._error


@pytest.mark.parametrize(
    "error",
    [
        ProviderError(SENTINEL),
        FailoverExhausted(),
        ValueError(SENTINEL),
        asyncio.CancelledError(),
        KeyboardInterrupt(),
    ],
    ids=["generic-provider", "exhausted", "unknown", "cancelled", "interrupt"],
)
async def test_what_is_not_eligible_is_the_same_object_and_never_selects(
    error: BaseException,
) -> None:
    switch = FakeSwitch()
    inner = _Boom(error)
    provider = FailoverProvider(inner, switch, ("uno", "dos"))

    with pytest.raises(type(error)) as raised:
        await provider.complete(USER)

    assert raised.value is error
    assert switch.selected == []
    assert inner.calls == 1


# --- the order, the turn and the end of the list -----------------------------------------------


async def test_two_failures_in_a_row_walk_the_list_in_its_order() -> None:
    scripts = {
        DEFAULT_MODEL: script(ProviderTimeout(SENTINEL)),
        MODELS["uno"]: script(QuotaExceeded(SENTINEL)),
        MODELS["dos"]: script(OK),
    }
    provider, inner, switch, seen = build(scripts)

    response = await provider.complete(USER)

    assert response.content == "listo"
    assert switch.selected == ["uno", "dos"]
    assert inner.models_called == [DEFAULT_MODEL, MODELS["uno"], MODELS["dos"]]
    assert [(s.from_model, s.to_model) for s in seen.switches] == [
        (DEFAULT_MODEL, MODELS["uno"]),
        (MODELS["uno"], MODELS["dos"]),
    ]


async def test_when_the_list_runs_out_the_error_is_fixed_and_each_model_was_called_once() -> None:
    scripts = {
        DEFAULT_MODEL: script(ProviderTimeout(SENTINEL)),
        MODELS["uno"]: script(QuotaExceeded(SENTINEL)),
        MODELS["dos"]: script(ProviderUnavailable(SENTINEL)),
    }
    provider, inner, switch, seen = build(scripts)

    with pytest.raises(FailoverExhausted) as raised:
        await provider.complete(USER)

    assert inner.models_called == [DEFAULT_MODEL, MODELS["uno"], MODELS["dos"]]  # once each
    assert switch.selected == ["uno", "dos"]  # and it did not go back to the first
    text = str(raised.value)
    assert text and SENTINEL not in text
    assert raised.value.__cause__ is None and raised.value.__context__ is None
    assert SENTINEL not in repr(raised.value)
    assert isinstance(raised.value, ProviderError)


async def test_a_second_call_after_the_end_of_the_list_does_not_try_anyone_again() -> None:
    scripts = {
        DEFAULT_MODEL: script(ProviderTimeout(SENTINEL)),
        MODELS["uno"]: script(ProviderTimeout(SENTINEL), ProviderTimeout(SENTINEL)),
    }
    provider, inner, switch, _ = build(scripts, ("uno",))
    with pytest.raises(FailoverExhausted):
        await provider.complete(USER)

    with pytest.raises(FailoverExhausted):  # same turn: nobody is left
        await provider.complete(USER)

    assert inner.models_called == [DEFAULT_MODEL, MODELS["uno"], MODELS["uno"]]
    assert switch.selected == ["uno"]


async def test_an_empty_list_exhausts_at_the_first_eligible_failure() -> None:
    provider, inner, switch, seen = build({DEFAULT_MODEL: script(ProviderTimeout(SENTINEL))}, ())

    with pytest.raises(FailoverExhausted):
        await provider.complete(USER)

    assert inner.models_called == [DEFAULT_MODEL]
    assert switch.selected == [] and seen.switches == []


async def test_the_alias_that_is_active_at_the_start_counts_as_tried() -> None:
    switch = FakeSwitch()
    switch.select("dos")  # the person chose it with /model, before the request
    switch.selected.clear()
    scripts = {
        MODELS["dos"]: script(ProviderTimeout(SENTINEL)),
        DEFAULT_MODEL: script(OK),
    }
    provider, inner, _, seen = build(scripts, ("uno", "dos"), switch=switch)
    scripts[MODELS["uno"]] = script(OK)

    response = await provider.complete(USER)

    assert response.content == "listo"
    assert switch.selected == [DEFAULT_ALIAS]  # the default is the first of the list
    assert inner.models_called == [MODELS["dos"], DEFAULT_MODEL]
    assert seen.switches == [Switched(MODELS["dos"], DEFAULT_MODEL, "ProviderTimeout")]


async def test_an_active_model_that_is_not_in_the_list_is_tried_once_and_the_list_goes_on() -> None:
    switch = FakeSwitch()
    switch.select("tres")  # /plan with an alias outside the failover list
    switch.selected.clear()
    scripts = {
        MODELS["tres"]: script(QuotaExceeded(SENTINEL)),
        DEFAULT_MODEL: script(OK),
    }
    provider, inner, _, _ = build(scripts, ("uno", "dos"), switch=switch)

    await provider.complete(USER)

    assert switch.selected == [DEFAULT_ALIAS]
    assert inner.models_called == [MODELS["tres"], DEFAULT_MODEL]


# --- models that cannot be built ---------------------------------------------------------------


async def test_a_model_that_cannot_be_built_is_skipped_with_a_fixed_line() -> None:
    switch = FakeSwitch(unavailable={"uno"})
    scripts = default_failing(ProviderTimeout(SENTINEL))
    provider, inner, _, seen = build(scripts, switch=switch)

    response = await provider.complete(USER)

    assert response.content == "listo"
    assert switch.selected == ["uno", "dos"]
    assert inner.models_called == [DEFAULT_MODEL, MODELS["dos"]]
    assert len(seen.warnings) == 1
    assert "uno" in seen.warnings[0]
    assert SENTINEL not in seen.warnings[0] and "VARIABLE_DE_PRUEBA" not in seen.warnings[0]
    assert seen.switches == [Switched(DEFAULT_MODEL, MODELS["dos"], "ProviderTimeout")]


async def test_an_unknown_alias_is_skipped_like_a_model_that_cannot_be_built() -> None:
    switch = FakeSwitch(unknown={"uno"})
    provider, inner, _, seen = build(default_failing(ProviderTimeout(SENTINEL)), switch=switch)

    await provider.complete(USER)

    assert inner.models_called == [DEFAULT_MODEL, MODELS["dos"]]
    assert len(seen.warnings) == 1


async def test_when_every_model_fails_to_build_the_list_is_exhausted() -> None:
    switch = FakeSwitch(unavailable={"uno", "dos"})
    scripts = {DEFAULT_MODEL: script(ProviderTimeout(SENTINEL))}
    provider, inner, _, seen = build(scripts, switch=switch)

    with pytest.raises(FailoverExhausted):
        await provider.complete(USER)

    assert inner.models_called == [DEFAULT_MODEL]
    assert switch.selected == ["uno", "dos"]
    assert len(seen.warnings) == 2 and seen.switches == []


async def test_a_skipped_model_is_not_tried_again_in_the_same_turn() -> None:
    switch = FakeSwitch(unavailable={"uno"})
    scripts = {
        DEFAULT_MODEL: script(ProviderTimeout(SENTINEL)),
        MODELS["dos"]: script(ProviderTimeout(SENTINEL)),
    }
    provider, _, _, _ = build(scripts, switch=switch)

    with pytest.raises(FailoverExhausted):
        await provider.complete(USER)

    assert switch.selected == ["uno", "dos"]  # "uno" was asked for once, not twice


async def test_the_failover_works_without_an_observer_and_without_a_warning_sink() -> None:
    switch = FakeSwitch(unavailable={"uno"})
    inner = PerModel(switch, default_failing(ProviderTimeout(SENTINEL)))
    provider = FailoverProvider(inner, switch, ("uno", "dos"))

    response = await provider.complete(USER)

    assert response.content == "listo"


# --- the observer ------------------------------------------------------------------------------


async def test_an_observer_that_fails_does_not_change_the_result() -> None:
    switch = FakeSwitch()
    inner = PerModel(switch, default_failing(ProviderTimeout(SENTINEL)))

    def broken(change: Switched) -> None:
        raise RuntimeError(SENTINEL)

    provider = FailoverProvider(inner, switch, ("uno", "dos"), observer=broken)

    response = await provider.complete(USER)

    assert response.content == "listo"
    assert switch.selected == ["uno"]


async def test_the_switched_record_carries_names_and_never_the_text_of_the_error() -> None:
    provider, _, _, seen = build(default_failing(QuotaExceeded(SENTINEL)))

    await provider.complete(USER)

    (change,) = seen.switches
    assert SENTINEL not in repr(change)
    assert change.error_type == "QuotaExceeded"


# --- the turns ---------------------------------------------------------------------------------


async def test_begin_turn_forgets_what_was_tried() -> None:
    scripts = {
        DEFAULT_MODEL: script(ProviderTimeout(SENTINEL), ProviderTimeout(SENTINEL)),
        MODELS["uno"]: script(ProviderTimeout(SENTINEL), OK),
    }
    provider, inner, switch, _ = build(scripts, ("uno",))
    with pytest.raises(FailoverExhausted):
        await provider.complete(USER)

    provider.begin_turn()
    switch.select(DEFAULT_ALIAS)  # the person went back with /model predeterminado
    switch.selected.clear()
    response = await provider.complete(USER)  # the default fails, "uno" is tried again

    assert response.content == "listo"
    assert inner.models_called == [DEFAULT_MODEL, MODELS["uno"], DEFAULT_MODEL, MODELS["uno"]]
    assert switch.selected == ["uno"]


async def test_without_begin_turn_the_tried_models_last_as_long_as_the_wrapper() -> None:
    scripts = {
        DEFAULT_MODEL: script(ProviderTimeout(SENTINEL), ProviderTimeout(SENTINEL)),
        MODELS["uno"]: script(ProviderTimeout(SENTINEL), OK),
    }
    provider, inner, switch, _ = build(scripts, ("uno",))
    with pytest.raises(FailoverExhausted):
        await provider.complete(USER)

    switch.select(DEFAULT_ALIAS)
    switch.selected.clear()
    with pytest.raises(FailoverExhausted):  # the list is not reset: no loop is possible
        await provider.complete(USER)

    assert switch.selected == []


async def test_the_active_model_is_read_from_the_switch_at_every_turn_not_cached() -> None:
    scripts = {
        DEFAULT_MODEL: script(OK, ProviderTimeout(SENTINEL)),
        MODELS["uno"]: script(OK),
        MODELS["dos"]: script(OK),
    }
    provider, inner, switch, _ = build(scripts, ("uno", "dos"))
    provider.begin_turn()
    await provider.complete(USER)  # the default answers

    switch.select("uno")  # /model uno between two requests
    provider.begin_turn()
    scripts[MODELS["uno"]] = script(ProviderTimeout(SENTINEL))
    scripts[DEFAULT_MODEL] = script(OK)
    response = await provider.complete(USER)  # "uno" fails: the first untried is the default

    assert response.content == "listo"
    assert inner.models_called[-2:] == [MODELS["uno"], DEFAULT_MODEL]


async def test_the_list_is_the_default_first_then_the_aliases_in_their_order() -> None:
    scripts = {
        DEFAULT_MODEL: script(ProviderTimeout(SENTINEL)),
        MODELS["tres"]: script(ProviderTimeout(SENTINEL)),
        MODELS["uno"]: script(OK),
    }
    provider, _, switch, _ = build(scripts, ("tres", "uno"))

    await provider.complete(USER)

    assert switch.selected == ["tres", "uno"]


# --- the error --------------------------------------------------------------------------------


def test_the_exhausted_error_is_a_provider_error_with_a_fixed_text_in_spanish() -> None:
    error = FailoverExhausted()

    assert isinstance(error, ProviderError)
    assert not isinstance(error, (QuotaExceeded, ProviderTimeout, ProviderUnavailable))
    assert "modelos" in str(error)
    assert str(FailoverExhausted()) == str(error)
