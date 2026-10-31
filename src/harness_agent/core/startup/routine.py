"""The startup routine of a resumed ticket (HU-11-08.2).

It reads the progress file of the ticket, the recent git log and runs the basic test (the
``pruebas`` command of the task) before the agent touches anything, and builds the text the agent
receives.
A ticket without a progress file is a new one: there is no routine. Whatever cannot be read or run
becomes a fixed "not available" text; nothing the sources say is kept as an error. Cancellation is
never caught.
"""

from __future__ import annotations

from harness_agent.core.progress.recorder import ProgressSink
from harness_agent.core.progress.render import progress_file_name
from harness_agent.core.startup.briefing import (
    Briefing,
    CheckResult,
    CheckState,
    StartupFacts,
    build_briefing,
)
from harness_agent.core.startup.gated import GatedCommandRunner, RunStatus
from harness_agent.core.tasks.commands import TaskCommand

GIT_LOG_COMMAND = "git log --oneline -n 10"
_LOG_CALL = "arranque-git"
_TEST_CALL = "arranque-prueba"


class StartupRoutine:
    """Gathers what a resumed ticket needs before new work starts.

    Args:
        progress: Where the progress file is read from (the destination of HU-11-08.1).
        runner: Runs the commands under the permission policy of the session.
        ticket: The title of the task (it names the progress file).
        session_id: Session of the run (names the file when the ticket has no usable title).
        tests: The ``pruebas`` command of the task, or ``None`` if it declares none.
    """

    def __init__(
        self,
        progress: ProgressSink,
        runner: GatedCommandRunner,
        *,
        ticket: str | None,
        session_id: str,
        tests: TaskCommand | None,
    ) -> None:
        self._progress = progress
        self._runner = runner
        self._name = progress_file_name(ticket, session_id)
        self._tests = tests

    async def run(self) -> Briefing | None:
        """The briefing for the agent, or ``None`` if the ticket has no previous progress."""
        text: str | None
        try:
            text = self._progress.read(self._name)
        except Exception:
            text = ""  # it could not be read: the ticket may have progress, so the rest runs
        if text is None:
            return None
        log = await self._git_log()
        check = await self._basic_test()
        return build_briefing(StartupFacts(progress=text or None, log=log, check=check))

    async def _git_log(self) -> str | None:
        result = await self._runner.run(_LOG_CALL, GIT_LOG_COMMAND, None)
        outcome = result.outcome
        if result.status is not RunStatus.RAN or outcome is None or outcome.exit_code != 0:
            return None
        return outcome.output

    async def _basic_test(self) -> CheckResult:
        if self._tests is None:
            return CheckResult(CheckState.NOT_CHECKED)
        result = await self._runner.run(
            _TEST_CALL, self._tests.command, self._tests.timeout_seconds
        )
        outcome = result.outcome
        if result.status is not RunStatus.RAN or outcome is None or not outcome.ran:
            return CheckResult(CheckState.NOT_CHECKED)
        if outcome.timed_out:
            return CheckResult(CheckState.FAILED, timed_out=True, output=outcome.output)
        if outcome.exit_code is None:
            return CheckResult(CheckState.NOT_CHECKED)
        if outcome.exit_code == 0:
            return CheckResult(CheckState.PASSED, exit_code=0)
        return CheckResult(CheckState.FAILED, exit_code=outcome.exit_code, output=outcome.output)
