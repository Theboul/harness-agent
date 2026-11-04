"""The runner of subagents: one child session, one empty conversation, one brief result (T005).

HU-09-01 AC-01 and AC-02, HU-09-03 AC-01: the loop of the child receives an empty history and the
task; what comes back is the structured result and never the transcript.
"""

from __future__ import annotations

import json

import pytest

from harness_agent.core import Message, Role, SubagentResult, SubagentRunner
from harness_agent.core.subagents.result import RESULT_SCHEMA
from harness_agent.core.subagents.task import build_task
from tests.unit.core.subagents.support import (
    GOAL,
    PARENT,
    SENTINEL,
    FakeSessions,
    FakeTurn,
    answer,
    make_runner,
)

KEYS = ["resultado", "hallazgos_clave", "fuentes", "error", "parcial"]


async def run(runner: SubagentRunner, context: list[Message] | None = None) -> SubagentResult:
    return await runner.execute("general", GOAL, context or [], RESULT_SCHEMA)


def test_the_runner_is_the_port_of_the_core() -> None:
    runner, *_ = make_runner(FakeTurn())

    assert isinstance(runner, SubagentRunner)


async def test_the_child_session_hangs_from_the_active_parent_with_a_one_line_goal() -> None:
    runner, sessions, _, _ = make_runner(FakeTurn(final_response=answer()))

    result = await runner.execute(
        "general", "Primera línea\n\n  segunda   línea", [], RESULT_SCHEMA
    )

    assert sessions.created == [(PARENT, "Primera línea segunda línea")]
    assert result.session_id == "hija-0001"


async def test_the_stored_goal_is_cut_to_a_short_line() -> None:
    runner, sessions, _, _ = make_runner(FakeTurn(final_response=answer()))

    await runner.execute("general", "x" * 1000, [], RESULT_SCHEMA)

    assert len(sessions.created[0][1]) <= 200


async def test_the_child_loop_gets_its_session_the_task_and_an_empty_history() -> None:
    context = [Message(Role.USER, "dato que paso")]
    runner, _, loop, _ = make_runner(FakeTurn(final_response=answer()))

    await run(runner, context)

    session_id, task, history_at_call = loop.calls[0]
    assert session_id == "hija-0001"
    assert task == build_task(GOAL, context, RESULT_SCHEMA)
    assert history_at_call == []  # nothing from the orchestrator: the loop adds the task itself


async def test_every_delegation_gets_its_own_history_and_session() -> None:
    runner, sessions, loop, _ = make_runner(FakeTurn(final_response=answer()))

    first, second = await run(runner), await run(runner)

    assert loop.histories[0] is not loop.histories[1]
    assert (first.session_id, second.session_id) == ("hija-0001", "hija-0002")
    assert [parent for parent, _ in sessions.created] == [PARENT, PARENT]


async def test_a_valid_answer_is_the_structured_result_with_the_five_keys() -> None:
    runner, *_ = make_runner(FakeTurn(final_response=answer()))

    result = await run(runner)

    assert result.is_error is False
    assert list(result.output) == KEYS
    assert result.output == {
        "resultado": "listo",
        "hallazgos_clave": ["uno", "dos"],
        "fuentes": ["a.py"],
        "error": None,
        "parcial": False,
    }


async def test_the_transcript_of_the_child_is_not_in_the_result() -> None:
    transcript = (
        Message(Role.USER, "tarea " + SENTINEL),
        Message(Role.ASSISTANT, "pienso " + SENTINEL),
        Message(Role.TOOL, "contenido de un archivo " + SENTINEL),
    )
    runner, *_ = make_runner(FakeTurn(final_response=answer(), history=transcript))

    result = await run(runner)

    assert SENTINEL not in json.dumps(result.output)


async def test_an_error_that_the_subagent_reports_makes_the_result_an_error() -> None:
    runner, *_ = make_runner(FakeTurn(final_response=answer(error="no encontré el archivo")))

    result = await run(runner)

    assert result.is_error is True
    assert result.output["error"] == "no encontré el archivo" and result.output["parcial"] is False


@pytest.mark.parametrize(
    "final",
    [None, "", "terminé " + SENTINEL, "[1]", answer(extra=SENTINEL), answer(resultado=3)],
    ids=["none", "empty", "prose", "list", "extra-key", "wrong-type"],
)
async def test_an_answer_that_is_not_the_result_is_a_fixed_error_without_copying_it(
    final: str | None,
) -> None:
    runner, *_ = make_runner(FakeTurn(final_response=final))

    result = await run(runner)

    assert result.is_error is True
    assert result.output["error"] == "resultado_no_valido" and result.output["resultado"] == ""
    assert SENTINEL not in json.dumps(result.output)


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("provider_failed", "fallo_del_proveedor"),
        ("invalid_provider_response", "respuesta_invalida_del_proveedor"),
        ("algo_nuevo", "fallo_del_subagente"),
    ],
)
async def test_a_turn_that_failed_gives_a_fixed_code_and_never_its_text(
    status: str, code: str
) -> None:
    runner, *_ = make_runner(FakeTurn(status=status, error="RuntimeError: " + SENTINEL))

    result = await run(runner)

    assert result.is_error is True and result.output["error"] == code
    assert SENTINEL not in json.dumps(result.output)


async def test_an_exception_of_the_loop_is_a_fixed_error_and_the_session_is_reported() -> None:
    runner, *_ = make_runner(RuntimeError(SENTINEL))

    result = await run(runner)

    assert result.is_error is True and result.output["error"] == "fallo_del_subagente"
    assert result.session_id == "hija-0001"
    assert SENTINEL not in json.dumps(result.output)


async def test_without_a_child_session_nothing_runs() -> None:
    runner, _, loop, _ = make_runner(FakeTurn(), sessions=FakeSessions(fail=True))

    result = await run(runner)

    assert loop.calls == []
    assert result.is_error is True and result.session_id == ""
    assert result.output["error"] == "sin_sesion_hija"
    assert SENTINEL not in json.dumps(result.output)


async def test_without_an_active_parent_nothing_runs() -> None:
    def no_parent() -> str:
        raise RuntimeError(SENTINEL)

    runner, sessions, loop, _ = make_runner(FakeTurn(), parent=no_parent)

    result = await run(runner)

    assert loop.calls == [] and sessions.created == []
    assert result.output["error"] == "sin_sesion_hija"


async def test_context_that_is_not_the_persons_is_not_passed_on() -> None:
    context = [
        Message(Role.ASSISTANT, "historial " + SENTINEL),
        Message(Role.USER, "dato externo " + SENTINEL, is_external=True),
        Message(Role.USER, "lo que paso"),
    ]
    runner, _, loop, _ = make_runner(FakeTurn(final_response=answer()))

    await run(runner, context)

    task = loop.calls[0][1]
    assert "lo que paso" in task and SENTINEL not in task
