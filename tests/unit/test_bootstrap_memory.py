"""compose() and run_session() wire the persistent memory (HU-04-01 and HU-04-02 / T008).

The provider is a ``FakeProvider``; the database is a temporary file shared by the sessions of a
test; the shell is a double that never runs. The memory is off by default: with it off nothing is
registered, loaded or said even if the file already holds entries.
"""

from __future__ import annotations

import dataclasses
import io
import json
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.storage import SqliteMemoryStore, SqliteSessionStore
from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import SubagentSettings
from harness_agent.core import (
    ApprovalAction,
    ContextSettings,
    CriterionDefinition,
    EventType,
    MemorySettings,
    Message,
    ProviderResponse,
    RegistryView,
    Role,
    Shell,
    ShellResult,
    TaskDefinition,
    ToolCall,
    find_memory_block,
    is_memory_block,
)
from tests.doubles import DummyApprover, FakeProvider
from tests.unit.bootstrap_support import build, make_config

ON = MemorySettings(enabled=True)
T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
SAVE = ToolCall("m1", "memoria", {"accion": "guardar", "clave": "estilo", "texto": "tabs de 4"})
SAVING = ProviderResponse(content="", tool_calls=[SAVE])
DONE = ProviderResponse(content="listo")
SAVING_AGAIN = ProviderResponse(
    content="", tool_calls=[ToolCall("m2", "memoria", {**SAVE.arguments, "texto": "tabs de 2"})]
)


class NoShell(Shell):
    @property
    def interpreter_name(self) -> str:
        return "bash"

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        raise AssertionError("no command runs in these tests")

    def terminate_running(self) -> None:
        """Nothing runs."""


@pytest.fixture(autouse=True)
def no_real_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: NoShell())


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def save_entries(tmp_path: Path, entries: dict[str, str]) -> None:
    """Write entries to the database of ``make_config`` before any composition opens it."""
    store = SqliteSessionStore(make_config(tmp_path).paths.sessions_db)
    ticks = iter(range(1, 10_000))
    memory = SqliteMemoryStore(store, clock=lambda: T0 + timedelta(seconds=next(ticks)))
    for key, content in entries.items():
        memory.remember(key, content)
    store.close()


def compose_with(
    tmp_path: Path,
    opened: list[Composition],
    *script: ProviderResponse,
    memory: MemorySettings = ON,
    **options: Any,
) -> tuple[Composition, FakeProvider]:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(parents=True, exist_ok=True)
    config = dataclasses.replace(make_config(tmp_path, workspace=workspace), memory=memory)
    for field in ("subagents", "context"):
        if field in options:
            config = dataclasses.replace(config, **{field: options.pop(field)})
    provider = FakeProvider(list(script) or [DONE])
    return build(opened, config, provider, system_name="Linux", **options), provider


async def drive(composition: Composition, *lines: str) -> list[str]:
    output = io.StringIO()
    await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
        output=output,
    )
    return output.getvalue().replace("tarea> ", "").splitlines()


def blocks(messages: list[Message]) -> list[Message]:
    return [message for message in messages if is_memory_block(message)]


# --- off by default ---------------------------------------------------------------------------


async def test_by_default_nothing_is_registered_loaded_or_said(
    tmp_path: Path, opened: list[Composition]
) -> None:
    save_entries(tmp_path, {"estilo": "tabs de 4"})
    composition, provider = compose_with(tmp_path, opened, memory=MemorySettings())

    shown = await drive(composition, "hola")

    assert composition.memory is None and composition.registry.get("memoria") is None
    assert blocks(provider.received[0]) == []
    assert [m.role for m in provider.received[0]] == [Role.SYSTEM, Role.USER]
    assert not any("Memoria" in line for line in shown)
    assert "memoria" not in {tool.name for tool in provider.received_tools[0] or []}


# --- on: the tool and the block ---------------------------------------------------------------


