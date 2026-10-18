"""Asynchronous tool cancellation and loop control spike (SPK-02).

Demonstrates experimentally:
1. Cooperative asyncio execution with non-blocking subprocess operations.
2. Controlled two-phase cancellation (terminate -> grace period -> kill).
3. Return of loop control in < 500 ms upon cancellation.
4. Clean OS process termination with no orphan PID (real processes: Windows only so far).
5. Successful execution of subsequent operations on the same loop post-cancellation.
6. Automatic timeout handling via asyncio.wait_for.
7. Edge cases (V8-V22): cancel before start, finish before cancel, terminate ignored,
   cancel during cleanup, loop liveness, explicit completed/failed/cancelled/timeout states.

Scope and caveats (read before reusing any of this):
- This is an experiment. It is NOT the production cancellation design (that is HU-06-03).
- ``SpikeLoop.run_operation`` swallows ``asyncio.CancelledError`` by default and returns a
  normal ``OperationResult``. That is convenient for the experiment but wrong for production:
  swallowing leaves ``Task.cancelling() > 0`` and hides the cancellation from callers.
  ``reraise_cancel=True`` shows the structured alternative (cleanup first, then re-raise).
- Real-process tests ran on Windows and on a local WSL2 Ubuntu (not a GitHub Actions runner).
  Scenarios that cannot be reproduced on Windows (a child that ignores SIGTERM, because
  ``terminate()`` is ``TerminateProcess``) are validated here against a controlled double
  (``FakeProcess``) and against a real child in ``test_linux_sigterm_spike.py`` (Linux only).
"""

from __future__ import annotations

import asyncio
import enum
import gc
import os
import sys
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol, TypeVar

import pytest

T = TypeVar("T")

TEST_TIME_LIMIT_S = 10.0


class OperationStatus(str, enum.Enum):
    """Lifecycle status of a spike operation."""

    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    FAILED = "failed"


@dataclass(frozen=True)
class OperationResult:
    """Outcome of a cancellable process operation."""

    status: OperationStatus
    return_code: int | None
    duration_ms: float
    output: str
    error_message: str | None = None


class ProcessLike(Protocol):
    """Subset of ``asyncio.subprocess.Process`` used by the cancellation algorithm."""

    @property
    def pid(self) -> int: ...

    @property
    def returncode(self) -> int | None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    async def wait(self) -> int: ...


def is_pid_alive(pid: int) -> bool:
    """Check if a process ID is currently alive in the operating system."""
    if pid <= 0:
        return False

    if sys.platform == "win32":
        import ctypes

        synchronize = 0x00100000
        process_query_limited_info = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            synchronize | process_query_limited_info, False, pid
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                # 259 is STILL_ACTIVE
                return exit_code.value == 259
            return False
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True


def open_handle_count() -> int | None:
    """Number of OS handles/descriptors held by this process, or None if not measurable.

    Windows uses ``GetProcessHandleCount``; Linux counts ``/proc/self/fd`` (executed on a local
    WSL2 Ubuntu; a GitHub Actions run is still pending).
    """
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.GetProcessHandleCount.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        count = ctypes.c_ulong()
        if kernel32.GetProcessHandleCount(kernel32.GetCurrentProcess(), ctypes.byref(count)):
            return int(count.value)
        return None
    if os.path.isdir("/proc/self/fd"):
        return len(os.listdir("/proc/self/fd"))
    return None


async def terminate_then_kill(proc: ProcessLike, grace_period_s: float = 0.15) -> None:
    """Two-phase shutdown: terminate -> bounded grace period -> kill -> wait.

    Safe to call on a process that already exited, or that exits between the checks.
    On Windows ``terminate()`` already is ``TerminateProcess``, so the kill phase only
    matters on POSIX (SIGTERM can be ignored, SIGKILL cannot).
    """
    if proc.returncode is not None:
        return

    try:
        proc.terminate()
    except ProcessLookupError:
        pass  # exited between the returncode check and the signal

    try:
        await asyncio.wait_for(proc.wait(), timeout=grace_period_s)
        return
    except TimeoutError:
        pass

    if proc.returncode is None:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
    await proc.wait()


