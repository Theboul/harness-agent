"""Gated runner and startup routine, with stand-ins for the policy, the runner and the file."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from harness_agent.core import (
    ApprovalAction,
    ApprovalGate,
    CheckState,
    CommandKind,
    CommandOutcome,
    EventType,
    GatedCommandRunner,
    PermissionDecision,
    RunStatus,
    StartupRoutine,
    TaskCommand,
    ToolCall,
)
from tests.doubles import DummyApprover, DummyTool, ScriptedPolicy

SENTINEL = "VALOR-DE-PRUEBA-123"
ALLOW, ASK, DENY = PermissionDecision.ALLOW, PermissionDecision.ASK, PermissionDecision.DENY
TESTS = TaskCommand(CommandKind.TESTS, "pytest -q", 90)
NAME = "progreso-TAREA-14.md"


class Progress:
    def __init__(self, text: str | None, error: BaseException | None = None) -> None:
        self.text, self.error = text, error
        self.read_names: list[str] = []

    def write(self, name: str, text: str) -> None:
        raise AssertionError("the routine never writes")

    def read(self, name: str) -> str | None:
        self.read_names.append(name)
        if self.error is not None:
            raise self.error
        return self.text


class Shell:
    """Answers per command; records every call it is asked to run."""

    def __init__(self, answers: dict[str, CommandOutcome | BaseException]) -> None:
        self.answers = answers
        self.calls: list[ToolCall] = []

    async def __call__(self, call: ToolCall) -> CommandOutcome:
        self.calls.append(call)
        answer = self.answers.get(call.arguments["command"], CommandOutcome(ran=False))
        if isinstance(answer, BaseException):
            raise answer
        return answer


def runner(
    shell: Shell,
    decisions: dict[str, Any] | None = None,
    approver: DummyApprover | None = None,
) -> tuple[GatedCommandRunner, list[tuple[EventType, dict[str, Any]]]]:
    events: list[tuple[EventType, dict[str, Any]]] = []
    return (
        GatedCommandRunner(
            ScriptedPolicy({"shell": ALLOW} if decisions is None else decisions),
            DummyTool(name="shell"),
            shell,
            lambda kind, payload: events.append((kind, payload)),
            gate=None if approver is None else ApprovalGate(approver),
            tool_name="shell",
            command_argument="command",
            timeout_argument="timeout_seconds",
        ),
        events,
    )


def routine(
    progress: Progress, gated: GatedCommandRunner, tests: TaskCommand | None = TESTS
) -> StartupRoutine:
    return StartupRoutine(progress, gated, ticket="TAREA-14: validar", session_id="s1", tests=tests)


GIT = "git log --oneline -n 10"
OK = CommandOutcome(ran=True, exit_code=0, output="a1b2c3 feat: algo\n")


class TestGatedRunner:
    async def test_an_allowed_call_runs_with_the_agents_shape(self) -> None:
        shell = Shell({"x": OK})
        gated, events = runner(shell)
        result = await gated.run("c1", "x", 90)
        assert result.status is RunStatus.RAN and result.outcome == OK
        call = shell.calls[0]
        assert (call.name, call.arguments) == ("shell", {"command": "x", "timeout_seconds": 90})
        assert events[0][0] is EventType.PERMISSION_DECIDED

    async def test_no_timeout_means_no_timeout_argument(self) -> None:
        shell = Shell({"x": OK})
        gated, _ = runner(shell)
        await gated.run("c1", "x", None)
        assert shell.calls[0].arguments == {"command": "x"}

    async def test_a_denied_call_never_runs_nor_asks(self) -> None:
        shell, approver = Shell({"x": OK}), DummyApprover()
        gated, _ = runner(shell, {"shell": DENY}, approver)
        assert (await gated.run("c1", "x", None)).status is RunStatus.DENIED
        assert shell.calls == [] and approver.recorded_requests == []

    async def test_asked_without_approver_does_not_run(self) -> None:
        shell = Shell({"x": OK})
        gated, _ = runner(shell, {"shell": ASK})
        assert (await gated.run("c1", "x", None)).status is RunStatus.NO_APPROVER
        assert shell.calls == []

    async def test_asked_and_approved_runs_and_rejected_does_not(self) -> None:
        shell = Shell({"x": OK})
        gated, events = runner(shell, {"shell": ASK}, DummyApprover(ApprovalAction.APPROVE_ONCE))
        assert (await gated.run("c1", "x", None)).status is RunStatus.RAN
        kinds = [kind for kind, _ in events]
        assert EventType.APPROVAL_REQUESTED in kinds and EventType.APPROVAL_RESOLVED in kinds
        shell2 = Shell({"x": OK})
        rejected, _ = runner(shell2, {"shell": ASK}, DummyApprover(ApprovalAction.REJECT))
        assert (await rejected.run("c1", "x", None)).status is RunStatus.NOT_APPROVED
        assert shell2.calls == []

    @pytest.mark.parametrize("bad", [RuntimeError("x"), None, "allow"])
    async def test_a_broken_policy_is_a_denial(self, bad: object) -> None:
        shell = Shell({"x": OK})
        gated, _ = runner(shell, {"shell": bad})
        assert (await gated.run("c1", "x", None)).status is RunStatus.DENIED
        assert shell.calls == []

    async def test_an_ordinary_failure_of_the_shell_is_an_error(self) -> None:
        gated, _ = runner(Shell({"x": RuntimeError(SENTINEL)}))
        result = await gated.run("c1", "x", None)
        assert result.status is RunStatus.ERROR and result.outcome is None

    async def test_cancellation_goes_through(self) -> None:
        gated, _ = runner(Shell({"x": asyncio.CancelledError()}))
        with pytest.raises(asyncio.CancelledError):
            await gated.run("c1", "x", None)


class TestRoutine:
    async def test_no_progress_file_means_no_routine(self) -> None:
        shell = Shell({})
        gated, _ = runner(shell)
        assert await routine(Progress(None), gated).run() is None
        assert shell.calls == []

    async def test_it_reads_the_file_of_the_ticket_and_reports_a_pass(self) -> None:
        progress = Progress("# Progreso del ticket\n- Hecho: algo")
        shell = Shell({GIT: OK, "pytest -q": CommandOutcome(ran=True, exit_code=0, output="ok")})
        gated, _ = runner(shell)
        briefing = await routine(progress, gated).run()
        assert briefing is not None and briefing.check_state is CheckState.PASSED
        assert progress.read_names == [NAME]
        assert "a1b2c3 feat: algo" in briefing.text and "- Hecho: algo" in briefing.text
        git_call, test_call = shell.calls
        assert git_call.arguments == {"command": GIT}
        assert test_call.arguments == {"command": "pytest -q", "timeout_seconds": 90}

    async def test_a_failing_test_asks_to_repair_first(self) -> None:
        failing = CommandOutcome(ran=True, exit_code=1, output="1 failed")
        gated, _ = runner(Shell({GIT: OK, "pytest -q": failing}))
        briefing = await routine(Progress("p"), gated).run()
        assert briefing is not None and briefing.check_state is CheckState.FAILED
        assert "Repara eso antes de avanzar" in briefing.text and "1 failed" in briefing.text

    async def test_a_timeout_is_a_failure(self) -> None:
        slow = CommandOutcome(ran=True, timed_out=True, timeout_seconds=90.0)
        gated, _ = runner(Shell({GIT: OK, "pytest -q": slow}))
        briefing = await routine(Progress("p"), gated).run()
        assert briefing is not None and briefing.check_state is CheckState.FAILED
        assert "tiempo agotado" in briefing.text

    async def test_a_task_without_a_basic_test_cannot_be_checked(self) -> None:
        shell = Shell({GIT: OK})
        gated, _ = runner(shell)
        briefing = await routine(Progress("p"), gated, tests=None).run()
        assert briefing is not None and briefing.check_state is CheckState.NOT_CHECKED
        assert len(shell.calls) == 1  # only the git log

    @pytest.mark.parametrize("decision", [DENY, ASK])
    async def test_a_test_that_cannot_run_is_not_checked(self, decision: object) -> None:
        shell = Shell({})
        gated, _ = runner(shell, {"shell": decision})
        briefing = await routine(Progress("p"), gated).run()
        assert briefing is not None and briefing.check_state is CheckState.NOT_CHECKED
        assert shell.calls == []
        assert "(log de git no disponible)" in briefing.text

    async def test_a_log_that_fails_is_unavailable_but_the_test_still_runs(self) -> None:
        not_a_repo = CommandOutcome(ran=True, exit_code=128, output="fatal: not a git repository")
        gated, _ = runner(Shell({GIT: not_a_repo, "pytest -q": CommandOutcome(True, 0)}))
        briefing = await routine(Progress("p"), gated).run()
        assert briefing is not None and briefing.check_state is CheckState.PASSED
        assert "(log de git no disponible)" in briefing.text
        assert "not a git repository" not in briefing.text

    async def test_an_unreadable_file_is_unavailable_and_leaks_nothing(self) -> None:
        gated, _ = runner(Shell({GIT: OK, "pytest -q": CommandOutcome(True, 0)}))
        briefing = await routine(Progress(None, error=OSError(SENTINEL)), gated).run()
        assert briefing is not None
        assert "(progreso no disponible)" in briefing.text and SENTINEL not in briefing.text

    async def test_cancellation_while_reading_goes_through(self) -> None:
        gated, _ = runner(Shell({}))
        with pytest.raises(asyncio.CancelledError):
            await routine(Progress(None, error=asyncio.CancelledError()), gated).run()

    async def test_the_briefing_never_carries_the_command(self) -> None:
        failing = CommandOutcome(ran=True, exit_code=1, output="x")
        gated, _ = runner(Shell({GIT: OK, "pytest -q": failing}))
        briefing = await routine(Progress("p"), gated).run()
        assert briefing is not None
        assert "pytest -q" not in briefing.text and GIT not in briefing.text


class TestOddAnswersOfTheShell:
    async def test_an_answer_that_is_not_an_outcome_is_an_error(self) -> None:
        async def odd(call: ToolCall) -> object:
            return "no es un resultado"

        gated = GatedCommandRunner(
            ScriptedPolicy({"shell": ALLOW}),
            DummyTool(name="shell"),
            odd,  # type: ignore[arg-type]
            lambda kind, payload: None,
            gate=None,
            tool_name="shell",
            command_argument="command",
            timeout_argument="timeout_seconds",
        )
        assert (await gated.run("c1", "x", None)).status is RunStatus.ERROR

    async def test_a_run_with_no_exit_code_and_no_timeout_is_not_checked(self) -> None:
        odd = CommandOutcome(ran=True, exit_code=None)
        gated, _ = runner(Shell({GIT: OK, "pytest -q": odd}))
        briefing = await routine(Progress("p"), gated).run()
        assert briefing is not None and briefing.check_state is CheckState.NOT_CHECKED
