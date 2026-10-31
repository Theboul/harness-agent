"""CriteriaVerifier: the matrix of cases, the call it makes and what it publishes (HU-11-04.1).

A real ``SqliteTaskStore`` in ``tmp_path`` keeps the criteria; the policy, the runner and the
approver are small stand-ins defined here. The runner records what it is asked to run and runs
nothing: a denied or asked command never reaches a real interpreter.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.storage import SqliteTaskStore
from harness_agent.core import (
    ApprovalAction,
    ApprovalGate,
    CommandOutcome,
    Confirmation,
    CriteriaVerifier,
    CriterionDefinition,
    CriterionStatus,
    EventType,
    NotRunCause,
    PermissionDecision,
    PermissionPolicy,
    TaskDefinition,
    TaskState,
    ToolCall,
)
from tests.doubles import DummyApprover, DummyTool
from tests.unit.adapters.storage.task_support import (
    RecordingBus,
    open_session_store,
    raw,
    sequential_ids,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
OUTPUT_SENTINEL = "SALIDA-DE-PRUEBA-456"
CREDENTIAL = (
    "https://" + "usuario-de-prueba" + ":" + "secreto-de-prueba" + "@servidor.example/r.git"
)
ALLOW, ASK, DENY = PermissionDecision.ALLOW, PermissionDecision.ASK, PermissionDecision.DENY
CONDITION = "codigo_salida == 0"

Emitted = list[tuple[EventType, dict[str, Any]]]


class StubPolicy(PermissionPolicy):
    """Decides by command text; anything not listed is asked, like the shell."""

    def __init__(self, decisions: dict[str, object] | None = None) -> None:
        self._decisions = decisions or {}
        self.calls: list[ToolCall] = []

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        self.calls.append(call)
        decision = self._decisions.get(call.arguments["command"], ASK)
        if isinstance(decision, BaseException):
            raise decision
        return decision  # type: ignore[return-value]


class ScriptedRunner:
    """Answers by command: a list is consumed one outcome per call; the last one repeats."""

    def __init__(self, outcomes: dict[str, list[CommandOutcome]] | None = None) -> None:
        self._outcomes = outcomes or {}
        self.calls: list[ToolCall] = []

    async def __call__(self, call: ToolCall) -> CommandOutcome:
        self.calls.append(call)
        queue = self._outcomes.get(call.arguments["command"], [ok()])
        return queue.pop(0) if len(queue) > 1 else queue[0]


def ok(output: str = "bien") -> CommandOutcome:
    return CommandOutcome(ran=True, exit_code=0, output=output)


def failed(code: int = 1, output: str = "mal") -> CommandOutcome:
    return CommandOutcome(ran=True, exit_code=code, output=output)


def criteria(*commands: str | None) -> tuple[CriterionDefinition, ...]:
    return tuple(
        CriterionDefinition(f"criterio {i}", command, None if command is None else CONDITION)
        for i, command in enumerate(commands, start=1)
    )


def task_of(*commands: str | None) -> TaskDefinition:
    return TaskDefinition(None, "objetivo", "", "", criteria(*commands))


class Rig:
    def __init__(
        self,
        tmp_path: Path,
        commands: tuple[str | None, ...],
        *,
        policy: StubPolicy | None = None,
        runner: ScriptedRunner | None = None,
        gate: ApprovalGate | None = None,
        declared: dict[str, int] | None = None,
        stored: tuple[str | None, ...] | None = None,
    ) -> None:
        self.bus = RecordingBus()
        self.sessions = open_session_store(tmp_path)
        self.store = SqliteTaskStore(
            self.sessions,
            exports_dir=tmp_path / "exp",
            bus=self.bus,
            id_factory=sequential_ids("id"),
        )
        self.session_id = self.store.start_task(
            task_of(*(commands if stored is None else stored))
        ).session_id
        self.policy = policy or StubPolicy({c: ALLOW for c in commands if c})
        self.runner = runner or ScriptedRunner()
        self.emitted: Emitted = []
        self.marks: list[tuple[str, str]] = []
        original = self.store.mark_passes

        def spy(criteria_id: str, evidence: str) -> None:
            self.marks.append((criteria_id, evidence))
            original(criteria_id, evidence)

        self.store.mark_passes = spy  # type: ignore[method-assign]
        self.verifier = CriteriaVerifier(
            self.store,
            task_of(*commands),
            self.policy,
            DummyTool("shell"),
            self.runner,
            lambda kind, payload: self.emitted.append((kind, payload)),
            gate=gate,
            tool_name="shell",
            command_argument="command",
            timeout_argument="timeout_seconds",
            declared_timeouts=declared,
        )

    def passes(self) -> list[bool]:
        return [item.passes for item in self.store.load_criteria(self.session_id)]

    def of(self, kind: EventType) -> list[dict[str, Any]]:
        return [payload for event, payload in self.emitted if event is kind]

    def everything_published(self) -> str:
        events = [payload for _, payload in self.emitted] + [e.payload for e in self.bus.events]
        return json.dumps(events, ensure_ascii=False)


@pytest.fixture
def make(tmp_path: Path) -> Callable[..., Rig]:
    def build(*commands: str | None, **options: Any) -> Rig:
        return Rig(tmp_path, commands, **options)

    return build


# --- the matrix of cases of the spec --------------------------------------------------------------


async def test_all_the_criteria_are_met(make: Callable[..., Rig]) -> None:
    rig = make("check-a", "check-b", runner=ScriptedRunner({"check-a": [ok("a bien")]}))

    report = await rig.verifier.verify(rig.session_id)

    assert [r.status for r in report.results] == [CriterionStatus.MET] * 2
    assert report.state is TaskState.VERIFIED
    assert rig.passes() == [True, True]
    assert len(rig.marks) == 2
    assert rig.marks[0][1].startswith("Código de salida: 0\na bien")
    assert "check-a" not in rig.marks[0][1]


async def test_the_objective_ones_are_met_and_there_is_a_semantic_one(
    make: Callable[..., Rig],
) -> None:
    rig = make("check-a", "check-b", None)

    report = await rig.verifier.verify(rig.session_id)

    assert [r.status for r in report.results] == [
        CriterionStatus.MET,
        CriterionStatus.MET,
        CriterionStatus.PENDING_HUMAN,
    ]
    assert report.state is TaskState.PENDING_HUMAN
    assert rig.passes() == [True, True, False]
    assert len(rig.runner.calls) == 2 and len(rig.policy.calls) == 2


async def test_one_that_fails_is_not_met_and_stays_false(make: Callable[..., Rig]) -> None:
    rig = make("check-a", "check-b", runner=ScriptedRunner({"check-b": [failed(3, "roto")]}))

    report = await rig.verifier.verify(rig.session_id)

    second = report.results[1]
    assert (second.status, second.exit_code, second.output) == (CriterionStatus.NOT_MET, 3, "roto")
    assert rig.passes() == [True, False]
    assert report.state is TaskState.NOT_FINISHED
    assert report.correctable == (second,)


async def test_a_regression_is_reported_and_passes_is_not_revoked(make: Callable[..., Rig]) -> None:
    runner = ScriptedRunner({"check-b": [ok(), failed(2, "volvió a fallar")]})
    rig = make("check-a", "check-b", runner=runner)

    first = await rig.verifier.verify(rig.session_id)
    marks_after_first = len(rig.marks)
    second = await rig.verifier.verify(rig.session_id)

    assert first.state is TaskState.VERIFIED and marks_after_first == 2
    assert [r.status for r in second.results] == [CriterionStatus.MET, CriterionStatus.REGRESSION]
    assert (second.results[1].exit_code, second.results[1].output) == (2, "volvió a fallar")
    assert second.state is TaskState.NOT_FINISHED
    assert rig.passes() == [True, True]  # not revoked
    assert len(rig.marks) == marks_after_first  # nothing is marked again


async def test_every_objective_criterion_runs_in_every_round(make: Callable[..., Rig]) -> None:
    rig = make("check-a", "check-b")

    await rig.verifier.verify(rig.session_id)
    await rig.verifier.verify(rig.session_id)

    assert [c.arguments["command"] for c in rig.runner.calls] == ["check-a", "check-b"] * 2


async def test_a_command_that_differs_from_the_stored_one_is_tampering(
    make: Callable[..., Rig],
) -> None:
    rig = make("check-x " + SENTINEL, "check-b", stored=("check-a", "check-b"))

    report = await rig.verifier.verify(rig.session_id)

    assert report.results[0].status is CriterionStatus.TAMPERED
    assert report.results[1].status is CriterionStatus.MET
    assert [c.arguments["command"] for c in rig.runner.calls] == ["check-b"]
    assert rig.passes() == [False, True]
    assert rig.of(EventType.CRITERIA_TAMPERED) == [{"motivo": "comando_no_coincide"}]
    published = rig.everything_published()
    assert SENTINEL not in published and "check-x" not in published and "check-a" not in published


async def test_a_semantic_definition_over_a_stored_command_is_tampering(
    make: Callable[..., Rig],
) -> None:
    rig = make(None, stored=("check-a",))

    report = await rig.verifier.verify(rig.session_id)

    assert report.results[0].status is CriterionStatus.TAMPERED
    assert rig.runner.calls == []


async def test_a_different_number_of_criteria_is_tampering(make: Callable[..., Rig]) -> None:
    rig = make("check-a", "check-b", None, stored=("check-a", "check-b"))

    report = await rig.verifier.verify(rig.session_id)

    assert [r.status for r in report.results] == [
        CriterionStatus.TAMPERED,
        CriterionStatus.TAMPERED,
        CriterionStatus.PENDING_HUMAN,
    ]
    assert rig.runner.calls == [] and rig.policy.calls == []
    assert rig.of(EventType.CRITERIA_TAMPERED) == [{"motivo": "criterios_no_coinciden"}]


async def test_a_tampered_database_makes_every_objective_criterion_tampered(
    make: Callable[..., Rig],
) -> None:
    rig = make("check-a", None, "check-b")
    connection = raw(rig.sessions)
    connection.execute("UPDATE criterios SET comando = 'otro' WHERE orden = 1")
    connection.commit()

    report = await rig.verifier.verify(rig.session_id)

    assert [r.status for r in report.results] == [
        CriterionStatus.TAMPERED,
        CriterionStatus.PENDING_HUMAN,
        CriterionStatus.TAMPERED,
    ]
    assert rig.runner.calls == [] and rig.marks == []


async def test_a_question_without_an_approver_is_not_run(make: Callable[..., Rig]) -> None:
    rig = make("check-a", policy=StubPolicy({"check-a": ASK}))

    report = await rig.verifier.verify(rig.session_id)

    assert report.results[0].status is CriterionStatus.NOT_RUN
    assert report.results[0].cause is NotRunCause.NO_APPROVER
    assert rig.runner.calls == [] and rig.passes() == [False]


async def test_a_denied_command_never_reaches_the_approver_or_the_runner(
    make: Callable[..., Rig],
) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    rig = make("check-a", policy=StubPolicy({"check-a": DENY}), gate=ApprovalGate(approver))

    report = await rig.verifier.verify(rig.session_id)

    assert report.results[0].cause is NotRunCause.DENIED
    assert approver.recorded_requests == []
    assert rig.runner.calls == [] and rig.of(EventType.APPROVAL_REQUESTED) == []


async def test_a_command_that_times_out_is_not_met(make: Callable[..., Rig]) -> None:
    timeout = CommandOutcome(
        ran=True, exit_code=None, timed_out=True, output="a medias", timeout_seconds=120
    )
    rig = make("check-a", runner=ScriptedRunner({"check-a": [timeout]}))

    report = await rig.verifier.verify(rig.session_id)

    result = report.results[0]
    assert (result.status, result.exit_code, result.timeout_seconds) == (
        CriterionStatus.TIMED_OUT,
        None,
        120,
    )
    assert result.output == "a medias"
    assert rig.passes() == [False]


async def test_a_criterion_without_a_command_is_pending_and_asks_nothing(
    make: Callable[..., Rig],
) -> None:
    rig = make(None, None)

    report = await rig.verifier.verify(rig.session_id)

    assert [r.status for r in report.results] == [CriterionStatus.PENDING_HUMAN] * 2
    assert report.state is TaskState.PENDING_HUMAN
    assert rig.policy.calls == [] and rig.runner.calls == [] and rig.marks == []


# --- the permission policy and the approver -------------------------------------------------------


async def test_the_call_has_the_form_of_the_one_of_the_agent(make: Callable[..., Rig]) -> None:
    rig = make("check-a", "check-b", declared={"check-b": 300})

    await rig.verifier.verify(rig.session_id)

    first, second = rig.policy.calls
    assert (first.id, first.name, first.arguments) == (
        "verificacion-1",
        "shell",
        {"command": "check-a"},
    )
    assert (second.id, second.arguments) == (
        "verificacion-2",
        {"command": "check-b", "timeout_seconds": 300},
    )
    assert rig.runner.calls == rig.policy.calls


async def test_the_person_decides_what_the_policy_asks(make: Callable[..., Rig]) -> None:
    approver = DummyApprover(ApprovalAction.REJECT, "no quiero " + SENTINEL)
    rig = make("check-a", policy=StubPolicy({"check-a": ASK}), gate=ApprovalGate(approver))

    report = await rig.verifier.verify(rig.session_id)

    assert report.results[0].cause is NotRunCause.NOT_APPROVED
    assert len(approver.recorded_requests) == 1 and rig.runner.calls == []
    assert SENTINEL not in rig.everything_published()  # the reason is not forwarded


async def test_an_approved_question_runs_once(make: Callable[..., Rig]) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    rig = make("check-a", policy=StubPolicy({"check-a": ASK}), gate=ApprovalGate(approver))

    first = await rig.verifier.verify(rig.session_id)
    second = await rig.verifier.verify(rig.session_id)

    assert first.results[0].status is CriterionStatus.MET
    assert second.results[0].status is CriterionStatus.MET
    assert len(approver.recorded_requests) == 2  # asked again every round


async def test_a_session_approval_is_not_asked_again(make: Callable[..., Rig]) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_SESSION)
    rig = make("check-a", policy=StubPolicy({"check-a": ASK}), gate=ApprovalGate(approver))

    await rig.verifier.verify(rig.session_id)
    await rig.verifier.verify(rig.session_id)

    assert len(approver.recorded_requests) == 1 and len(rig.runner.calls) == 2


@pytest.mark.parametrize("decision", [RuntimeError(SENTINEL), "allow", None, 5])
async def test_a_policy_that_fails_or_answers_nonsense_denies(
    make: Callable[..., Rig], decision: object
) -> None:
    rig = make("check-a", policy=StubPolicy({"check-a": decision}))

    report = await rig.verifier.verify(rig.session_id)

    assert report.results[0].cause is NotRunCause.DENIED
    assert rig.runner.calls == []
    decided = rig.of(EventType.PERMISSION_DECIDED)[0]
    assert (decided["decision"], decided["resolved_as"], decided["reason"]) == (
        "deny",
        "deny",
        "policy_error",
    )
    assert SENTINEL not in rig.everything_published()


async def test_an_unsupported_condition_is_not_run(
    make: Callable[..., Rig], tmp_path: Path
) -> None:
    rig = make("check-a")
    odd = TaskDefinition(None, "o", "", "", (CriterionDefinition("a", "check-a", "ok"),))
    rig.verifier = CriteriaVerifier(
        rig.store,
        odd,
        rig.policy,
        DummyTool("shell"),
        rig.runner,
        lambda kind, payload: None,
        tool_name="shell",
        command_argument="command",
        timeout_argument="timeout_seconds",
    )

    report = await rig.verifier.verify(rig.session_id)

    assert report.results[0].cause is NotRunCause.UNSUPPORTED_CONDITION
    assert rig.runner.calls == []


class RaisingRunner(ScriptedRunner):
    async def __call__(self, call: ToolCall) -> CommandOutcome:
        raise OSError(SENTINEL)


@pytest.mark.parametrize(
    "runner",
    [ScriptedRunner({"check-a": [CommandOutcome(ran=False)]}), RaisingRunner()],
    ids=["did-not-run", "raises"],
)
async def test_a_runner_that_could_not_run_or_raises_is_an_error(
    make: Callable[..., Rig], runner: ScriptedRunner
) -> None:
    rig = make("check-a", runner=runner)

    report = await rig.verifier.verify(rig.session_id)

    assert report.results[0].cause is NotRunCause.ERROR
    assert SENTINEL not in rig.everything_published()


async def test_a_run_without_an_exit_code_that_did_not_time_out_is_an_error(
    make: Callable[..., Rig],
) -> None:
    runner = ScriptedRunner({"check-a": [CommandOutcome(ran=True, exit_code=None)]})
    rig = make("check-a", runner=runner)

    report = await rig.verifier.verify(rig.session_id)

    assert report.results[0].cause is NotRunCause.ERROR


async def test_a_store_that_cannot_mark_leaves_the_criterion_unmet(
    make: Callable[..., Rig],
) -> None:
    rig = make("check-a")

    def broken(criteria_id: str, evidence: str) -> None:
        raise RuntimeError(SENTINEL)

    rig.store.mark_passes = broken  # type: ignore[method-assign]

    report = await rig.verifier.verify(rig.session_id)

    assert report.results[0].status is CriterionStatus.NOT_RUN
    assert report.results[0].cause is NotRunCause.ERROR
    assert rig.passes() == [False]
    assert SENTINEL not in rig.everything_published()


async def test_cancellation_is_never_swallowed(make: Callable[..., Rig]) -> None:
    class Cancelled(ScriptedRunner):
        async def __call__(self, call: ToolCall) -> CommandOutcome:
            raise asyncio.CancelledError

    rig = make("check-a", runner=Cancelled())

    with pytest.raises(asyncio.CancelledError):
        await rig.verifier.verify(rig.session_id)


# --- what is published ----------------------------------------------------------------------------


async def test_one_criterion_verified_event_per_criterion_in_order(
    make: Callable[..., Rig],
) -> None:
    rig = make(
        "pytest tests/a.py",
        None,
        "pytest tests/b.py",
        runner=ScriptedRunner({"pytest tests/b.py": [failed(1)]}),
    )

    await rig.verifier.verify(rig.session_id)

    payloads = rig.of(EventType.CRITERION_VERIFIED)
    assert payloads == [
        {
            "criterion": 1,
            "total": 3,
            "description": "criterio 1",
            "status": "cumplido",
            "met": True,
            "exit_code": 0,
            "program": "pytest",
        },
        {
            "criterion": 2,
            "total": 3,
            "description": "criterio 2",
            "status": "pendiente_humano",
            "met": False,
            "exit_code": None,
            "program": None,
        },
        {
            "criterion": 3,
            "total": 3,
            "description": "criterio 3",
            "status": "no_cumplido",
            "met": False,
            "exit_code": 1,
            "program": "pytest",
        },
    ]
    assert [list(p) for p in payloads] == [
        ["criterion", "total", "description", "status", "met", "exit_code", "program"]
    ] * 3


async def test_the_events_of_a_command_that_is_asked_have_the_shape_of_the_loop(
    make: Callable[..., Rig],
) -> None:
    approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
    rig = make("check-a", policy=StubPolicy({"check-a": ASK}), gate=ApprovalGate(approver))

    await rig.verifier.verify(rig.session_id)

    (decided,) = rig.of(EventType.PERMISSION_DECIDED)
    (requested,) = rig.of(EventType.APPROVAL_REQUESTED)
    (resolved,) = rig.of(EventType.APPROVAL_RESOLVED)
    assert set(decided) == {"call_id", "name", "decision", "resolved_as", "reason"}
    assert (decided["decision"], decided["resolved_as"]) == ("ask", "ask")
    assert set(requested) == {"call_id", "name", "risk"}
    assert set(resolved) == {"call_id", "name", "action", "approved", "source"}
    assert resolved["approved"] is True and requested["call_id"] == "verificacion-1"


async def test_nothing_of_the_command_or_the_output_is_published_or_stored(
    make: Callable[..., Rig],
) -> None:
    command = "check-a --token " + SENTINEL
    output = f"{OUTPUT_SENTINEL} {CREDENTIAL}"
    rig = make(command, "check-b", runner=ScriptedRunner({"check-b": [failed(1, output)]}))

    report = await rig.verifier.verify(rig.session_id)

    published = rig.everything_published()
    for secret in (SENTINEL, OUTPUT_SENTINEL, "secreto-de-prueba", "usuario-de-prueba"):
        assert secret not in published
    assert "criterio 1" in published  # the description is text of the task
    assert report.results[1].output == output  # only the report carries the output
    assert SENTINEL not in rig.marks[0][1]


# --- human confirmation of a semantic criterion (HU-11-05) -----------------------------------------


def test_confirming_a_semantic_criterion_marks_it_with_human_evidence(
    make: Callable[..., Rig],
) -> None:
    rig = make("check-a", None)

    outcome = rig.verifier.confirm(rig.session_id, 2)

    assert outcome is Confirmation.CONFIRMED
    assert rig.passes() == [False, True]
    assert len(rig.marks) == 1 and "persona" in rig.marks[0][1]
    (payload,) = rig.of(EventType.CRITERION_VERIFIED)
    assert payload["criterion"] == 2 and payload["total"] == 2
    assert payload["status"] == "confirmado_humano" and payload["met"] is True
    assert payload["exit_code"] is None and payload["program"] is None


def test_confirming_twice_is_harmless_and_silent(make: Callable[..., Rig]) -> None:
    rig = make(None)
    rig.verifier.confirm(rig.session_id, 1)

    assert rig.verifier.confirm(rig.session_id, 1) is Confirmation.ALREADY
    assert len(rig.marks) == 1 and len(rig.of(EventType.CRITERION_VERIFIED)) == 1


@pytest.mark.parametrize("index", [0, 3, -1, True])
def test_only_an_existing_criterion_can_be_confirmed(make: Callable[..., Rig], index: int) -> None:
    rig = make("check-a", None)

    assert rig.verifier.confirm(rig.session_id, index) is Confirmation.NOT_CONFIRMABLE
    assert rig.marks == []


def test_an_objective_criterion_is_never_confirmed_by_a_person(make: Callable[..., Rig]) -> None:
    rig = make("check-a", None)

    assert rig.verifier.confirm(rig.session_id, 1) is Confirmation.NOT_CONFIRMABLE
    assert rig.passes() == [False, False] and rig.marks == []


def test_a_stored_criterion_that_differs_from_the_definition_is_tampering(
    make: Callable[..., Rig],
) -> None:
    rig = make(None, stored=("echo algo",))

    assert rig.verifier.confirm(rig.session_id, 1) is Confirmation.TAMPERED
    assert rig.marks == []


def test_a_store_that_cannot_mark_leaves_the_criterion_unconfirmed(
    make: Callable[..., Rig],
) -> None:
    rig = make(None)

    def broken(criteria_id: str, evidence: str) -> None:
        raise RuntimeError("disco lleno")

    rig.store.mark_passes = broken  # type: ignore[method-assign]

    assert rig.verifier.confirm(rig.session_id, 1) is Confirmation.FAILED
    assert rig.of(EventType.CRITERION_VERIFIED) == []


async def test_a_later_round_reports_a_confirmed_criterion_as_confirmed(
    make: Callable[..., Rig],
) -> None:
    rig = make("check-a", None)
    rig.verifier.confirm(rig.session_id, 2)

    report = await rig.verifier.verify(rig.session_id)

    assert [r.status for r in report.results] == [
        CriterionStatus.MET,
        CriterionStatus.CONFIRMED_HUMAN,
    ]
    assert report.state is TaskState.VERIFIED


def test_a_different_number_of_stored_criteria_blocks_the_confirmation(
    make: Callable[..., Rig],
) -> None:
    rig = make(None, None, stored=(None,))

    assert rig.verifier.confirm(rig.session_id, 1) is Confirmation.TAMPERED
    assert rig.of(EventType.CRITERIA_TAMPERED) == [{"motivo": "criterios_no_coinciden"}]
    assert rig.marks == []