class SpikeProcessOperation:
    """Controlled long-running operation executed in an isolated Python subprocess."""

    def __init__(self, script: str, grace_period_s: float = 0.15) -> None:
        self.script = script
        self.grace_period_s = grace_period_s
        self.proc: ProcessLike | None = None
        self.pid: int | None = None
        self._started_at: float = 0.0

    @property
    def returncode(self) -> int | None:
        """Exit code of the underlying process, or None if unknown or still running."""
        return None if self.proc is None else self.proc.returncode

    async def execute(self) -> tuple[int | None, str]:
        """Spawn the process and wait for completion."""
        self._started_at = time.perf_counter()
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            self.script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.proc = proc
        self.pid = proc.pid

        stdout_bytes, stderr_bytes = await proc.communicate()
        output = (stdout_bytes + stderr_bytes).decode("utf-8", errors="replace")
        return proc.returncode, output

    async def cancel(self, grace_period_s: float | None = None) -> None:
        """Two-phase shutdown: graceful terminate -> grace period -> forced kill."""
        if self.proc is None:
            return
        grace = self.grace_period_s if grace_period_s is None else grace_period_s
        await terminate_then_kill(self.proc, grace)

    def is_alive(self) -> bool:
        """Check whether the spawned subprocess is still executing."""
        if self.proc is None:
            return False
        if self.proc.returncode is not None:
            return False
        if self.pid is not None:
            return is_pid_alive(self.pid)
        return False


async def complete_cleanup(op: SpikeProcessOperation) -> int:
    """Run ``op.cancel()`` to completion even if the caller is cancelled again meanwhile.

    The cleanup runs as its own task and is awaited through ``asyncio.shield`` inside a loop:
    every extra ``CancelledError`` is absorbed and the wait is resumed until the cleanup task
    is done. ``shield`` alone is NOT enough: it only protects the inner task, while the outer
    await still raises immediately on a second cancel (see the control tests below).

    Returns the number of extra cancellation requests absorbed during the cleanup.
    """
    cleanup = asyncio.ensure_future(op.cancel())
    extra_requests = 0
    while not cleanup.done():
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            if cleanup.done():
                break
            extra_requests += 1
    cleanup.result()
    return extra_requests


class SpikeLoop:
    """Minimal prototype loop simulating turn execution and cancellation recovery."""

    async def run_operation(
        self,
        op: SpikeProcessOperation,
        timeout: float | None = None,
        reraise_cancel: bool = False,
    ) -> OperationResult:
        """Execute a cancellable operation, recovering control on cancellation or timeout.

        Outcome mapping: exit code 0 -> COMPLETED, non-zero -> FAILED, ``TimeoutError`` ->
        TIMEOUT, ``CancelledError`` -> CANCELLED. In every cancelled/timeout path the
        subprocess cleanup finishes before this method returns or re-raises.

        With ``reraise_cancel=False`` (experiment only) the cancellation is swallowed and a
        normal result is returned. With ``reraise_cancel=True`` the ``CancelledError`` is
        re-raised after the cleanup, which is the semantics production code must keep.
        """
        start_time = time.perf_counter()
        try:
            if timeout is not None:
                return_code, output = await asyncio.wait_for(op.execute(), timeout=timeout)
            else:
                return_code, output = await op.execute()

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            status = OperationStatus.COMPLETED if return_code == 0 else OperationStatus.FAILED
            return OperationResult(
                status=status,
                return_code=return_code,
                duration_ms=elapsed_ms,
                output=output,
            )
        except TimeoutError:
            await complete_cleanup(op)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return OperationResult(
                status=OperationStatus.TIMEOUT,
                return_code=op.returncode,
                duration_ms=elapsed_ms,
                output="",
                error_message=f"Operation timed out after {timeout}s",
            )
        except asyncio.CancelledError:
            extra_requests = await complete_cleanup(op)
            if reraise_cancel:
                raise
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            message = "Operation was cancelled"
            if extra_requests:
                message += f" (extra cancel requests during cleanup: {extra_requests})"
            return OperationResult(
                status=OperationStatus.CANCELLED,
                return_code=op.returncode,
                duration_ms=elapsed_ms,
                output="",
                error_message=message,
            )


