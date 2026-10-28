"""compose() and run_session() save the messages of the conversation (HU-03-04 / T009).

The provider is a ``FakeProvider``; the database is a temporary file. The spies record the order in
which the messages and the events reach the store: a message must be saved before its event.
"""

from __future__ import annotations

import io
from collections.abc import Iterator, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.storage import SqliteMessageStore, SqliteSessionStore
from harness_agent.bootstrap import Composition, run_session
from harness_agent.core import (
    Event,
    EventType,
    MessageRecord,
    ProviderResponse,
    ToolCall,
)
from tests.doubles import FakeProvider
from tests.integration.test_essential_context_agent_loop import make_task
from tests.unit.bootstrap_support import SENTINEL, build, make_config, one_turn

FIXED = "No se pudo guardar un mensaje de la conversación; la sesión no podrá reanudarse."
MODEL = "openai/modelo-de-prueba"
READ = ToolCall("c1", "leer_archivo", {"path": "a.txt"})


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


@pytest.fixture
def trail(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Every message and event the store receives, in order, and what comes after."""
    seen: list[tuple[str, str]] = []

    class SpyStore(SqliteSessionStore):
        def save_event(self, event: Event) -> None:
            seen.append(("event", event.id))
            super().save_event(event)

    class SpyMessages(SqliteMessageStore):
        def append(self, session_id: str, records: Sequence[MessageRecord]) -> None:
            seen.extend(("message", record.event_id or "-") for record in records)
            super().append(session_id, records)

    monkeypatch.setattr(bootstrap, "SqliteSessionStore", SpyStore)
    monkeypatch.setattr(bootstrap, "SqliteMessageStore", SpyMessages)
    return seen


def make(tmp_path: Path, opened: list[Composition], script: list[ProviderResponse]) -> Composition:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    (workspace / "a.txt").write_text("contenido de a", encoding="utf-8")
    config = make_config(tmp_path, workspace=workspace, model=MODEL)
    return build(opened, config, FakeProvider(script), system_name="Linux")


async def drive(composition: Composition, *lines: str) -> tuple[int, str]:
    output = io.StringIO()
    code = await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{x}\n" for x in (*lines, "/salir"))),
        output=output,
    )
    return code, output.getvalue()


def rows(composition: Composition) -> list[tuple[int, str, str | None]]:
    cursor = composition.store.connection().execute(
        "SELECT posicion, rol, evento_id FROM mensajes ORDER BY posicion"
    )
    return [(p, r, e) for p, r, e in cursor]


TOOL_TURN = [
    ProviderResponse(content="", tool_calls=[READ]),
    ProviderResponse(content="listo"),
]


async def test_a_message_is_saved_before_its_event_and_before_the_terminal(
    tmp_path: Path, opened: list[Composition], trail: list[tuple[str, str]]
) -> None:
    composition = make(tmp_path, opened, TOOL_TURN)
    for kind in (
        EventType.USER_MESSAGE,
        EventType.ASSISTANT_MESSAGE,
        EventType.TOOL_REQUESTED,
        EventType.TOOL_FINISHED,
    ):  # what the terminal does: subscribe after the recorder
        composition.bus.subscribe(kind, lambda event: trail.append(("cli", event.id)))

    code, _ = await drive(composition, "lee a.txt")

    assert code == 0
    with_event = [e for kind, e in trail if kind == "message" and e != "-"]
    assert len(with_event) == 3  # the request, the result and the final answer
    for event_id in with_event:
        message = trail.index(("message", event_id))
        event = trail.index(("event", event_id))
        terminal = trail.index(("cli", event_id))
        assert message < event < terminal
    assert ("message", "-") in trail  # the answer that only asks for the tool, with no event


async def test_the_messages_of_a_turn_with_tools_are_saved_in_order(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = make(tmp_path, opened, TOOL_TURN)

    await drive(composition, "lee a.txt")

    stored = rows(composition)
    assert [(p, r) for p, r, _ in stored] == [
        (1, "user"),
        (2, "assistant"),
        (3, "tool"),
        (4, "assistant"),
    ]
    assert [e is None for _, _, e in stored] == [False, True, False, False]


async def test_a_final_empty_answer_is_saved_when_the_turn_closes(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = make(tmp_path, opened, [ProviderResponse(content="")])

    await drive(composition, "hola")

    assert [(p, r, e is None) for p, r, e in rows(composition)] == [
        (1, "user", False),
        (2, "assistant", True),
    ]


async def test_the_numbering_starts_after_what_the_session_already_has(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = make(tmp_path, opened, [ProviderResponse(content="uno")])
    await drive(composition, "hola")

    assert [p for p, _, _ in rows(composition)] == [1, 2]
    assert composition.messages is not None
    assert composition.messages.last_position(composition.session_id) == 2


async def test_the_capture_is_inert_when_the_loop_is_driven_without_run_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = make(tmp_path, opened, [ProviderResponse(content="uno")])

    await one_turn(composition)

    assert rows(composition) == []
    assert composition.capture is not None and composition.capture.session_id is None


async def test_run_session_binds_the_capture_to_its_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = make(tmp_path, opened, [ProviderResponse(content="uno")])

    await drive(composition, "hola")

    assert composition.capture is not None
    assert composition.capture.session_id == composition.session_id


async def test_a_store_that_fails_stops_the_turn_with_one_fixed_notice_and_the_event_is_kept(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    class Failing(SqliteMessageStore):
        calls = 0

        def append(self, session_id: str, records: Sequence[MessageRecord]) -> None:
            Failing.calls += 1
            if Failing.calls == 2:
                raise RuntimeError(SENTINEL)
            super().append(session_id, records)

    monkeypatch.setattr(bootstrap, "SqliteMessageStore", Failing)
    composition = make(tmp_path, opened, TOOL_TURN)

    code, shown = await drive(composition, "lee a.txt")

    assert code == 1
    assert shown.count(FIXED) == 1 and SENTINEL not in shown
    assert "EventDeliveryError" in shown  # the type of the failure, as for any failed delivery
    assert [(p, r) for p, r, _ in rows(composition)] == [(1, "user")]
    stored = composition.store.connection().execute("SELECT type FROM events ORDER BY seq")
    assert "tool_requested" in [t for (t,) in stored]  # the recorder still saved the event
    assert composition.capture is not None
    assert composition.capture.incomplete_sessions == frozenset({composition.session_id})


async def test_a_session_with_a_task_does_not_save_its_messages(
    tmp_path: Path, opened: list[Composition]
) -> None:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    config = replace(make_config(tmp_path, workspace=workspace, model=MODEL))
    composition = build(
        opened,
        config,
        FakeProvider([ProviderResponse(content="listo")]),
        task=make_task(),
        system_name="Linux",
    )

    await one_turn(composition)

    assert composition.capture is None and composition.messages is None
    assert rows(composition) == []
