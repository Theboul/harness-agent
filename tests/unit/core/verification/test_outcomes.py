"""Statuses, outcomes, reports and the state of the task (HU-11-04.1)."""

from __future__ import annotations

import pytest

from harness_agent.core import (
    CommandOutcome,
    CriterionResult,
    CriterionStatus,
    NotRunCause,
    TaskState,
    VerificationReport,
    task_state,
)

CUMPLIDO = "cumplido"
PENDIENTE = "pendiente_humano"


def result(index: int, status: CriterionStatus, **fields: object) -> CriterionResult:
    return CriterionResult(index=index, description=f"criterio {index}", status=status, **fields)  # type: ignore[arg-type]


def test_the_values_are_the_ones_of_the_contract() -> None:
    assert [s.value for s in CriterionStatus] == [
        "cumplido",
        "no_cumplido",
        "regresion",
        "no_ejecutado",
        "tiempo_agotado",
        "alterado",
        "pendiente_humano",
    ]
    assert [c.value for c in NotRunCause] == [
        "denegado",
        "sin_aprobador",
        "no_aprobado",
        "condicion_no_soportada",
        "error",
    ]
    assert [s.value for s in TaskState] == ["verificada", "pendiente_humano", "no_terminada"]


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([CUMPLIDO, CUMPLIDO], TaskState.VERIFIED),
        ([CUMPLIDO], TaskState.VERIFIED),
        ([CUMPLIDO, CUMPLIDO, PENDIENTE], TaskState.PENDING_HUMAN),
        ([PENDIENTE], TaskState.PENDING_HUMAN),
        ([CUMPLIDO, "no_cumplido", PENDIENTE], TaskState.NOT_FINISHED),
        (["regresion", CUMPLIDO], TaskState.NOT_FINISHED),
        (["no_ejecutado"], TaskState.NOT_FINISHED),
        (["tiempo_agotado"], TaskState.NOT_FINISHED),
        (["alterado", PENDIENTE], TaskState.NOT_FINISHED),
        (["algo desconocido", CUMPLIDO], TaskState.NOT_FINISHED),
        ([], TaskState.NOT_FINISHED),
        ([CriterionStatus.MET, CriterionStatus.PENDING_HUMAN], TaskState.PENDING_HUMAN),
    ],
)
def test_the_state_of_the_task_follows_the_table(statuses: list[str], expected: TaskState) -> None:
    assert task_state(statuses) is expected


def test_a_value_that_is_not_text_is_never_a_verified_task() -> None:
    assert task_state([CUMPLIDO, 5]) is TaskState.NOT_FINISHED
    assert task_state([None]) is TaskState.NOT_FINISHED


class TestCommandOutcome:
    def test_an_outcome_that_ran(self) -> None:
        outcome = CommandOutcome(ran=True, exit_code=3, output="salida")
        assert (outcome.ran, outcome.exit_code, outcome.timed_out) == (True, 3, False)

    def test_a_timeout_has_no_exit_code(self) -> None:
        outcome = CommandOutcome(ran=True, exit_code=None, timed_out=True, timeout_seconds=120)
        assert outcome.timed_out is True
        with pytest.raises(ValueError):
            CommandOutcome(ran=True, exit_code=0, timed_out=True)

    def test_what_did_not_run_has_no_code_no_output_and_no_timeout(self) -> None:
        assert CommandOutcome(ran=False, exit_code=None).output == ""
        for fields in ({"exit_code": 0}, {"output": "x"}, {"timed_out": True}):
            with pytest.raises(ValueError):
                CommandOutcome(ran=False, **fields)


class TestReport:
    def test_the_state_comes_from_the_results(self) -> None:
        met = result(1, CriterionStatus.MET, exit_code=0)
        pending = result(2, CriterionStatus.PENDING_HUMAN)
        assert VerificationReport((met,)).state is TaskState.VERIFIED
        assert VerificationReport((met, pending)).state is TaskState.PENDING_HUMAN
        failed = result(3, CriterionStatus.NOT_MET, exit_code=1)
        assert VerificationReport((met, pending, failed)).state is TaskState.NOT_FINISHED

    def test_only_what_the_agent_can_fix_is_correctable(self) -> None:
        results = (
            result(1, CriterionStatus.MET, exit_code=0),
            result(2, CriterionStatus.NOT_MET, exit_code=1),
            result(3, CriterionStatus.REGRESSION, exit_code=1),
            result(4, CriterionStatus.TIMED_OUT),
            result(5, CriterionStatus.NOT_RUN, cause=NotRunCause.DENIED),
            result(6, CriterionStatus.TAMPERED),
            result(7, CriterionStatus.PENDING_HUMAN),
        )
        report = VerificationReport(results)
        assert [r.index for r in report.correctable] == [2, 3, 4]

    def test_an_empty_report_is_not_finished(self) -> None:
        assert VerificationReport(()).state is TaskState.NOT_FINISHED
        assert VerificationReport(()).correctable == ()