async def bounded(awaitable: Awaitable[T], limit_s: float = TEST_TIME_LIMIT_S) -> T:
    """Await with a hard time limit so a regression fails fast instead of hanging."""
    return await asyncio.wait_for(awaitable, timeout=limit_s)


# ==============================================================================
# Suite of 7 Validation Scenarios (AC-01 / V1-V7)
# ==============================================================================


@pytest.mark.asyncio
async def test_v1_spawn_and_normal_completion() -> None:
    """Scenario V1: Normal fast execution completes with code 0 and valid output."""
    loop = SpikeLoop()
    op = SpikeProcessOperation("print('harness_spike_v1_ok')")

    result = await loop.run_operation(op)

    assert result.status == OperationStatus.COMPLETED
    assert result.return_code == 0
    assert "harness_spike_v1_ok" in result.output
    assert not op.is_alive()


@pytest.mark.asyncio
async def test_v2_active_cancellation_within_500ms() -> None:
    """Scenario V2: Active operation cancelled mid-flight returns control in < 500 ms."""
    loop = SpikeLoop()
    op = SpikeProcessOperation("import time; time.sleep(5)")

    task = asyncio.create_task(loop.run_operation(op))

    # Give the process enough time to spawn and start sleeping
    await asyncio.sleep(0.12)
    assert op.is_alive(), "Process should be alive before cancellation signal"

    cancel_start = time.perf_counter()
    task.cancel()

    result = await task
    cancel_duration_ms = (time.perf_counter() - cancel_start) * 1000

    assert result.status == OperationStatus.CANCELLED
    assert cancel_duration_ms < 500.0, (
        f"Cancellation took {cancel_duration_ms:.1f} ms, expected < 500 ms (SC-001)"
    )
    assert not op.is_alive(), "Subprocess must not be alive after cancellation"


@pytest.mark.asyncio
async def test_v3_process_terminated_and_no_orphan_pid() -> None:
    """Scenario V3: Cancelled process is completely terminated with no orphan PID in the OS."""
    loop = SpikeLoop()
    op = SpikeProcessOperation("import time; time.sleep(5)")

    task = asyncio.create_task(loop.run_operation(op))
    await asyncio.sleep(0.12)

    captured_pid = op.pid
    assert captured_pid is not None, "Subprocess PID should be captured"
    assert is_pid_alive(captured_pid), "Subprocess PID should be active before cancellation"

    task.cancel()
    result = await task

    assert result.status == OperationStatus.CANCELLED
    assert result.return_code is not None, "Process returncode must be set upon termination"
    assert not is_pid_alive(captured_pid), (
        f"PID {captured_pid} still alive in OS! Orphan process detected."
    )


@pytest.mark.asyncio
async def test_v4_loop_recovers_control() -> None:
    """Scenario V4: Loop recovers control immediately without hanging on cancelled coroutine."""
    loop = SpikeLoop()
    op = SpikeProcessOperation("import time; time.sleep(5)")

    task = asyncio.create_task(loop.run_operation(op))
    await asyncio.sleep(0.1)
    task.cancel()

    result = await task
    assert result.status == OperationStatus.CANCELLED

    # Check loop is alive and unblocked by performing an async operation immediately
    control_checkpoint = False
    await asyncio.sleep(0.01)
    control_checkpoint = True

    assert control_checkpoint is True, "Loop failed to resume control after cancellation"


@pytest.mark.asyncio
async def test_v5_post_cancellation_execution() -> None:
    """Scenario V5: Subsequent operation executes successfully on the same loop."""
    loop = SpikeLoop()

    # Step 1: Run and cancel a long operation
    op1 = SpikeProcessOperation("import time; time.sleep(5)")
    task1 = asyncio.create_task(loop.run_operation(op1))
    await asyncio.sleep(0.1)
    task1.cancel()
    result1 = await task1
    assert result1.status == OperationStatus.CANCELLED
    assert not op1.is_alive()

    # Step 2: Immediately execute a second, normal operation
    op2 = SpikeProcessOperation("print('turn_2_post_cancellation_success')")
    result2 = await loop.run_operation(op2)

    assert result2.status == OperationStatus.COMPLETED
    assert result2.return_code == 0
    assert "turn_2_post_cancellation_success" in result2.output
    assert not op2.is_alive()


