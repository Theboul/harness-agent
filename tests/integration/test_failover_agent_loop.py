"""The failover between models with the real composition, loop, retries and a real SQLite file.

HU-07-05 (spec 052): AC-01 (an eligible failure switches, repeats the call and is recorded and
shown), AC-02 (a failure that is not eligible reaches the person), AC-03 (every model is tried once
per request, no loop, a fixed error) and AC-04 (the threshold of the new model). The providers are
``FakeProvider`` doubles by model, or the real LiteLLM adapter over an injected completion function
(to prove the classification); nothing uses the network, a key or the console.
"""

from __future__ import annotations

import io
import json
import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.providers.errors import RateLimited
from harness_agent.adapters.providers.litellm_provider import LiteLLMProvider
from harness_agent.bootstrap import Composition, compose, run_session
from harness_agent.config import (
    HarnessConfig,
    ModelAlias,
    Retries,
    Secret,
    SubagentSettings,
)
from harness_agent.core import (
    ContextSettings,
    Message,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    Role,
    ToolCall,
    is_summary,
)
from harness_agent.core.loop import TurnStatus
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import make_config

SENTINEL = "VALOR-DE-PRUEBA-123"
DEFAULT, UNO, DOS, PLAN = "openai/base", "gemini/uno", "groq/dos", "ollama/plan"
UNO_ALIAS = ModelAlias("uno", UNO, Secret("clave-de-prueba-uno"), "GEMINI_API_KEY")
DOS_ALIAS = ModelAlias("dos", DOS, Secret("clave-de-prueba-dos"), "GROQ_API_KEY")
PLAN_ALIAS = ModelAlias("plan", PLAN, None, None)
NO_KEY_ALIAS = ModelAlias("sinclave", "gemini/sin-clave", None, "GEMINI_API_KEY")
SUMMARY_PROMPT_START = "Resume la conversación"
FILLING = "relleno " * 48  # about 100 estimated tokens per reply

Step = ProviderResponse | ProviderError


def reply(model: str, number: int = 0) -> ProviderResponse:
    return ProviderResponse(content=f"de {model} {number} {FILLING}".strip())


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class World:
    """One provider per model: a ``FakeProvider`` of a script, or a ready-made provider."""

    def __init__(
        self, scripts: dict[str, list[Step]], custom: dict[str, Provider] | None = None
    ) -> None:
        self.scripts = scripts
        self.custom = custom or {}
        self.providers: dict[str, Provider] = {}

    def __call__(self, config: HarnessConfig) -> Provider:
        model = config.model
        if model not in self.providers:
            self.providers[model] = self.custom.get(model) or FakeProvider(
                self.scripts.get(model, [reply(model)] * 8)
            )
        return self.providers[model]

    def calls(self, model: str) -> int:
        provider = self.providers.get(model)
        return 0 if provider is None else int(getattr(provider, "call_count", 0))

    def received(self, model: str) -> list[list[Message]]:
        provider = self.providers[model]
        assert isinstance(provider, FakeProvider)
        return provider.received


def make(
    tmp_path: Path,
    opened: list[Composition],
    world: World,
    *,
    aliases: tuple[ModelAlias, ...] = (UNO_ALIAS, DOS_ALIAS),
    failover: tuple[str, ...] = ("uno", "dos"),
    attempts: int = 1,
    context: ContextSettings | None = None,
    subagents: bool = False,
) -> Composition:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(exist_ok=True)
    config = make_config(tmp_path, workspace=workspace, model=DEFAULT)
    config = replace(
        config,
        models=aliases,
        failover=failover,
        retries=Retries(max_attempts=attempts),
        subagents=SubagentSettings(enabled=subagents),
    )
    if context is not None:
        config = replace(config, context=context)

    async def no_wait(seconds: float) -> None:
        return None

    composition = compose(config, provider_factory=world, system_name="Linux", retry_sleep=no_wait)
    opened.append(composition)
    return composition


async def run(composition: Composition, *lines: str) -> str:
    output = io.StringIO()
    await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
        output=output,
    )
    return output.getvalue()


def stored(composition: Composition, kind: str) -> list[dict[str, Any]]:
    """The payloads of the events of a type, read from the file the process left on the disk."""
    path = composition.store.connection().execute("PRAGMA database_list").fetchone()[2]
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            "SELECT content FROM events WHERE type = ? ORDER BY rowid", (kind,)
        ).fetchall()
    finally:
        connection.close()
    return [json.loads(content) for (content,) in rows]


