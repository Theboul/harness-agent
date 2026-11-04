"""The delegation to subagents with the real loop, the real policy chain and a real SQLite file.

HU-09-01 AC-01 and AC-02, HU-09-03 AC-01, HU-09-04 AC-01 and AC-02 (spec 051). The provider is a
``FakeProvider`` whose script has the steps of the orchestrator and of the subagent in the order the
calls happen. Nothing uses the network, a key or the console.
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

from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import SubagentSettings
from harness_agent.core import (
    ApprovalAction,
    EventType,
    Message,
    PermissionRules,
    ProviderResponse,
    Role,
    ToolCall,
)
from tests.doubles import DummyApprover, FakeProvider
from tests.unit.bootstrap_support import build, make_config

PARENT_SENTINEL = "VALOR-DE-PRUEBA-123"
CHILD_SENTINEL = "DATO-DEL-SUBAGENTE-456"
KEY = "sk-" + "abcdefghijklmnopqrstuvwx"
OBJECTIVE = "Resume el archivo a.txt."


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def delegation(call_id: str = "c-del", **arguments: Any) -> ProviderResponse:
    """The step in which the orchestrator asks to delegate."""
    call = ToolCall(call_id, "delegar", {"objetivo": OBJECTIVE, **arguments})
    return ProviderResponse(content="", tool_calls=[call])


def reading(call_id: str, path: str = "a.txt", text: str = "") -> ProviderResponse:
    """The step in which a subagent reads a file of the work area."""
    return ProviderResponse(
        content=text, tool_calls=[ToolCall(call_id, "leer_archivo", {"path": path})]
    )


def writing_outside(call_id: str) -> ProviderResponse:
    """A write outside the work area: the policy asks; the tool would refuse it anyway."""
    arguments = {"path": "../fuera.txt", "content": "x"}
    return ProviderResponse(
        content="", tool_calls=[ToolCall(call_id, "escribir_archivo", arguments)]
    )


def finished(**changes: Any) -> ProviderResponse:
    """The step in which a subagent ends with its structured result."""
    data = {"resultado": "listo", "hallazgos_clave": ["uno"], "fuentes": ["a.txt"], **changes}
    return ProviderResponse(content=json.dumps(data))


def make(
    tmp_path: Path,
    opened: list[Composition],
    *script: ProviderResponse,
    settings: SubagentSettings | None = None,
    permissions: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
    **options: Any,
) -> tuple[Composition, FakeProvider]:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(exist_ok=True)
    (workspace / "a.txt").write_text(f"contenido de a {CHILD_SENTINEL}", encoding="utf-8")
    config = make_config(tmp_path, workspace=workspace, permissions=permissions)
    config = replace(config, subagents=settings or SubagentSettings(enabled=True))
    provider = FakeProvider(script)
    return build(opened, config, provider, system_name="Linux", **options), provider


async def delegate(
    composition: Composition, history: list[Message] | None = None
) -> tuple[list[Message], list[Any]]:
    """Run one request of the orchestrator; return its history and the events of every session."""
    seen: list[Any] = []
    for kind in EventType:
        composition.bus.subscribe(kind, seen.append)
    messages = [] if history is None else history
    await composition.loop.run_turn(
        session_id=composition.session_id, task="delega", history=messages
    )
    return messages, seen


def database(composition: Composition) -> sqlite3.Connection:
    """A new connection to the file: what the process left on the disk."""
    path = composition.store.connection().execute("PRAGMA database_list").fetchone()[2]
    return sqlite3.connect(path)


def result_of(history: list[Message]) -> dict[str, Any]:
    tool_messages = [m for m in history if m.role is Role.TOOL]
    return json.loads(tool_messages[-1].content)  # type: ignore[no-any-return]


PRIOR = [
    Message(Role.USER, f"petición anterior {PARENT_SENTINEL}"),
    Message(Role.ASSISTANT, f"respuesta anterior {PARENT_SENTINEL}"),
]


async def test_the_subagent_starts_with_one_message_that_has_only_the_task(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(tmp_path, opened, delegation(), finished(), finished_text())

    await delegate(composition, list(PRIOR))

    orchestrator, subagent = provider.received[0], provider.received[1]
    assert any(PARENT_SENTINEL in m.content for m in orchestrator)  # it did have the history
    assert len(subagent) == 1 and subagent[0].role is Role.USER  # HU-09-01 AC-01
    assert OBJECTIVE in subagent[0].content
    assert all(PARENT_SENTINEL not in m.content for m in subagent)  # HU-09-01 AC-02
    assert "delegar" not in {tool.name for tool in provider.received_tools[1] or []}


def finished_text() -> ProviderResponse:
    return ProviderResponse(content="hecho")


async def test_the_orchestrator_gets_the_structured_result_and_not_the_transcript(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(
        tmp_path, opened, delegation(), reading("c-read"), finished(), finished_text()
    )

    history, _ = await delegate(composition)

    assert result_of(history) == {
        "resultado": "listo",
        "hallazgos_clave": ["uno"],
        "fuentes": ["a.txt"],
        "error": None,
        "parcial": False,
    }
    # The subagent did read the file (its request after the reading carries the content)...
    assert any(CHILD_SENTINEL in m.content for m in provider.received[2])
    # ...but nothing of what it saw reaches the orchestrator: not its history, not its next request.
    assert all(CHILD_SENTINEL not in m.content for m in history)
    assert all(CHILD_SENTINEL not in m.content for m in provider.received[3])
    assert [m.role for m in history] == [Role.USER, Role.ASSISTANT, Role.TOOL, Role.ASSISTANT]


async def test_the_result_travels_as_external_data(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = make(tmp_path, opened, delegation(), finished(), finished_text())

    history, _ = await delegate(composition)

    tool_message = next(m for m in history if m.role is Role.TOOL)
    assert tool_message.is_external is True and tool_message.tool_result is not None
    assert tool_message.tool_result.is_error is False


async def test_a_secret_of_the_subagent_is_hidden_in_the_result_and_in_what_is_stored(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = make(
        tmp_path,
        opened,
        delegation(contexto_minimo=f"usa {KEY}"),
        finished(
            resultado=f"la clave es {KEY}", fuentes=["https://" + "u:" + KEY + "@host.example/x"]
        ),
        finished_text(),
    )

    history, _ = await delegate(composition)

    assert KEY not in json.dumps([m.content for m in history])
    connection = database(composition)
    stored = "".join(
        str(row)
        for table in ("sessions", "events")
        for row in connection.execute(f"SELECT * FROM {table}")
    )
    assert KEY not in stored  # what reaches the disk is clean (the events in memory are not)


async def test_the_child_session_is_on_the_disk_with_its_parent_and_its_own_events(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = make(
        tmp_path, opened, delegation(), reading("c-read"), finished(), finished_text()
    )
    _, events = await delegate(composition)
    started = next(e for e in events if e.type is EventType.SUBAGENT_STARTED)
    child_id = started.payload["child_session_id"]

    connection = database(composition)
    rows = connection.execute("SELECT id, parent_id, goal, model FROM sessions").fetchall()
    child = next(row for row in rows if row[0] == child_id)
    assert child[1] == composition.session_id  # HU-09-01 rule 2
    assert child[2] == OBJECTIVE and child[3] == composition.model
    kinds = [
        kind
        for (kind,) in connection.execute(
            "SELECT type FROM events WHERE session_id = ? ORDER BY seq", (child_id,)
        )
    ]
    assert kinds.count("tool_requested") == 1 and "assistant_message" in kinds
    parent_kinds = [
        kind
        for (kind,) in connection.execute(
            "SELECT type FROM events WHERE session_id = ? ORDER BY seq", (composition.session_id,)
        )
    ]
    assert "subagent_started" in parent_kinds and "subagent_finished" in parent_kinds
    assert connection.execute(
        "SELECT count(*) FROM mensajes WHERE sesion_id = ?", (child_id,)
    ).fetchone() == (0,)  # a child session keeps no messages: it cannot be resumed


async def test_the_list_of_sessions_leaves_the_child_out_and_it_cannot_be_resumed(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = make(tmp_path, opened, delegation(), finished(), finished_text())
    _, events = await delegate(composition)
    child_id = next(e for e in events if e.type is EventType.SUBAGENT_STARTED).payload[
        "child_session_id"
    ]
    output = io.StringIO()

    await run_session(
        composition,
        input_stream=io.StringIO(f"/sesiones\n/reanudar {child_id}\n/salir\n"),
        output=output,
    )

    shown = output.getvalue()
    assert composition.session_id in shown and child_id not in shown
    assert "Esa sesión se guardó sin el detalle de sus mensajes y no se puede reanudar." in shown
    assert "Sesión reanudada" not in shown


async def test_the_events_of_the_orchestrator_say_how_the_subagent_ended_without_any_text(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = make(tmp_path, opened, delegation(), finished(), finished_text())

    _, events = await delegate(composition)

    ends = [e for e in events if e.type is EventType.SUBAGENT_FINISHED]
    assert len(ends) == 1 and ends[0].session_id == composition.session_id
    assert ends[0].payload["status"] == "completed" and ends[0].payload["is_error"] is False
    assert "listo" not in json.dumps(ends[0].payload)


def sessions_under_a_parent(composition: Composition) -> list[tuple[str, str]]:
    rows = database(composition).execute(
        "SELECT id, parent_id FROM sessions WHERE parent_id IS NOT NULL ORDER BY created_at, id"
    )
    return list(rows)


def kinds_of(events: list[Any], kind: EventType) -> list[Any]:
    return [event for event in events if event.type is kind]


async def test_a_subagent_that_tries_to_delegate_is_rejected_and_no_third_level_exists(
    tmp_path: Path, opened: list[Composition]
) -> None:
    nested = ProviderResponse(
        content="", tool_calls=[ToolCall("c-nested", "delegar", {"objetivo": "otra"})]
    )
    composition, provider = make(
        tmp_path, opened, delegation(), nested, finished(), finished_text()
    )

    history, events = await delegate(composition)

    child_result = next(m for m in provider.received[2] if m.role is Role.TOOL)
    assert child_result.content.startswith("[unknown_tool]")  # HU-09-04 AC-01
    assert len(sessions_under_a_parent(composition)) == 1  # the nested call created nothing
    assert len(kinds_of(events, EventType.SUBAGENT_STARTED)) == 1
    assert result_of(history)["parcial"] is False  # the subagent went on and finished


async def test_reaching_the_turn_limit_of_the_subagent_gives_a_partial_result(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(
        tmp_path,
        opened,
        delegation(),
        reading("c-r1", text="voy leyendo"),
        reading("c-r2"),
        finished_text(),
        settings=SubagentSettings(enabled=True, max_turns=2),
    )

    history, events = await delegate(composition)

    assert result_of(history) == {
        "resultado": "voy leyendo",
        "hallazgos_clave": [],
        "fuentes": [],
        "error": "limite_alcanzado:turns",
        "parcial": True,
    }  # HU-09-04 AC-02
    assert provider.call_count == 4  # the limit stopped the third call of the subagent
    [stop] = kinds_of(events, EventType.LIMIT_REACHED)
    child_id = kinds_of(events, EventType.SUBAGENT_STARTED)[0].payload["child_session_id"]
    assert stop.session_id == child_id and stop.session_id != composition.session_id
    assert stop.payload == {"limit": "turns", "used": 2, "maximum": 2}
    tool_message = next(m for m in history if m.role is Role.TOOL)
    assert tool_message.tool_result is not None and tool_message.tool_result.is_error is False
    [end] = kinds_of(events, EventType.SUBAGENT_FINISHED)
    assert end.payload["status"] == "partial" and end.payload["partial"] is True


async def test_the_limits_of_the_subagent_and_the_ones_of_the_orchestrator_do_not_mix(
    tmp_path: Path, opened: list[Composition]
) -> None:
    # The orchestrator may make 2 calls and the subagent 3: five calls in all would break a
    # counter that was shared.
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    (workspace / "a.txt").write_text("contenido", encoding="utf-8")
    config = make_config(tmp_path, workspace=workspace)
    config = replace(
        config,
        limits=replace(config.limits, max_turns=2),
        subagents=SubagentSettings(enabled=True, max_turns=3),
    )
    script = [delegation(), reading("c-r1"), reading("c-r2"), finished(), finished_text()]
    provider = FakeProvider(script)
    composition = build(opened, config, provider, system_name="Linux")

    history, events = await delegate(composition)

    assert provider.call_count == 5 and not kinds_of(events, EventType.LIMIT_REACHED)
    assert result_of(history)["parcial"] is False
    assert history[-1].role is Role.ASSISTANT and history[-1].content == "hecho"


async def test_a_final_answer_that_is_not_the_result_reaches_the_orchestrator_as_an_error(
    tmp_path: Path, opened: list[Composition]
) -> None:
    prose = ProviderResponse(content=f"terminé, mira {CHILD_SENTINEL}")
    composition, _ = make(tmp_path, opened, delegation(), prose, finished_text())

    history, _ = await delegate(composition)

    message = next(m for m in history if m.role is Role.TOOL)
    assert message.tool_result is not None and message.tool_result.is_error is True
    assert json.loads(message.content)["error"] == "resultado_no_valido"
    assert CHILD_SENTINEL not in message.content


async def test_what_the_subagent_needs_approved_goes_to_the_person_saying_who_asks(
    tmp_path: Path, opened: list[Composition]
) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_SESSION)
    composition, _ = make(
        tmp_path,
        opened,
        delegation(),
        writing_outside("c-w1"),
        finished(),
        writing_outside("c-w2"),
        finished_text(),
        approver=approver,
    )

    _, events = await delegate(composition)

    asked = approver.recorded_requests
    assert (
        len(asked) == 2
    )  # the approval "for the session" of the subagent is not the orchestrator's
    first, second = asked[0][1], asked[1][1]
    child_id = kinds_of(events, EventType.SUBAGENT_STARTED)[0].payload["child_session_id"]
    assert first["requested_by"] == f"subagente {child_id[:8]}"
    assert "requested_by" not in second  # the orchestrator asks as itself
    requests = kinds_of(events, EventType.APPROVAL_REQUESTED)
    assert [e.session_id for e in requests] == [child_id, composition.session_id]


async def test_a_rejection_of_the_person_reaches_the_subagent_and_it_goes_on(
    tmp_path: Path, opened: list[Composition]
) -> None:
    approver = DummyApprover(ApprovalAction.REJECT, "no")
    composition, provider = make(
        tmp_path,
        opened,
        delegation(),
        writing_outside("c-w1"),
        finished(),
        finished_text(),
        approver=approver,
    )

    history, _ = await delegate(composition)

    rejected = next(m for m in provider.received[2] if m.role is Role.TOOL)
    assert rejected.content.startswith("[approval_rejected]")
    assert result_of(history)["parcial"] is False


async def test_without_an_approver_what_asks_is_denied_for_the_subagent_too(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, provider = make(
        tmp_path, opened, delegation(), writing_outside("c-w1"), finished(), finished_text()
    )

    await delegate(composition)

    denied = next(m for m in provider.received[2] if m.role is Role.TOOL)
    assert denied.content.startswith("[approval_required_unavailable]")


async def test_the_deny_of_the_configuration_binds_the_subagent_as_it_binds_the_orchestrator(
    tmp_path: Path, opened: list[Composition]
) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    composition, provider = make(
        tmp_path,
        opened,
        delegation(),
        writing_outside("c-w1"),
        finished(),
        finished_text(),
        permissions=PermissionRules(deny=("escribir_archivo",)),
        approver=approver,
    )

    await delegate(composition)

    denied = next(m for m in provider.received[2] if m.role is Role.TOOL)
    assert denied.content.startswith("[permission_denied]")
    assert approver.recorded_requests == []  # a denial never reaches the person


async def test_the_read_only_mode_turned_on_during_the_delegation_binds_the_subagent(
    tmp_path: Path, opened: list[Composition]
) -> None:
    holder: list[Composition] = []

    class Flipping(FakeProvider):
        async def complete(self, messages: list[Message], tools: Any = None) -> ProviderResponse:
            if self.call_count == 1 and holder[0].read_only_switch is not None:
                holder[0].read_only_switch.enable()  # the person types /plan while it runs
            return await super().complete(messages, tools)

    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    config = replace(
        make_config(tmp_path, workspace=workspace), subagents=SubagentSettings(enabled=True)
    )
    inside = ProviderResponse(
        content="",
        tool_calls=[ToolCall("c-w1", "escribir_archivo", {"path": "n.txt", "content": "x"})],
    )
    provider = Flipping([delegation(), inside, finished(), finished_text()])
    composition = build(opened, config, provider, system_name="Linux")
    holder.append(composition)

    await delegate(composition)

    denied = next(m for m in provider.received[2] if m.role is Role.TOOL)
    assert denied.content.startswith("[permission_denied]")
    assert not (workspace / "n.txt").exists()


async def test_two_delegations_in_a_row_get_two_sessions_under_the_same_parent(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = make(
        tmp_path,
        opened,
        delegation("c-d1"),
        finished(resultado="uno"),
        delegation("c-d2"),
        finished(resultado="dos"),
        finished_text(),
    )

    history, events = await delegate(composition)

    rows = sessions_under_a_parent(composition)
    assert len(rows) == 2 and {parent for _, parent in rows} == {composition.session_id}
    tool_results = [json.loads(m.content)["resultado"] for m in history if m.role is Role.TOOL]
    assert tool_results == ["uno", "dos"]
    assert len(kinds_of(events, EventType.SUBAGENT_STARTED)) == 2


async def test_arguments_the_schema_rejects_create_no_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    bad = ProviderResponse(content="", tool_calls=[ToolCall("c-bad", "delegar", {"objetivo": ""})])
    composition, provider = make(tmp_path, opened, bad, finished_text())

    await delegate(composition)

    rejected = next(m for m in provider.received[1] if m.role is Role.TOOL)
    assert rejected.content.startswith("[invalid_arguments]")
    assert sessions_under_a_parent(composition) == []
