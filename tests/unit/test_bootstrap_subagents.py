"""Composition root: the delegation to subagents (HU-09-01, HU-09-04 / T011).

The provider is a ``FakeProvider`` whose script has the steps of the orchestrator and of the
subagent in the order the calls happen; the database is a temporary file.
"""

from __future__ import annotations

import io
import json
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.tools import Question
from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import SubagentSettings
from harness_agent.core import (
    RESULT_SCHEMA,
    EventType,
    PermissionRules,
    ProviderResponse,
    RegistryView,
    SubagentApprover,
    SubagentRunner,
    ToolCall,
)
from harness_agent.core.loop import AgentLoop
from tests.doubles import DummyApprover, DummyTool, FakeProvider
from tests.unit.bootstrap_support import build, make_config

CALL = ToolCall("c1", "delegar", {"objetivo": "Resume el módulo."})
DELEGATE = ProviderResponse(content="", tool_calls=[CALL])
ANSWER = ProviderResponse(
    content=json.dumps({"resultado": "listo", "hallazgos_clave": ["uno"], "fuentes": ["a.py"]})
)
FINAL = ProviderResponse(content="hecho")
ON = SubagentSettings(enabled=True)


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def make(
    tmp_path: Path,
    opened: list[Composition],
    *script: ProviderResponse,
    permissions: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
    subagents: SubagentSettings = ON,
    **options: Any,
) -> tuple[Composition, FakeProvider]:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(exist_ok=True)
    config = make_config(tmp_path, workspace=workspace, permissions=permissions)
    config = replace(config, subagents=subagents)
    provider = FakeProvider(script or [FINAL])
    return build(opened, config, provider, system_name="Linux", **options), provider


async def turn(composition: Composition) -> list[dict[str, Any]]:
    """Run one request and return the permission decisions of the orchestrator's session."""
    decisions: list[dict[str, Any]] = []
    composition.bus.subscribe(
        EventType.PERMISSION_DECIDED,
        lambda event: (
            decisions.append(event.payload) if event.session_id == composition.session_id else None
        ),
    )
    await composition.loop.run_turn(session_id=composition.session_id, task="delega", history=[])
    return decisions