def whole_database(composition: Composition) -> str:
    """Every text in the database, to prove that a value is nowhere."""
    path = composition.store.connection().execute("PRAGMA database_list").fetchone()[2]
    connection = sqlite3.connect(path)
    try:
        names = [
            name
            for (name,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return repr([connection.execute(f"SELECT * FROM {name}").fetchall() for name in names])
    finally:
        connection.close()


def litellm_provider(model: str, *failures: str) -> LiteLLMProvider:
    """The real adapter over a completion function that fails with LiteLLM-named exceptions."""
    errors = list(failures)

    async def completion(**request: Any) -> Any:
        if errors:
            kind: type[Exception] = type(errors.pop(0), (Exception,), {})
            raise kind(SENTINEL)
        return {"choices": [{"index": 0, "message": {"role": "assistant", "content": "listo"}}]}

    return LiteLLMProvider(model, max_output_tokens=100, completion=completion)


# --- AC-01 -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        QuotaExceeded(f"cuota {SENTINEL}"),
        RateLimited(f"límite {SENTINEL}"),
        ProviderTimeout(f"tiempo {SENTINEL}"),
        ProviderUnavailable(f"servicio {SENTINEL}"),
    ],
    ids=["quota", "rate-limit", "timeout", "unavailable"],
)
async def test_each_eligible_failure_switches_repeats_the_call_and_is_recorded_and_shown(
    tmp_path: Path, opened: list[Composition], error: ProviderError
) -> None:
    world = World({DEFAULT: [error]})
    composition = make(tmp_path, opened, world)

    shown = await run(composition, "hola")

    kind = type(error).__name__
    assert world.calls(DEFAULT) == 1 and world.calls(UNO) == 1
    assert f"de {UNO}" in shown  # the same request got the answer of the fallback model
    assert f"Cambio de modelo por fallo: {DEFAULT} a {UNO} ({kind})." in shown
    assert stored(composition, "provider_switched") == [
        {"from_model": DEFAULT, "to_model": UNO, "reason": kind}
    ]
    assert SENTINEL not in shown and SENTINEL not in whole_database(composition)


