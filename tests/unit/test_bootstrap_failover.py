"""The composition root wires the failover between models (HU-07-05 / T006).

The provider factory is a recording double that returns a ``FakeProvider`` per model: no network,
key or console. The retries are turned down to one attempt so the failures reach the failover.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from harness_agent.adapters.providers.failover_provider import FailoverProvider
from harness_agent.adapters.providers.retrying_provider import RetryingProvider
from harness_agent.bootstrap import Composition, compose, run_session
from harness_agent.config import HarnessConfig, ModelAlias, Retries, Secret
from harness_agent.core import (
    Event,
    EventType,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    QuotaExceeded,
)
from harness_agent.core.loop import TurnStatus
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import SENTINEL, make_config

DEFAULT = "openai/modelo-de-prueba"
UNO = "gemini/modelo-uno"
DOS = "groq/modelo-dos"
KEY_VALUE = "valor-de-clave-de-prueba-uno"
UNO_ALIAS = ModelAlias("uno", UNO, Secret(KEY_VALUE), "GEMINI_API_KEY")
DOS_ALIAS = ModelAlias("dos", DOS, Secret("valor-de-clave-de-prueba-dos"), "GROQ_API_KEY")
NO_KEY_ALIAS = ModelAlias("sinclave", "gemini/modelo-sin-clave", None, "GEMINI_API_KEY")


def reply(model: str) -> ProviderResponse:
    return ProviderResponse(content=f"de {model}")


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class Factory:
    """Builds one ``FakeProvider`` per model from a script per model."""

    def __init__(self, scripts: dict[str, list[ProviderResponse | ProviderError]]) -> None:
        self.scripts = scripts
        self.built: list[str] = []
        self.providers: dict[str, FakeProvider] = {}

    def __call__(self, config: HarnessConfig) -> Provider:
        self.built.append(config.model)
        provider = FakeProvider(self.scripts.get(config.model, [reply(config.model)] * 4))
        self.providers[config.model] = provider
        return provider


def config_with(
    tmp_path: Path, *aliases: ModelAlias, failover: tuple[str, ...] = ()
) -> HarnessConfig:
    folder = tmp_path / "trabajo"
    folder.mkdir(exist_ok=True)
    base = make_config(tmp_path, workspace=folder, model=DEFAULT)
    return replace(base, models=aliases, failover=failover, retries=Retries(max_attempts=1))


def open_with(opened: list[Composition], config: HarnessConfig, factory: Factory) -> Composition:
    composition = compose(config, provider_factory=factory, system_name="Linux")
    opened.append(composition)
    return composition


def listen(composition: Composition) -> list[Event]:
    seen: list[Event] = []
    composition.bus.subscribe(EventType.PROVIDER_SWITCHED, seen.append)
    return seen


async def drive(composition: Composition, *lines: str) -> str:
    output = io.StringIO()
    await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
        output=output,
    )
    return output.getvalue()


# --- off by default ----------------------------------------------------------------------------


async def test_by_default_there_is_no_failover(tmp_path: Path, opened: list[Composition]) -> None:
    factory = Factory({})
    composition = open_with(opened, config_with(tmp_path, UNO_ALIAS), factory)

    assert composition.failover is None
    assert isinstance(composition.loop._provider, RetryingProvider)
    assert composition.notices == ()


async def test_an_empty_list_changes_nothing(tmp_path: Path, opened: list[Composition]) -> None:
    config = config_with(tmp_path, UNO_ALIAS, failover=())
    composition = open_with(opened, config, Factory({DEFAULT: [ProviderTimeout(SENTINEL)]}))
    seen = listen(composition)

    result = await composition.loop.run_turn(
        session_id=composition.session_id, task="x", history=[]
    )

    assert result.status is TurnStatus.PROVIDER_FAILED
    assert seen == []


# --- the wrapper -------------------------------------------------------------------------------


async def test_the_wrapper_is_the_provider_of_the_loop_and_sits_outside_the_retries(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = config_with(tmp_path, UNO_ALIAS, failover=("uno",))
    composition = open_with(opened, config, Factory({}))

    assert isinstance(composition.failover, FailoverProvider)
    assert composition.loop._provider is composition.failover
    assert isinstance(composition.failover.inner, RetryingProvider)


async def test_the_switch_is_an_event_of_the_active_session_with_names_only(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = config_with(tmp_path, UNO_ALIAS, failover=("uno",))
    factory = Factory({DEFAULT: [ProviderTimeout(f"texto {SENTINEL}")]})
    composition = open_with(opened, config, factory)
    seen = listen(composition)

    result = await composition.loop.run_turn(
        session_id=composition.session_id, task="x", history=[]
    )

    assert result.status is TurnStatus.COMPLETED
    assert result.final_response == f"de {UNO}"
    (event,) = seen
    assert event.session_id == composition.session_id
    assert dict(event.payload) == {
        "from_model": DEFAULT,
        "to_model": UNO,
        "reason": "ProviderTimeout",
    }
    assert SENTINEL not in repr(event.payload)


async def test_the_event_is_saved_with_the_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = config_with(tmp_path, UNO_ALIAS, failover=("uno",))
    composition = open_with(opened, config, Factory({DEFAULT: [QuotaExceeded(SENTINEL)]}))

    await composition.loop.run_turn(session_id=composition.session_id, task="x", history=[])

    rows = (
        composition.store.connection()
        .execute("SELECT session_id, type FROM events WHERE type = 'provider_switched'")
        .fetchall()
    )
    assert [tuple(row) for row in rows] == [(composition.session_id, "provider_switched")]


async def test_the_switch_is_shown_on_the_screen_with_a_fixed_line(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = config_with(tmp_path, UNO_ALIAS, failover=("uno",))
    factory = Factory({DEFAULT: [ProviderTimeout(f"texto {SENTINEL}")]})
    composition = open_with(opened, config, factory)

    shown = await drive(composition, "hola")

    line = f"Cambio de modelo por fallo: {DEFAULT} a {UNO} (ProviderTimeout)."
    assert line in shown.replace("tarea> ", "").splitlines()
    assert SENTINEL not in shown


async def test_the_event_follows_the_active_session_after_new(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = config_with(tmp_path, UNO_ALIAS, failover=("uno",))
    factory = Factory({DEFAULT: [ProviderTimeout("a")]})
    composition = open_with(opened, config, factory)
    seen = listen(composition)

    await drive(composition, "/nueva", "hola")

    (event,) = seen
    assert event.session_id != composition.session_id
    assert composition.session_cursor is not None
    assert event.session_id == composition.session_cursor.value


# --- begin_turn --------------------------------------------------------------------------------


async def test_every_request_starts_a_new_list(tmp_path: Path, opened: list[Composition]) -> None:
    config = config_with(tmp_path, UNO_ALIAS, failover=("uno",))
    factory = Factory(
        {
            DEFAULT: [ProviderTimeout("a"), reply(DEFAULT)],
            UNO: [ProviderTimeout("b"), ProviderTimeout("c")],
        }
    )
    composition = open_with(opened, config, factory)

    shown = await drive(composition, "primera", "segunda")

    # First request: the default fails, "uno" fails, nobody is left. Second request: "uno" is the
    # active one and fails, and the default - tried in the first request - is tried again.
    assert "FailoverExhausted" in shown
    assert f"de {DEFAULT}" in shown
    assert factory.providers[DEFAULT].call_count == 2
    assert factory.providers[UNO].call_count == 2


async def test_the_manual_compaction_also_starts_a_new_list(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = config_with(tmp_path, UNO_ALIAS, failover=("uno",))
    composition = open_with(opened, config, Factory({DEFAULT: [ProviderTimeout("a")]}))
    assert composition.failover is not None
    await composition.loop.run_turn(session_id=composition.session_id, task="x", history=[])
    assert composition.failover.tried == frozenset({"predeterminado", "uno"})

    await drive(composition, "/compactar")

    assert composition.failover.tried == frozenset()


# --- the active model --------------------------------------------------------------------------


async def test_the_model_stays_switched_and_the_view_shows_it(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = config_with(tmp_path, UNO_ALIAS, failover=("uno",))
    composition = open_with(opened, config, Factory({DEFAULT: [ProviderTimeout("a")]}))

    await composition.loop.run_turn(session_id=composition.session_id, task="x", history=[])

    assert composition.current_view is not None
    view = composition.current_view()
    assert view.model == UNO and view.active_alias == "uno"
    assert composition.model_switch is not None and composition.model_switch.model == UNO


# --- keys that are missing ---------------------------------------------------------------------


async def test_an_alias_without_its_key_is_left_out_with_a_fixed_notice(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = config_with(tmp_path, NO_KEY_ALIAS, UNO_ALIAS, failover=("sinclave", "uno"))
    factory = Factory({DEFAULT: [ProviderTimeout("a")]})
    composition = open_with(opened, config, factory)

    assert any(
        "sinclave" in notice and "GEMINI_API_KEY" in notice for notice in composition.notices
    )
    assert all(KEY_VALUE not in notice for notice in composition.notices)
    seen = listen(composition)

    result = await composition.loop.run_turn(
        session_id=composition.session_id, task="x", history=[]
    )

    assert result.status is TurnStatus.COMPLETED
    assert [event.payload["to_model"] for event in seen] == [UNO]


async def test_when_no_alias_is_usable_there_is_no_wrapper_but_there_is_a_notice(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = config_with(tmp_path, NO_KEY_ALIAS, failover=("sinclave",))
    composition = open_with(opened, config, Factory({}))

    assert composition.failover is None
    assert isinstance(composition.loop._provider, RetryingProvider)
    assert any("sinclave" in notice for notice in composition.notices)


async def test_the_notice_is_written_before_the_first_prompt(
    tmp_path: Path, opened: list[Composition]
) -> None:
    config = config_with(tmp_path, NO_KEY_ALIAS, UNO_ALIAS, failover=("sinclave", "uno"))
    composition = open_with(opened, config, Factory({}))

    shown = await drive(composition)

    assert "GEMINI_API_KEY" in shown and KEY_VALUE not in shown