async def test_the_delegation_is_registered_and_offered_to_the_model(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(tmp_path, opened, FINAL)

    await turn(composition)

    names = {tool.name for tool in provider.received_tools[0] or []}
    assert "delegar" in names and "leer_archivo" in names
    assert isinstance(composition.subagent_runner, SubagentRunner)


async def test_by_default_the_delegation_does_not_exist(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(tmp_path, opened, FINAL, subagents=SubagentSettings())

    await turn(composition)

    names = {tool.name for tool in provider.received_tools[0] or []}
    assert "delegar" not in names and composition.registry.get("delegar") is None
    assert composition.subagent_runner is None


async def test_it_is_registered_with_the_question_tool_too(
    tmp_path: Path, opened: list[Composition]
) -> None:
    async def ask(question: Question) -> None:
        return None

    composition, _ = make(tmp_path, opened, FINAL, ask=ask)

    assert composition.registry.get("delegar") is not None
    assert composition.registry.get("preguntar_usuario") is not None


async def test_the_chain_allows_the_delegation_without_asking(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(tmp_path, opened, DELEGATE, ANSWER, FINAL)

    decisions = await turn(composition)

    assert [(d["name"], d["decision"]) for d in decisions] == [("delegar", "allow")]
    assert provider.call_count == 3  # the orchestrator, the subagent and the orchestrator again


@pytest.mark.parametrize(
    ("rules", "decision"),
    [
        (PermissionRules(deny=("delegar",)), "deny"),
        (PermissionRules(ask=("delegar",)), "ask"),
    ],
    ids=["deny", "ask"],
)
async def test_the_configuration_can_deny_or_ask_the_delegation(
    tmp_path: Path, opened: list[Composition], rules: PermissionRules, decision: str
) -> None:
    composition, provider = make(tmp_path, opened, DELEGATE, FINAL, permissions=rules)

    decisions = await turn(composition)

    assert decisions[0]["decision"] == decision and decisions[0]["resolved_as"] == "deny"
    assert provider.call_count == 2  # the subagent never ran


async def test_the_read_only_mode_denies_the_delegation(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(tmp_path, opened, DELEGATE, FINAL, read_only=True)

    decisions = await turn(composition)

    assert decisions[0]["decision"] == "deny" and provider.call_count == 2


async def test_the_subagent_does_not_see_the_delegation_but_sees_the_rest_and_what_comes_later(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(tmp_path, opened, DELEGATE, ANSWER, FINAL)
    composition.registry.register(DummyTool(name="mcp_buscar"))

    await turn(composition)

    orchestrator = {tool.name for tool in provider.received_tools[0] or []}
    subagent = {tool.name for tool in provider.received_tools[1] or []}
    assert "delegar" in orchestrator
    assert "delegar" not in subagent
    assert subagent == orchestrator - {"delegar"} and "mcp_buscar" in subagent


class Spy(AgentLoop):
    """Records the collaborators each loop is built with: the first is the orchestrator's."""

    built: list[dict[str, Any]] = []

    def __init__(self, provider: Any, registry: Any, policy: Any, bus: Any, *args: Any, **kw: Any):
        Spy.built.append(
            {"provider": provider, "registry": registry, "policy": policy, "bus": bus, **kw}
        )
        super().__init__(provider, registry, policy, bus, *args, **kw)


async def test_the_loop_of_the_subagent_shares_provider_policy_and_bus_with_its_own_limits(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    Spy.built = []
    monkeypatch.setattr(bootstrap, "AgentLoop", Spy)
    settings = SubagentSettings(enabled=True, max_turns=4, max_seconds=60, max_tokens=1000)
    composition, _ = make(
        tmp_path, opened, DELEGATE, ANSWER, FINAL, subagents=settings, approver=DummyApprover()
    )

    await turn(composition)

    main, child = Spy.built
    assert child["policy"] is main["policy"]  # the very object: deny, protected and read-only
    assert child["provider"] is main["provider"] and child["bus"] is main["bus"]
    assert isinstance(child["registry"], RegistryView) and child["registry"] is not main["registry"]
    assert (main["limits"].max_turns, child["limits"].max_turns) == (30, 4)
    assert (child["limits"].max_seconds, child["limits"].max_tokens) == (60, 1000)
    assert isinstance(child["approver"], SubagentApprover)


async def test_without_an_approver_the_subagent_has_none_either(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    Spy.built = []
    monkeypatch.setattr(bootstrap, "AgentLoop", Spy)
    composition, _ = make(tmp_path, opened, DELEGATE, ANSWER, FINAL)

    await turn(composition)

    assert Spy.built[1]["approver"] is None


async def test_the_child_session_hangs_from_the_session_after_a_new_one_too(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = make(tmp_path, opened, ANSWER)
    output = io.StringIO()
    await run_session(composition, input_stream=io.StringIO("/nueva\n/salir\n"), output=output)
    newest = composition.session_cursor.value if composition.session_cursor else ""

    assert newest and newest != composition.session_id
    assert newest in output.getvalue()


async def test_the_runner_hangs_the_child_from_the_cursor_and_reports_a_missing_parent(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(tmp_path, opened, ANSWER)
    runner = composition.subagent_runner
    assert runner is not None and composition.session_cursor is not None

    good = await runner.execute("general", "meta", [], RESULT_SCHEMA)
    composition.session_cursor.value = "no-existe"
    lost = await runner.execute("general", "meta", [], RESULT_SCHEMA)

    row = (
        composition.store.connection()
        .execute("SELECT parent_id, goal FROM sessions WHERE id = ?", (good.session_id,))
        .fetchone()
    )
    assert row == (composition.session_id, "meta")
    assert lost.is_error is True and lost.output["error"] == "sin_sesion_hija"
    assert provider.call_count == 1  # the lost parent never reached the provider


async def test_a_new_session_works_in_a_composition_without_a_cursor(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = make(tmp_path, opened, ANSWER)
    output = io.StringIO()

    await run_session(
        replace(composition, session_cursor=None),
        input_stream=io.StringIO("/nueva\n/salir\n"),
        output=output,
    )

    assert "Sesión nueva:" in output.getvalue()