@pytest.mark.asyncio
async def test_v6_controlled_timeout() -> None:
    """Scenario V6: Operation exceeding timeout is automatically cancelled and cleaned up."""
    loop = SpikeLoop()
    op = SpikeProcessOperation("import time; time.sleep(4)")

    # Execute with a 0.25-second timeout
    result = await loop.run_operation(op, timeout=0.25)

    assert result.status == OperationStatus.TIMEOUT
    assert "timed out after 0.25s" in (result.error_message or "")
    assert not op.is_alive()
    if op.pid is not None:
        assert not is_pid_alive(op.pid), "Process must be terminated after timeout"


@pytest.mark.asyncio
async def test_v7_resource_cleanup_after_repeated_cancellations() -> None:
    """Scenario V7: Repeated cancellations leave no live direct-child PID (Windows only)."""
    loop = SpikeLoop()
    pids: list[int] = []

    for _ in range(3):
        op = SpikeProcessOperation("import time; time.sleep(3)")
        task = asyncio.create_task(loop.run_operation(op))
        await asyncio.sleep(0.08)
        assert op.pid is not None
        pids.append(op.pid)
        task.cancel()
        await task
        assert not op.is_alive()

    # Ensure none of the 3 PIDs remain active in the operating system
    for pid in pids:
        assert not is_pid_alive(pid), f"PID {pid} leaked into OS after multiple runs"


# ==============================================================================
# Controlled doubles (deterministic edge cases that must not depend on the real OS)
# ==============================================================================


class FakeProcess:
    """Controlled process double. Never touches the operating system.

    - ``exits_on_terminate=True``: cooperative child, exits (code -15) on terminate().
    - ``exits_on_terminate=False``: child that ignores terminate(); only kill() ends it (-9).
    - ``vanishes_on_terminate=True``: the process exits (code 0) just before terminate() and
      terminate() raises ProcessLookupError, like a real race.
    """

    def __init__(
        self,
        *,
        exits_on_terminate: bool = False,
        vanishes_on_terminate: bool = False,
        initial_returncode: int | None = None,
        pid: int = 424242,
    ) -> None:
        self._pid = pid
        self._returncode = initial_returncode
        self._exits_on_terminate = exits_on_terminate
        self._vanishes_on_terminate = vanishes_on_terminate
        self._exited = asyncio.Event()
        if initial_returncode is not None:
            self._exited.set()
        self.calls: list[str] = []
        self.terminate_called = asyncio.Event()

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def returncode(self) -> int | None:
        return self._returncode

    def _exit(self, code: int) -> None:
        self._returncode = code
        self._exited.set()

    def terminate(self) -> None:
        self.calls.append("terminate")
        self.terminate_called.set()
        if self._vanishes_on_terminate:
            self._exit(0)
            raise ProcessLookupError
        if self._exits_on_terminate:
            self._exit(-15)

    def kill(self) -> None:
        self.calls.append("kill")
        self._exit(-9)

    async def wait(self) -> int:
        await self._exited.wait()
        assert self._returncode is not None
        return self._returncode


class FakeProcessOperation(SpikeProcessOperation):
    """Operation bound to a FakeProcess that never finishes on its own."""

    def __init__(self, proc: FakeProcess, grace_period_s: float = 0.5) -> None:
        super().__init__("", grace_period_s=grace_period_s)
        self.fake = proc
        self.started = asyncio.Event()

    async def execute(self) -> tuple[int | None, str]:
        self.proc = self.fake
        self.pid = self.fake.pid
        self.started.set()
        await asyncio.Event().wait()
        return None, ""