async def test_a_connection_error_of_the_adapter_switches(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World({}, {DEFAULT: litellm_provider(DEFAULT, "APIConnectionError")})
    composition = make(tmp_path, opened, world)

    shown = await run(composition, "hola")

    assert world.calls(UNO) == 1 and f"de {UNO}" in shown
    assert stored(composition, "provider_switched")[0]["reason"] == "ProviderUnavailable"
    assert SENTINEL not in shown and SENTINEL not in whole_database(composition)


async def test_the_fallback_model_receives_the_same_history_and_tools(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World({DEFAULT: [ProviderTimeout("a")]})
    composition = make(tmp_path, opened, world)

    await run(composition, "hola")

    assert world.received(DEFAULT)[0] == world.received(UNO)[0]
    default_tools = world.providers[DEFAULT].received_tools[0]  # type: ignore[attr-defined]
    assert world.providers[UNO].received_tools[0] == default_tools  # type: ignore[attr-defined]


async def test_the_retries_are_spent_before_the_failover(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World({DEFAULT: [ProviderTimeout("a"), ProviderTimeout("b")]})
    composition = make(tmp_path, opened, world, attempts=2)

    await run(composition, "hola")

    assert world.calls(DEFAULT) == 2  # the retry of HU-07-04 first
    assert world.calls(UNO) == 1


async def test_the_model_stays_switched_for_the_next_requests_and_the_command_shows_it(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World({DEFAULT: [ProviderTimeout("a")]})
    composition = make(tmp_path, opened, world)

    shown = await run(composition, "primera", "segunda", "/model")

    assert world.calls(DEFAULT) == 1 and world.calls(UNO) == 2
    assert UNO in shown.split("Modelo")[-1]


async def test_an_eligible_failure_in_the_call_of_the_summary_switches_too(
    tmp_path: Path, opened: list[Composition]
) -> None:
    context = ContextSettings(
        window_tokens=2_400,
        threshold_percent=45,
        recent_percent=5,
        min_recent_messages=4,
        summary_tokens=100,
    )
    world = World(
        {
            DEFAULT: [reply(DEFAULT, n) for n in range(1, 5)] + [ProviderTimeout("a")],
            UNO: [ProviderResponse(content="Resumen de lo anterior."), reply(UNO, 5)],
        }
    )
    composition = make(tmp_path, opened, world, context=context)

    shown = await run(composition, *(f"tarea {n}" for n in range(1, 6)))

    summary_prompts = [
        messages
        for messages in world.received(UNO)
        if messages[0].role is Role.SYSTEM and messages[0].content.startswith(SUMMARY_PROMPT_START)
    ]
    assert len(summary_prompts) == 1  # the summary call was repeated on the fallback model
    assert stored(composition, "provider_switched")[0]["to_model"] == UNO
    assert stored(composition, "context_compacted") != []
    assert stored(composition, "provider_error") == []  # no failed compaction
    assert "de gemini/uno 5" in shown


# --- AC-02 -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failure",
    ["AuthenticationError", "BadRequestError", "ContentPolicyViolationError", "SomethingNew"],
    ids=["bad-key", "bad-request", "content-policy", "unknown"],
)
async def test_a_failure_that_is_not_eligible_reaches_the_person_without_a_switch(
    tmp_path: Path, opened: list[Composition], failure: str
) -> None:
    world = World({}, {DEFAULT: litellm_provider(DEFAULT, failure)})
    composition = make(tmp_path, opened, world)

    result = await composition.loop.run_turn(
        session_id=composition.session_id, task="hola", history=[]
    )

    assert result.status is TurnStatus.PROVIDER_FAILED
    assert world.calls(UNO) == 0 and world.calls(DOS) == 0
    assert stored(composition, "provider_switched") == []
    assert SENTINEL not in whole_database(composition)


@pytest.mark.parametrize(
    "error",
    [ProviderError(f"x {SENTINEL}"), RuntimeError(SENTINEL)],
    ids=["generic-provider-error", "unknown-exception"],
)
async def test_a_generic_or_unknown_error_makes_a_single_call_and_ends_the_turn(
    tmp_path: Path, opened: list[Composition], error: Exception
) -> None:
    class Raising(Provider):
        calls = 0

        async def complete(self, messages: list[Message], tools: Any = None) -> ProviderResponse:
            type(self).calls += 1
            raise error

    world = World({}, {DEFAULT: Raising()})
    composition = make(tmp_path, opened, world)

    result = await composition.loop.run_turn(
        session_id=composition.session_id, task="hola", history=[]
    )

    assert result.status is TurnStatus.PROVIDER_FAILED
    assert Raising.calls == 1 and world.calls(UNO) == 0
    assert stored(composition, "provider_switched") == []


# --- AC-03 -----------------------------------------------------------------------------------


async def test_when_every_model_fails_each_is_called_once_and_the_error_is_fixed(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World(
        {
            DEFAULT: [ProviderTimeout(f"a {SENTINEL}")],
            UNO: [QuotaExceeded(f"b {SENTINEL}")],
            DOS: [ProviderUnavailable(f"c {SENTINEL}")],
        }
    )
    composition = make(tmp_path, opened, world)

    shown = await run(composition, "hola")

    assert (world.calls(DEFAULT), world.calls(UNO), world.calls(DOS)) == (1, 1, 1)
    assert "FailoverExhausted" in shown
    assert SENTINEL not in shown and SENTINEL not in whole_database(composition)
    assert [e["to_model"] for e in stored(composition, "provider_switched")] == [UNO, DOS]
    (failure,) = stored(composition, "provider_error")
    assert failure["error_type"] == "FailoverExhausted"
    assert SENTINEL not in repr(failure)


async def test_the_next_request_starts_the_list_again(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World(
        {
            DEFAULT: [ProviderTimeout("a"), reply(DEFAULT, 2)],
            UNO: [ProviderTimeout("b")],
            DOS: [ProviderTimeout("c"), ProviderTimeout("d")],
        }
    )
    composition = make(tmp_path, opened, world)

    shown = await run(composition, "primera", "segunda")

    # First request: default, uno and dos all fail. Second: dos is active and fails, and the
    # default - tried in the first request - is tried again and answers.
    assert world.calls(DEFAULT) == 2 and world.calls(DOS) == 2
    assert f"de {DEFAULT} 2" in shown


async def test_the_model_that_is_active_when_the_request_starts_counts_as_tried(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World({PLAN: [QuotaExceeded("a")]})
    composition = make(tmp_path, opened, world, aliases=(PLAN_ALIAS, UNO_ALIAS), failover=("uno",))

    shown = await run(composition, "/model plan", "hola")

    assert world.calls(PLAN) == 1  # not tried again
    assert world.calls(DEFAULT) == 1  # the default goes first in the list
    assert "de openai/base" in shown
    assert stored(composition, "provider_switched")[0]["from_model"] == PLAN


async def test_a_manual_change_between_two_requests_does_not_break_the_failover(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World({UNO: [ProviderTimeout("a")]})
    composition = make(tmp_path, opened, world)

    shown = await run(composition, "primera", "/model uno", "segunda")

    assert world.calls(DEFAULT) == 2 and world.calls(UNO) == 1
    assert stored(composition, "provider_switched") == [
        {"from_model": UNO, "to_model": DEFAULT, "reason": "ProviderTimeout"}
    ]
    assert "de openai/base" in shown


# --- keys, subagents ----------------------------------------------------------------------------


async def test_a_fallback_without_its_key_is_left_out_and_the_next_one_is_used(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World({DEFAULT: [ProviderTimeout("a")]})
    composition = make(
        tmp_path,
        opened,
        world,
        aliases=(NO_KEY_ALIAS, DOS_ALIAS),
        failover=("sinclave", "dos"),
    )

    shown = await run(composition, "hola")

    assert "Modelo de respaldo «sinclave» omitido: falta la variable GEMINI_API_KEY" in shown
    assert world.calls(DOS) == 1
    assert [e["to_model"] for e in stored(composition, "provider_switched")] == [DOS]


async def test_a_subagent_shares_the_state_of_the_request(
    tmp_path: Path, opened: list[Composition]
) -> None:
    delegation = ProviderResponse(
        content="", tool_calls=[ToolCall("c-del", "delegar", {"objetivo": "Resume a.txt."})]
    )
    result = ProviderResponse(
        content=json.dumps({"resultado": "listo", "hallazgos_clave": [], "fuentes": []})
    )
    world = World(
        {
            DEFAULT: [ProviderTimeout("a")],
            UNO: [delegation, ProviderTimeout("b")],
            DOS: [result, ProviderResponse(content="terminado")],
        }
    )
    composition = make(tmp_path, opened, world, subagents=True)

    outcome = await composition.loop.run_turn(
        session_id=composition.session_id, task="delega", history=[]
    )

    assert outcome.status is TurnStatus.COMPLETED and outcome.final_response == "terminado"
    # The default was tried by the orchestrator in this request: the subagent does not go back to
    # it when its own call fails, it goes on to the next model of the list.
    assert (world.calls(DEFAULT), world.calls(UNO), world.calls(DOS)) == (1, 2, 2)
    assert [e["to_model"] for e in stored(composition, "provider_switched")] == [UNO, DOS]


# --- AC-04 -----------------------------------------------------------------------------------


def small_and_large(small_model: str, large_model: str) -> ContextSettings:
    return ContextSettings(
        window_tokens=1_000_000,
        windows=((small_model, 2_400), (large_model, 1_000_000)),
        threshold_percent=45,
        recent_percent=5,
        min_recent_messages=4,
        summary_tokens=100,
    )


def summary_calls(world: World, model: str) -> int:
    return sum(
        1
        for messages in world.received(model)
        if messages[0].role is Role.SYSTEM and messages[0].content.startswith(SUMMARY_PROMPT_START)
    )


async def test_after_the_switch_the_compaction_uses_the_threshold_of_the_new_model(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World(
        {
            DEFAULT: [reply(DEFAULT, n) for n in range(1, 4)] + [ProviderTimeout("a")],
            UNO: [reply(UNO, 4), ProviderResponse(content="Resumen."), reply(UNO, 5)],
        }
    )
    composition = make(
        tmp_path, opened, world, context=small_and_large(UNO, DEFAULT), failover=("uno",)
    )

    await run(composition, *(f"tarea {n}" for n in range(1, 6)))

    # The default (a huge window) never compacted; "uno" (a small window) did, on the request that
    # followed the switch.
    assert summary_calls(world, DEFAULT) == 0
    assert summary_calls(world, UNO) == 1
    assert len(stored(composition, "context_compacted")) == 1
    assert composition.current_view is not None
    assert composition.current_view().window_tokens == 2_400


async def test_with_a_big_window_in_both_models_the_same_flow_does_not_compact(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World(
        {
            DEFAULT: [reply(DEFAULT, n) for n in range(1, 4)] + [ProviderTimeout("a")],
            UNO: [reply(UNO, 4), reply(UNO, 5)],
        }
    )
    composition = make(
        tmp_path, opened, world, context=ContextSettings(window_tokens=1_000_000), failover=("uno",)
    )

    await run(composition, *(f"tarea {n}" for n in range(1, 6)))

    assert summary_calls(world, UNO) == 0
    assert all(not is_summary(m) for call in world.received(UNO) for m in call)
    assert stored(composition, "context_compacted") == []