async def test_with_the_memory_on_the_tool_is_offered_and_the_loader_exists(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = compose_with(tmp_path, opened)

    await drive(composition, "hola")

    assert composition.memory is not None and composition.registry.get("memoria") is not None
    assert "memoria" in {tool.name for tool in provider.received_tools[0] or []}


async def test_the_block_goes_before_the_first_request_after_the_prefix(
    tmp_path: Path, opened: list[Composition]
) -> None:
    save_entries(tmp_path, {"estilo": "tabs de 4", "idioma": "español"})
    composition, provider = compose_with(tmp_path, opened)

    shown = await drive(composition, "hola")

    sent = provider.received[0]
    assert [m.role for m in sent] == [Role.SYSTEM, Role.USER, Role.USER]
    assert is_memory_block(sent[1]) and not is_memory_block(sent[2]) and sent[2].content == "hola"
    assert find_memory_block(sent) == 1
    assert "tabs de 4" in sent[1].content and "español" in sent[1].content
    assert sent[1].is_external is True
    assert not any("Memoria:" in line for line in shown)  # everything fit: nothing to say


async def test_without_entries_there_is_no_block_and_no_line(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = compose_with(tmp_path, opened)

    shown = await drive(composition, "hola")

    assert blocks(provider.received[0]) == []
    assert not any("Memoria" in line for line in shown)


async def test_what_does_not_fit_is_said_before_the_first_prompt(
    tmp_path: Path, opened: list[Composition]
) -> None:
    save_entries(tmp_path, {f"k{n:02d}": "x" * 300 for n in range(30)})
    composition, provider = compose_with(
        tmp_path, opened, memory=MemorySettings(enabled=True, budget_tokens=400)
    )

    shown = await drive(composition, "hola")

    (block,) = blocks(provider.received[0])
    loaded = block.content.count("\n- ")
    assert 0 < loaded < 30
    assert f"Se omitieron {30 - loaded} entradas más antiguas por el presupuesto." in block.content
    line = f"Memoria: se cargaron {loaded} entradas y se omitieron {30 - loaded} más antiguas "
    assert (line + "por el presupuesto.") in shown
    assert shown.index(line + "por el presupuesto.") < shown.index("Sesión terminada.")
    assert "k29" in block.content  # the most recent one enters first


async def test_a_new_session_loads_the_block_once_and_drops_the_old_conversation(
    tmp_path: Path, opened: list[Composition]
) -> None:
    save_entries(tmp_path, {"estilo": "tabs de 4"})
    composition, provider = compose_with(tmp_path, opened, DONE, DONE)

    await drive(composition, "primera", "/nueva", "segunda")

    second = provider.received[1]
    assert [m.content for m in second if m.role is Role.USER and not m.is_external] == ["segunda"]
    assert len(blocks(second)) == 1 and find_memory_block(second) == 1


async def test_a_resumed_session_does_not_get_the_block(
    tmp_path: Path, opened: list[Composition]
) -> None:
    first, _ = compose_with(tmp_path, opened)
    await drive(first, "hola")
    first.close()
    save_entries(tmp_path, {"estilo": "tabs de 4"})
    second, provider = compose_with(tmp_path, opened, DONE)

    await drive(second, f"/reanudar {first.session_id}", "sigue")

    assert blocks(provider.received[0]) == []
    assert any(m.content == "hola" for m in provider.received[0])


async def test_the_block_is_loaded_with_the_budget_of_the_active_model(
    tmp_path: Path, opened: list[Composition]
) -> None:
    save_entries(tmp_path, {f"k{n:02d}": "x" * 150 for n in range(20)})
    context = ContextSettings(windows=(("openai/modelo-de-prueba", 1_500),))
    composition, provider = compose_with(tmp_path, opened, context=context)

    await drive(composition, "hola")

    (block,) = blocks(provider.received[0])
    assert 0 < block.content.count("\n- ") < 20  # 20 % of the threshold of a 1 500 window: 240


# --- a session with a task --------------------------------------------------------------------


async def test_a_task_session_gets_the_block_after_the_essential_one(
    tmp_path: Path, opened: list[Composition]
) -> None:
    save_entries(tmp_path, {"estilo": "tabs de 4"})
    task = TaskDefinition(
        title="TAREA-1: Algo",
        objective="Hacer algo.",
        context="",
        rules="",
        criteria=(CriterionDefinition("Se ve bien"),),
    )
    composition, provider = compose_with(tmp_path, opened, task=task)

    await drive(composition, "hola")

    sent = provider.received[0]
    memory_at = find_memory_block(sent)
    assert memory_at is not None and len(blocks(sent)) == 1
    prefix = sent[:memory_at]
    assert prefix and all(m.role is Role.SYSTEM for m in prefix)  # environment, git, essential
    assert any("[contexto esencial de la tarea]" in m.content for m in prefix)
    assert sent[memory_at + 1].role is Role.USER and not sent[memory_at + 1].is_external


# --- permissions: read-only, /plan, the approver ---------------------------------------------


async def decisions(composition: Composition, *lines: str) -> list[str]:
    seen: list[str] = []
    composition.bus.subscribe(
        EventType.PERMISSION_DECIDED,
        lambda event: seen.append(str(event.payload["decision"]))
        if event.payload["name"] == "memoria"
        else None,
    )
    await drive(composition, *lines)
    return seen


def stored(composition: Composition) -> list[tuple[Any, ...]]:
    return (
        composition.store.connection().execute("SELECT clave, contenido FROM memorias").fetchall()
    )


async def test_the_tool_asks_and_with_an_approver_it_saves(
    tmp_path: Path, opened: list[Composition]
) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    composition, _ = compose_with(tmp_path, opened, SAVING, DONE, approver=approver)

    seen = await decisions(composition, "guarda")

    assert seen == ["ask"] and len(approver.recorded_requests) == 1
    assert stored(composition) == [("estilo", "tabs de 4")]


async def test_without_an_approver_it_is_denied_and_nothing_is_saved(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = compose_with(tmp_path, opened, SAVING, DONE)

    await decisions(composition, "guarda")

    assert stored(composition) == []


async def test_read_only_denies_it_even_with_an_approver_that_approves(
    tmp_path: Path, opened: list[Composition]
) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    composition, _ = compose_with(tmp_path, opened, SAVING, DONE, approver=approver, read_only=True)

    seen = await decisions(composition, "guarda")

    assert seen == ["deny"] and approver.recorded_requests == [] and stored(composition) == []


async def test_plan_mode_denies_it_and_implement_gives_it_back(
    tmp_path: Path, opened: list[Composition]
) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    composition, _ = compose_with(
        tmp_path, opened, SAVING, DONE, SAVING_AGAIN, DONE, approver=approver
    )

    seen = await decisions(composition, "/plan", "guarda", "/implementar", "guarda otra vez")

    assert seen == ["deny", "ask"]
    assert stored(composition) == [("estilo", "tabs de 2")]


async def test_the_loading_still_works_in_read_only_mode(
    tmp_path: Path, opened: list[Composition]
) -> None:
    save_entries(tmp_path, {"estilo": "tabs de 4"})
    composition, provider = compose_with(tmp_path, opened, read_only=True)

    await drive(composition, "hola")

    assert len(blocks(provider.received[0])) == 1


# --- the subagents ----------------------------------------------------------------------------


async def test_a_subagent_does_not_see_the_tool_nor_the_block(
    tmp_path: Path, opened: list[Composition]
) -> None:
    save_entries(tmp_path, {"estilo": "tabs de 4"})
    delegate = ProviderResponse(
        content="", tool_calls=[ToolCall("d1", "delegar", {"objetivo": "Resume."})]
    )
    answer = ProviderResponse(
        content=json.dumps({"resultado": "ok", "hallazgos_clave": [], "fuentes": []})
    )
    composition, provider = compose_with(
        tmp_path, opened, delegate, answer, DONE, subagents=SubagentSettings(enabled=True)
    )

    await drive(composition, "delega")

    orchestrator = {tool.name for tool in provider.received_tools[0] or []}
    child = {tool.name for tool in provider.received_tools[1] or []}
    assert "memoria" in orchestrator and "memoria" not in child
    assert blocks(provider.received[1]) == [] and len(provider.received[1]) == 1


def test_the_view_of_the_subagents_hides_the_memory_tool(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = compose_with(tmp_path, opened)

    view = RegistryView(composition.registry, {"delegar", "memoria"})

    assert view.get("memoria") is None and composition.registry.get("memoria") is not None