class ImmediateOperation(SpikeProcessOperation):
    """Operation that completes on its first scheduling step, with no real await."""

    def __init__(self) -> None:
        super().__init__("")

    async def execute(self) -> tuple[int | None, str]:
        self.proc = FakeProcess(initial_returncode=0)
        return 0, "done"


# ==============================================================================
# Edge cases and semantics (V8-V22)
# ==============================================================================


@pytest.mark.asyncio
async def test_v8_cancel_before_task_starts_spawns_nothing() -> None:
    """Edge case 1a: cancelled before its first step, the coroutine body never runs."""
    loop = SpikeLoop()
    op = SpikeProcessOperation("import time; time.sleep(5)")

    task = asyncio.create_task(loop.run_operation(op))
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await bounded(task)

    assert task.cancelled()
    assert op.proc is None and op.pid is None, "No subprocess may be spawned"


@pytest.mark.asyncio
async def test_v9_cancel_while_spawning_leaves_no_live_process() -> None:
    """Edge case 1b: cancelled at the first suspension point (spawn in flight)."""
    loop = SpikeLoop()
    op = SpikeProcessOperation("import time; time.sleep(5)")

    task = asyncio.create_task(loop.run_operation(op))
    await asyncio.sleep(0)  # let the task run until it suspends inside the spawn
    task.cancel()

    result = await bounded(task)

    assert result.status == OperationStatus.CANCELLED
    assert op.proc is None or op.proc.returncode is not None
    if op.pid is not None:
        assert not is_pid_alive(op.pid)


@pytest.mark.asyncio
async def test_v10_cancel_after_natural_exit_keeps_result_and_exit_code() -> None:
    """Edge case 2: the process already exited; a late cancel must be a harmless no-op."""
    loop = SpikeLoop()
    op = SpikeProcessOperation("print('finished_before_cancel')")

    result = await bounded(loop.run_operation(op))
    assert result.status == OperationStatus.COMPLETED

    await bounded(op.cancel())  # late cancellation request: must not raise or change state

    assert op.returncode == 0
    assert not op.is_alive()


@pytest.mark.asyncio
async def test_v11_cancel_after_task_already_finished_is_rejected_by_asyncio() -> None:
    """Edge case 2: the result was produced one step before the cancel signal arrives."""
    loop = SpikeLoop()
    op = ImmediateOperation()

    task = asyncio.create_task(loop.run_operation(op))
    await asyncio.sleep(0)  # the task completes in its first step
    assert task.done()

    assert task.cancel() is False, "A finished task cannot be cancelled"
    result = await bounded(task)
    assert result.status == OperationStatus.COMPLETED
    assert result.return_code == 0
    assert not task.cancelled()


@pytest.mark.asyncio
async def test_v12_terminate_ignored_escalates_to_kill() -> None:
    """Edge cases 3 and 4: a child that ignores terminate() is killed after the grace period."""
    proc = FakeProcess(exits_on_terminate=False)

    start = time.perf_counter()
    await bounded(terminate_then_kill(proc, grace_period_s=0.05))
    elapsed_s = time.perf_counter() - start

    assert proc.calls == ["terminate", "kill"]
    assert proc.returncode == -9
    assert elapsed_s < 1.0


@pytest.mark.asyncio
async def test_v13_cooperative_child_is_not_killed() -> None:
    """Edge case 4 (negative): a child that honours terminate() never receives kill()."""
    proc = FakeProcess(exits_on_terminate=True)

    await bounded(terminate_then_kill(proc, grace_period_s=0.5))

    assert proc.calls == ["terminate"]
    assert proc.returncode == -15


@pytest.mark.asyncio
async def test_v14_process_vanishing_during_terminate_is_tolerated() -> None:
    """Edge case 2 (race): terminate() raises ProcessLookupError because the child just exited."""
    proc = FakeProcess(vanishes_on_terminate=True)

    await bounded(terminate_then_kill(proc, grace_period_s=0.5))

    assert proc.calls == ["terminate"]
    assert proc.returncode == 0


