"""The runner: partial result at a limit, events, secrets and cancellation (T006).

HU-09-04 AC-02: a subagent that reaches its limit ends and the orchestrator gets a partial result.
"""

from __future__ import annotations

import asyncio
import json
from typing import cast

import pytest

from harness_agent.core import EventType, Message, Role, SubagentResult, redact_secrets
from harness_agent.core.subagents.result import RESULT_SCHEMA
from tests.unit.core.subagents.support import (
    GOAL,
    PARENT,
    SENTINEL,
    FakeSessions,
    FakeTurn,
    RecordingBus,
    answer,
    make_runner,
)

KEY = "sk-" + "abcdefghijklmnopqrstuvwx"
LIMIT = "Session limit 'turns' reached (2 of 2)."


async def run(runner: object) -> SubagentResult:
    return await runner.execute("general", GOAL, [], RESULT_SCHEMA)  # type: ignore[attr-defined, no-any-return]


def stopped(history: tuple[Message, ...] = ()) -> FakeTurn:
    return FakeTurn(status="limit_reached", error=LIMIT, history=history)


async def test_a_limit_ends_the_subagent_with_a_partial_result_not_an_error() -> None:
    history = (
        Message(Role.USER, "tarea"),
        Message(Role.ASSISTANT, "avance parcial"),
        Message(Role.TOOL, "contenido " + SENTINEL),
        Message(Role.ASSISTANT, ""),
    )
    runner, *_ = make_runner(stopped(history))

    result = await run(runner)

    assert result.is_error is False
    assert result.output == {
        "resultado": "avance parcial",
        "hallazgos_clave": [],
        "fuentes": [],
        "error": "limite_alcanzado:turns",
        "parcial": True,
    }
    assert SENTINEL not in json.dumps(result.output)


async def test_a_partial_result_without_any_text_of_the_child_has_an_empty_result() -> None:
    runner, *_ = make_runner(stopped((Message(Role.USER, "tarea"),)))

    result = await run(runner)

    assert result.output["resultado"] == "" and result.output["parcial"] is True


async def test_a_limit_the_turn_does_not_name_is_still_a_partial_result() -> None:
    runner, *_ = make_runner(FakeTurn(status="limit_reached", error=None))

    result = await run(runner)

    assert result.output["error"] == "limite_alcanzado" and result.output["parcial"] is True


async def test_the_start_and_the_end_are_published_in_the_session_of_the_orchestrator() -> None:
    runner, _, _, bus = make_runner(FakeTurn(final_response=answer()))

    await run(runner)

    events = cast(RecordingBus, bus).events
    assert [(e.type, e.session_id) for e in events] == [
        (EventType.SUBAGENT_STARTED, PARENT),
        (EventType.SUBAGENT_FINISHED, PARENT),
    ]
    assert events[0].payload == {"child_session_id": "hija-0001", "profile": "general"}
    assert events[1].payload == {
        "child_session_id": "hija-0001",
        "status": "completed",
        "is_error": False,
        "partial": False,
    }


@pytest.mark.parametrize(
    ("outcome", "status", "is_error", "partial"),
    [
        (stopped(), "partial", False, True),
        (FakeTurn(final_response="no es json"), "failed", True, False),
        (FakeTurn(status="provider_failed"), "failed", True, False),
        (RuntimeError(SENTINEL), "failed", True, False),
    ],
    ids=["limit", "invalid-result", "provider", "exception"],
)
async def test_the_end_event_says_how_it_ended_without_any_text(
    outcome: FakeTurn | BaseException, status: str, is_error: bool, partial: bool
) -> None:
    runner, _, _, bus = make_runner(outcome)

    await run(runner)

    finished = cast(RecordingBus, bus).events[-1]
    assert finished.type is EventType.SUBAGENT_FINISHED
    assert finished.payload == {
        "child_session_id": "hija-0001",
        "status": status,
        "is_error": is_error,
        "partial": partial,
    }
    assert SENTINEL not in json.dumps(finished.payload)


async def test_a_subscriber_that_fails_does_not_stop_the_delegation() -> None:
    bus = RecordingBus(frozenset({EventType.SUBAGENT_STARTED, EventType.SUBAGENT_FINISHED}))
    runner, *_ = make_runner(FakeTurn(final_response=answer()), bus=bus)

    result = await run(runner)

    assert result.is_error is False and result.output["resultado"] == "listo"
    assert SENTINEL not in json.dumps(result.output)


async def test_secrets_are_hidden_in_every_text_of_the_result_and_in_the_stored_goal() -> None:
    final = answer(
        resultado=f"la clave es {KEY}",
        hallazgos_clave=[f"token {KEY}", "normal"],
        fuentes=["https://" + "usuario:" + KEY + "@host.example/ruta"],
        error=f"falló con {KEY}",
    )
    runner, sessions, *_ = make_runner(FakeTurn(final_response=final), redact=redact_secrets)

    result = await runner.execute("general", f"usa la clave {KEY}", [], RESULT_SCHEMA)

    assert KEY not in json.dumps(result.output)
    assert result.output["hallazgos_clave"][1] == "normal"
    assert KEY not in sessions.created[0][1]
    assert result.output["parcial"] is False and result.is_error is True


async def test_a_secret_in_a_partial_result_is_hidden_too() -> None:
    history = (Message(Role.ASSISTANT, f"probé con {KEY}"),)
    runner, *_ = make_runner(stopped(history), redact=redact_secrets)

    result = await run(runner)

    assert KEY not in json.dumps(result.output)


async def test_the_fixed_codes_are_not_changed_by_the_redaction() -> None:
    runner, *_ = make_runner(FakeTurn(final_response="no es json"), redact=redact_secrets)

    result = await run(runner)

    assert result.output["error"] == "resultado_no_valido"


async def test_a_cancellation_goes_up_and_the_end_is_not_published() -> None:
    runner, _, _, bus = make_runner(asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await run(runner)

    assert [e.type for e in cast(RecordingBus, bus).events] == [EventType.SUBAGENT_STARTED]


async def test_two_delegations_in_a_row_each_get_their_own_session_under_the_same_parent() -> None:
    sessions = FakeSessions()
    runner, *_ = make_runner(FakeTurn(final_response=answer()), sessions=sessions)

    first, second = await run(runner), await run(runner)

    assert first.session_id != second.session_id
    assert [parent for parent, _ in sessions.created] == [PARENT, PARENT]
