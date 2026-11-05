"""AC-02 of HU-00-05.1 with the composed system: a provider failing after a tool, a raising tool.

``compose()`` builds the real loop, policy chain, registry (with its trace and truncation
wrappers), bus, audit, failover and retries over a SQLite file in ``tmp_path``; the models are
``FakeProvider`` doubles by name. Nothing reaches the network, a key or the console. What the
existing tests already prove (the four errors on the first call of a turn, the loop with doubles,
the cancellation) is not repeated here.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.providers.errors import RateLimited
from harness_agent.bootstrap import Composition, compose, run_session
from harness_agent.config import HarnessConfig, Limits, ModelAlias, Retries, Secret
from harness_agent.core import (
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    RiskLevel,
    Role,
    Tool,
    ToolCall,
    ToolResult,
)
from harness_agent.core.loop import TurnStatus
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import make_config

SENTINEL = "VALOR-DE-PRUEBA-123"
DEFAULT, UNO = "openai/base", "gemini/uno"
UNO_ALIAS = ModelAlias("uno", UNO, Secret("clave-de-prueba-uno"), "GEMINI_API_KEY")
SCHEMA = {
    "type": "object",
    "properties": {"path": {"type": "string"}},
    "required": ["path"],
    "additionalProperties": False,
}


class Fatal(BaseException):
    """A failure that is neither an ``Exception`` nor a cancellation."""


class Echo(Tool):
    """An instant tool inside the work area (low risk: the policy lets it through)."""

    @property
    def name(self) -> str:
        return "eco"

    @property
    def description(self) -> str:
        return "Answers ok."

    @property
    def schema(self) -> dict[str, Any]:
        return SCHEMA

    @property
    def risk(self) -> RiskLevel:
        return RiskLevel.LOW

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return ToolResult("", "ok", False)


class Breaking(Echo):
    """The same tool, but it fails with the given error."""

    def __init__(self, error: BaseException) -> None:
        self._error = error

    @property
    def name(self) -> str:
        return "roto"

    async def run(self, args: dict[str, Any]) -> ToolResult:
        raise self._error


def call(identifier: str, tool: str) -> ProviderResponse:
    return ProviderResponse(content="", tool_calls=[ToolCall(identifier, tool, {"path": "."})])


class World:
    """One ``FakeProvider`` per model name, built once."""

    def __init__(self, scripts: dict[str, list[ProviderResponse | ProviderError]]) -> None:
        self._scripts = scripts
        self.providers: dict[str, FakeProvider] = {}

    def __call__(self, config: HarnessConfig) -> Provider:
        if config.model not in self.providers:
            self.providers[config.model] = FakeProvider(self._scripts[config.model])
        return self.providers[config.model]


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def make(
    tmp_path: Path,
    opened: list[Composition],
    world: World,
    *tools: Tool,
    failover: bool = False,
) -> Composition:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(exist_ok=True)
    config = replace(
        make_config(tmp_path, workspace=workspace, model=DEFAULT),
        limits=Limits(max_turns=50, max_output_tokens=777),
        retries=Retries(max_attempts=1),
    )
    if failover:
        config = replace(config, models=(UNO_ALIAS,), failover=("uno",))

    async def no_wait(seconds: float) -> None:
        return None

    composition = compose(config, provider_factory=world, system_name="Linux", retry_sleep=no_wait)
    opened.append(composition)
    for tool in tools:
        composition.registry.register(tool)
    return composition


def events(composition: Composition) -> list[tuple[str, dict[str, Any]]]:
    rows = composition.store.connection().execute(
        "SELECT type, content FROM events WHERE session_id = ? ORDER BY seq",
        (composition.session_id,),
    )
    return [(kind, json.loads(content)) for kind, content in rows]


def whole_database(composition: Composition, tables: tuple[str, ...]) -> str:
    connection = composition.store.connection()
    return repr([connection.execute(f"SELECT * FROM {table}").fetchall() for table in tables])


async def turn(composition: Composition) -> tuple[Any, list[Any]]:
    history = list(composition.history_prefix)
    result = await composition.loop.run_turn(
        session_id=composition.session_id, task="hola", history=history
    )
    return result, history


# --- AC-02: the provider fails after a tool ran --------------------------------------------------


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
async def test_ac02_a_failure_after_a_tool_switches_and_repeats_the_call_with_its_result(
    tmp_path: Path, opened: list[Composition], error: ProviderError
) -> None:
    world = World({DEFAULT: [call("c1", "eco"), error], UNO: [ProviderResponse(content="de uno")]})
    composition = make(tmp_path, opened, world, Echo(), failover=True)
    output = io.StringIO()

    code = await run_session(composition, input_stream=io.StringIO("hola\n/salir\n"), output=output)

    default, fallback = world.providers[DEFAULT], world.providers[UNO]
    assert code == 0 and "de uno" in output.getvalue()  # the turn ended with the fallback's answer
    assert default.call_count == 2 and fallback.call_count == 1
    assert fallback.received[0] == default.received[1]  # the same call, repeated
    assert [m.role for m in fallback.received[0]][-1] is Role.TOOL  # ... with the tool's result
    assert [kind for kind, _payload in events(composition)] == [
        "user_message",
        "tool_requested",
        "permission_decided",
        "tool_finished",
        "provider_switched",
        "assistant_message",  # the call of the first model has no text, so it has no event
    ]
    assert [p for kind, p in events(composition) if kind == "provider_switched"] == [
        {"from_model": DEFAULT, "to_model": UNO, "reason": type(error).__name__}
    ]
    assert SENTINEL not in output.getvalue()
    assert SENTINEL not in whole_database(composition, ("events", "auditoria", "trazas"))


# --- AC-02: a tool that raises -------------------------------------------------------------------


async def test_ac02_a_raising_tool_reaches_the_model_as_a_bounded_error_and_the_turn_goes_on(
    tmp_path: Path, opened: list[Composition]
) -> None:
    long_text = f"{SENTINEL} " + "x" * 2_000
    world = World({DEFAULT: [call("c1", "roto"), ProviderResponse(content="seguimos")]})
    composition = make(tmp_path, opened, world, Breaking(RuntimeError(long_text)))

    result, history = await turn(composition)

    assert result.status is TurnStatus.COMPLETED  # the loop went on to the model's next call
    provider = world.providers[DEFAULT]
    assert provider.call_count == 2
    received = provider.received[1][-1]
    assert received.role is Role.TOOL and received.tool_result is not None
    assert received.tool_result.is_error is True
    assert received.content.startswith("[tool_exception] Tool 'roto' raised RuntimeError: ")
    assert "Traceback" not in received.content and len(received.content) < 700  # bounded
    assert history[-1].content == "seguimos"


async def test_ac02_a_tool_error_leaves_event_audit_and_trace_without_the_exception_text(
    tmp_path: Path, opened: list[Composition]
) -> None:
    world = World({DEFAULT: [call("c1", "roto"), ProviderResponse(content="seguimos")]})
    composition = make(tmp_path, opened, world, Breaking(RuntimeError(SENTINEL)))

    await turn(composition)

    finished = [p for kind, p in events(composition) if kind == "tool_finished"]
    assert finished == [
        {"call_id": "c1", "name": "roto", "is_error": True, "category": "tool_exception"}
    ]
    connection = composition.store.connection()
    audit = connection.execute("SELECT herramienta, decision, resolucion FROM auditoria").fetchall()
    assert [tuple(row) for row in audit] == [("roto", "allow", "permitida")]
    traces = connection.execute(
        "SELECT tipo, nombre, resultado FROM trazas WHERE tipo = 'herramienta'"
    ).fetchall()
    assert [tuple(row) for row in traces] == [
        ("herramienta", "roto", "RuntimeError")
    ]  # the class that the tool raised
    assert SENTINEL not in whole_database(composition, ("events", "auditoria", "trazas"))


async def test_a_base_exception_of_a_tool_that_is_not_a_cancellation_propagates_unconverted(
    tmp_path: Path, opened: list[Composition]
) -> None:
    """Characterization of today's design (finding F-01): it rises like a cancellation would."""
    world = World({DEFAULT: [call("c1", "roto"), ProviderResponse(content="no llega")]})
    composition = make(tmp_path, opened, world, Breaking(Fatal(SENTINEL)))
    history = list(composition.history_prefix)

    with pytest.raises(Fatal):
        await composition.loop.run_turn(
            session_id=composition.session_id, task="hola", history=history
        )

    kinds = [kind for kind, _payload in events(composition)]
    assert "tool_finished" not in kinds  # no result was made up for the call
    assert world.providers[DEFAULT].call_count == 1  # and the loop did not go on
    assert history[-1].role is Role.ASSISTANT and history[-1].tool_calls  # call without result