@pytest.mark.asyncio
async def test_v15_second_cancel_during_cleanup_still_ends_the_process() -> None:
    """Edge case 5: a repeated cancel while the cleanup runs must not abandon the child."""
    proc = FakeProcess(exits_on_terminate=False)
    op = FakeProcessOperation(proc, grace_period_s=0.5)
    loop = SpikeLoop()

    task = asyncio.create_task(loop.run_operation(op))
    await bounded(op.started.wait())

    task.cancel()  # first request: cleanup starts (terminate sent, grace period running)
    await bounded(proc.terminate_called.wait())
    task.cancel()  # second request arrives in the middle of the cleanup

    result = await bounded(task)

    assert result.status == OperationStatus.CANCELLED
    assert result.error_message is not None and "extra cancel requests" in result.error_message
    assert proc.calls == ["terminate", "kill"]
    assert proc.returncode == -9
    assert not op.is_alive()


@pytest.mark.asyncio
async def test_v16_control_naive_cleanup_is_abandoned_by_second_cancel() -> None:
    """Negative control for edge case 5: awaiting op.cancel() directly loses the kill phase."""
    proc = FakeProcess(exits_on_terminate=False)
    op = FakeProcessOperation(proc, grace_period_s=0.5)

    async def naive_run() -> None:
        try:
            await op.execute()
        except asyncio.CancelledError:
            await op.cancel()  # not protected: a second cancel interrupts it
            raise

    task = asyncio.create_task(naive_run())
    await bounded(op.started.wait())
    task.cancel()
    await bounded(proc.terminate_called.wait())
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await bounded(task)

    assert proc.calls == ["terminate"], "kill phase never ran"
    assert proc.returncode is None, "the child that ignores terminate() is still running"
    proc.kill()  # test housekeeping on the double


@pytest.mark.asyncio
async def test_v17_control_shield_alone_returns_before_cleanup_completes() -> None:
    """Negative control: a single shield() does not make the caller wait for the cleanup."""
    proc = FakeProcess(exits_on_terminate=False)
    op = FakeProcessOperation(proc, grace_period_s=0.3)
    cleanup_holder: list[asyncio.Future[None]] = []

    async def shield_only_run() -> None:
        try:
            await op.execute()
        except asyncio.CancelledError:
            cleanup = asyncio.ensure_future(op.cancel())
            cleanup_holder.append(cleanup)
            await asyncio.shield(cleanup)  # single shield, no re-await loop
            raise

    task = asyncio.create_task(shield_only_run())
    await bounded(op.started.wait())
    task.cancel()
    await bounded(proc.terminate_called.wait())
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await bounded(task)

    # The caller regained control while the child was still alive: the cleanup survives
    # only because the inner task keeps running, and nobody is waiting for its outcome.
    assert proc.returncode is None
    await bounded(cleanup_holder[0])
    assert proc.returncode == -9


@pytest.mark.asyncio
async def test_v18_loop_stays_responsive_during_cleanup() -> None:
    """Edge case 7: the loop keeps ticking while a slow cleanup is in progress."""
    proc = FakeProcess(exits_on_terminate=False)
    op = FakeProcessOperation(proc, grace_period_s=0.3)
    loop = SpikeLoop()
    ticks = 0
    stop = asyncio.Event()

    async def heartbeat() -> None:
        nonlocal ticks
        while not stop.is_set():
            await asyncio.sleep(0.01)
            ticks += 1

    beat = asyncio.create_task(heartbeat())
    task = asyncio.create_task(loop.run_operation(op))
    await bounded(op.started.wait())
    ticks_before = ticks
    task.cancel()
    result = await bounded(task)
    ticks_during_cleanup = ticks - ticks_before
    stop.set()
    await bounded(beat)

    assert result.status == OperationStatus.CANCELLED
    assert ticks_during_cleanup >= 5, f"only {ticks_during_cleanup} ticks during cleanup"

    # And the same loop runs a fresh real operation afterwards.
    follow_up = await bounded(loop.run_operation(SpikeProcessOperation("print('next_turn')")))
    assert follow_up.status == OperationStatus.COMPLETED


