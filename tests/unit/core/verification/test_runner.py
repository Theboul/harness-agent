"""VerifyingRunner: the turn, the verification and the correction round (HU-11-04.1)."""

from __future__ import annotations

import asyncio

import pytest

from harness_agent.core import (
    CriterionResult,
    CriterionStatus,
    Message,
    NotRunCause,
    Role,
    VerificationReport,
    VerifyingRunner,
    compose_feedback,
)
from harness_agent.core.loop import TurnResult, TurnStatus

SESSION = "sesion-1"
COMPLETED, LIMIT = TurnStatus.COMPLETED, TurnStatus.LIMIT_REACHED


def turn(status: TurnStatus = COMPLETED) -> TurnResult:
    return TurnResult(status=status, final_response="listo", history=())


def result(index: int, status: CriterionStatus, **fields: object) -> CriterionResult:
    return CriterionResult(index=index, description=f"criterio {index}", status=status, **fields)  # type: ignore[arg-type]


FIXABLE = VerificationReport((result(1, CriterionStatus.NOT_MET, exit_code=1, output="mal"),))
DONE = VerificationReport((result(1, CriterionStatus.MET, exit_code=0),))
WAITING = VerificationReport(
    (result(1, CriterionStatus.MET, exit_code=0), result(2, CriterionStatus.PENDING_HUMAN))
)
STUCK = VerificationReport((result(1, CriterionStatus.NOT_RUN, cause=NotRunCause.NO_APPROVER),))


class ScriptedTurns:
    """``run_turn`` that answers from a list and remembers the tasks and the history it saw."""

    def __init__(self, *results: TurnResult) -> None:
        self._results = list(results)
        self.tasks: list[str] = []
        self.histories: list[list[Message]] = []

    async def __call__(self, task: str, history: list[Message]) -> TurnResult:
        self.tasks.append(task)
        self.histories.append(list(history))
        history.append(Message(Role.USER, task))
        return self._results.pop(0)


class ScriptedVerifier:
    def __init__(self, *reports: VerificationReport) -> None:
        self._reports = list(reports)
        self.sessions: list[str] = []

    async def verify(self, session_id: str) -> VerificationReport:
        self.sessions.append(session_id)
        return self._reports.pop(0)


async def test_a_turn_that_did_not_complete_is_not_verified() -> None:
    turns = ScriptedTurns(turn(TurnStatus.PROVIDER_FAILED))
    verifier = ScriptedVerifier()
    runner = VerifyingRunner(turns, verifier, SESSION)

    outcome = await runner.run("haz algo", [])

    assert outcome.status is TurnStatus.PROVIDER_FAILED
    assert verifier.sessions == []


@pytest.mark.parametrize("report", [DONE, WAITING], ids=["verified", "waiting-for-a-person"])
async def test_a_finished_task_ends_after_one_turn(report: VerificationReport) -> None:
    turns = ScriptedTurns(turn())
    verifier = ScriptedVerifier(report)

    outcome = await VerifyingRunner(turns, verifier, SESSION).run("haz algo", [])

    assert outcome.status is COMPLETED
    assert turns.tasks == ["haz algo"] and verifier.sessions == [SESSION]


async def test_something_the_agent_can_fix_opens_a_round_with_the_framed_output() -> None:
    turns = ScriptedTurns(turn(), turn())
    verifier = ScriptedVerifier(FIXABLE, DONE)
    history: list[Message] = []
    feedback = compose_feedback(FIXABLE)
    assert feedback is not None

    outcome = await VerifyingRunner(turns, verifier, SESSION).run("haz algo", history)

    assert outcome.status is COMPLETED
    assert turns.tasks == ["haz algo", feedback.notice]
    external = turns.histories[1][-1]  # what the second turn saw last, before its own task
    assert (external.role, external.content, external.is_external) == (
        Role.USER,
        feedback.external,
        True,
    )
    assert history[-1].content == feedback.notice
    assert len(verifier.sessions) == 2


async def test_a_limit_ends_the_rounds() -> None:
    turns = ScriptedTurns(turn(), turn(LIMIT))
    verifier = ScriptedVerifier(FIXABLE)

    outcome = await VerifyingRunner(turns, verifier, SESSION).run("haz algo", [])

    assert outcome.status is LIMIT
    assert len(verifier.sessions) == 1


async def test_nothing_the_agent_can_fix_does_not_open_a_round() -> None:
    turns = ScriptedTurns(turn())
    verifier = ScriptedVerifier(STUCK)

    outcome = await VerifyingRunner(turns, verifier, SESSION).run("haz algo", [])

    assert outcome.status is COMPLETED and turns.tasks == ["haz algo"]


async def test_the_only_bound_of_the_rounds_is_the_one_of_the_turn() -> None:
    turns = ScriptedTurns(*([turn()] * 5), turn(LIMIT))
    verifier = ScriptedVerifier(*([FIXABLE] * 5))

    outcome = await VerifyingRunner(turns, verifier, SESSION).run("haz algo", [])

    assert outcome.status is LIMIT
    assert len(turns.tasks) == 6 and len(verifier.sessions) == 5


async def test_without_a_verifier_the_turn_passes_through() -> None:
    turns = ScriptedTurns(turn())

    outcome = await VerifyingRunner(turns, None, SESSION).run("haz algo", [])

    assert outcome.status is COMPLETED and turns.tasks == ["haz algo"]


async def test_cancellation_is_never_swallowed() -> None:
    class Cancelling:
        async def verify(self, session_id: str) -> VerificationReport:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await VerifyingRunner(ScriptedTurns(turn()), Cancelling(), SESSION).run("haz algo", [])