@pytest.mark.asyncio
async def test_v19_four_outcomes_are_distinguishable_and_leave_no_live_pid() -> None:
    """Edge case 6 and semantics: completed/failed/cancelled/timeout, no controlled PID alive."""
    loop = SpikeLoop()
    ops: dict[OperationStatus, SpikeProcessOperation] = {
        OperationStatus.COMPLETED: SpikeProcessOperation("print('ok')"),
        OperationStatus.FAILED: SpikeProcessOperation("raise SystemExit(3)"),
        OperationStatus.CANCELLED: SpikeProcessOperation("import time; time.sleep(5)"),
        OperationStatus.TIMEOUT: SpikeProcessOperation("import time; time.sleep(5)"),
    }

    completed = await bounded(loop.run_operation(ops[OperationStatus.COMPLETED]))
    failed = await bounded(loop.run_operation(ops[OperationStatus.FAILED]))

    cancel_task = asyncio.create_task(loop.run_operation(ops[OperationStatus.CANCELLED]))
    await asyncio.sleep(0.12)
    cancel_task.cancel()
    cancelled = await bounded(cancel_task)

    timed_out = await bounded(loop.run_operation(ops[OperationStatus.TIMEOUT], timeout=0.25))

    assert completed.status == OperationStatus.COMPLETED and completed.return_code == 0
    assert failed.status == OperationStatus.FAILED and failed.return_code == 3
    assert cancelled.status == OperationStatus.CANCELLED
    assert timed_out.status == OperationStatus.TIMEOUT
    assert cancelled.return_code not in (None, 0)
    assert timed_out.return_code not in (None, 0)

    for status, op in ops.items():
        assert op.pid is not None, status
        assert op.returncode is not None, f"{status}: returncode must be set"
        assert not is_pid_alive(op.pid), f"{status}: PID {op.pid} still alive"
        assert not op.is_alive()


@pytest.mark.asyncio
async def test_v20_reraise_mode_cleans_up_and_keeps_task_cancelled() -> None:
    """Semantics: with reraise_cancel=True the task ends cancelled, after the cleanup."""
    loop = SpikeLoop()
    op = SpikeProcessOperation("import time; time.sleep(5)")

    task = asyncio.create_task(loop.run_operation(op, reraise_cancel=True))
    await asyncio.sleep(0.12)
    assert op.is_alive()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await bounded(task)

    assert task.cancelled()
    assert op.returncode is not None
    assert op.pid is not None and not is_pid_alive(op.pid)


@pytest.mark.asyncio
async def test_v21_swallow_mode_limitation_is_observable() -> None:
    """Documents the experimental shortcut: swallowing hides the cancellation from the caller."""
    loop = SpikeLoop()
    op = SpikeProcessOperation("import time; time.sleep(5)")

    task = asyncio.create_task(loop.run_operation(op))
    await asyncio.sleep(0.12)
    task.cancel()
    result = await bounded(task)

    assert result.status == OperationStatus.CANCELLED
    assert not task.cancelled(), "the task looks like a normal completion to its awaiter"
    assert task.cancelling() == 1, "the cancellation request counter is left dangling"


@pytest.mark.asyncio
async def test_v22_repeated_cancellations_do_not_leak_handles() -> None:
    """Resource evidence: the process handle/descriptor count is stable across cancel cycles."""
    loop = SpikeLoop()

    async def cancel_cycle() -> None:
        op = SpikeProcessOperation("import time; time.sleep(5)")
        task = asyncio.create_task(loop.run_operation(op))
        await asyncio.sleep(0.1)
        task.cancel()
        result = await bounded(task)
        assert result.status == OperationStatus.CANCELLED

    async def settled_count() -> int | None:
        gc.collect()
        await asyncio.sleep(0.2)
        gc.collect()
        return open_handle_count()

    await cancel_cycle()  # warm-up: lazy loop/transport resources are created once
    before = await settled_count()
    if before is None:
        pytest.skip("handle/descriptor count is not measurable on this platform")

    for _ in range(5):
        await cancel_cycle()
    after = await settled_count()

    assert after is not None
    assert after - before <= 2, f"handles grew from {before} to {after} after 5 cancel cycles"
