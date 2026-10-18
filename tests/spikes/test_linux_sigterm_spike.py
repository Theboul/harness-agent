"""Real-process SIGTERM -> SIGKILL escalation on Linux (SPK-02, task T016).

The Windows suite cannot exercise this path: ``Process.terminate()`` is ``TerminateProcess``
there, so a child cannot "ignore" it. These tests spawn a real Python child that installs
``SIG_IGN`` for SIGTERM and check that the two-phase cleanup escalates to SIGKILL.

Every test is skipped outside Linux. Evidence collected so far comes from a local WSL2 Ubuntu
run; a GitHub Actions ``ubuntu-latest`` run is still pending (see docs/decisiones/D-01).

Determinism: the child writes a marker file only after the handler is installed, and the test
polls for it with a hard deadline, so SIGTERM is never sent before it would be ignored.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

from tests.spikes.test_async_cancellation_spike import (
    OperationResult,
    OperationStatus,
    SpikeLoop,
    SpikeProcessOperation,
    bounded,
    is_pid_alive,
)

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="requires POSIX signals (Linux only)"
)

# asyncio reports death by signal N as returncode -N; SIGKILL is signal 9 on Linux. A literal is
# used because ``signal.SIGKILL`` does not exist on Windows and would break type checking there.
SIGKILL_RETURNCODE = -9
GRACE_S = 0.15
READY_DEADLINE_S = 5.0


def ignoring_child_script(marker: Path) -> str:
    """Child that ignores SIGTERM, signals readiness through ``marker`` and then sleeps."""
    return (
        "import pathlib, signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"pathlib.Path({str(marker)!r}).write_text('ready')\n"
        "time.sleep(30)\n"
    )


async def wait_ready(marker: Path) -> None:
    """Poll until the child installed its handler, failing fast instead of hanging."""
    deadline = time.perf_counter() + READY_DEADLINE_S
    while not marker.exists():
        if time.perf_counter() > deadline:
            pytest.fail("child never signalled readiness")
        await asyncio.sleep(0.01)


def child_pids_of_current_process() -> set[int]:
    """PIDs whose parent is this process (zombies included), read from ``/proc``."""
    children: set[int] = set()
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            stat = Path(f"/proc/{entry}/stat").read_text()
        except OSError:
            continue  # the process vanished while scanning
        # Format: "pid (comm) state ppid ..."; comm may contain spaces or parentheses.
        fields = stat.rsplit(")", 1)[1].split()
        if int(fields[1]) == os.getpid():
            children.add(int(entry))
    return children


def assert_gone(pid: int) -> None:
    """The PID must be absent from the OS: no live process and no unreaped zombie."""
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert not Path(f"/proc/{pid}").exists(), f"/proc/{pid} still exists (zombie?)"


async def start_ignoring_op(
    loop: SpikeLoop, tmp_path: Path, name: str, grace_s: float = GRACE_S
) -> tuple[SpikeProcessOperation, asyncio.Task[OperationResult]]:
    marker = tmp_path / f"{name}.ready"
    op = SpikeProcessOperation(ignoring_child_script(marker), grace_period_s=grace_s)
    task: asyncio.Task[OperationResult] = asyncio.create_task(loop.run_operation(op))
    await wait_ready(marker)
    return op, task


@pytest.mark.asyncio
async def test_linux_child_really_ignores_sigterm(tmp_path: Path) -> None:
    """Control: SIGTERM alone does not end the child; only SIGKILL does (returncode -9)."""
    marker = tmp_path / "control.ready"
    proc = await asyncio.create_subprocess_exec(sys.executable, "-c", ignoring_child_script(marker))
    try:
        await wait_ready(marker)
        proc.terminate()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(proc.wait(), timeout=0.5)
        assert proc.returncode is None, "SIGTERM must not end a child that ignores it"
        assert is_pid_alive(proc.pid)
    finally:
        proc.kill()
        await bounded(proc.wait())

    assert proc.returncode == SIGKILL_RETURNCODE
    assert_gone(proc.pid)


@pytest.mark.asyncio
async def test_linux_sigterm_ignored_escalates_to_sigkill(tmp_path: Path) -> None:
    """Cancelling an op whose child ignores SIGTERM escalates to SIGKILL within the bound."""
    loop = SpikeLoop()
    op, task = await start_ignoring_op(loop, tmp_path, "escalation")
    pid = op.pid
    assert pid is not None and is_pid_alive(pid)

    started = time.perf_counter()
    task.cancel()
    result = await bounded(task)
    elapsed_s = time.perf_counter() - started

    assert result.status == OperationStatus.CANCELLED
    assert op.returncode == SIGKILL_RETURNCODE, "cleanup must escalate to SIGKILL"
    assert elapsed_s >= GRACE_S, "SIGKILL cannot come before the grace period expired"
    assert elapsed_s < 0.5, f"control returned after {elapsed_s * 1000:.1f} ms (limit 500 ms)"
    assert_gone(pid)
    print(
        f"[linux-evidence] escalation: grace={GRACE_S * 1000:.0f} ms "
        f"returncode={op.returncode} control_back_after={elapsed_s * 1000:.1f} ms pid={pid}"
    )


@pytest.mark.asyncio
async def test_linux_second_cancel_during_grace_period_still_kills(tmp_path: Path) -> None:
    """Repeated cancels while the cleanup waits out the grace period do not abort the kill."""
    loop = SpikeLoop()
    op, task = await start_ignoring_op(loop, tmp_path, "double", grace_s=0.3)
    pid = op.pid
    assert pid is not None

    started = time.perf_counter()
    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()
    await asyncio.sleep(0.05)
    task.cancel()
    result = await bounded(task)
    elapsed_s = time.perf_counter() - started

    assert result.status == OperationStatus.CANCELLED
    assert "extra cancel requests during cleanup: 2" in (result.error_message or "")
    assert op.returncode == SIGKILL_RETURNCODE
    assert_gone(pid)
    print(
        f"[linux-evidence] repeated cancel: extra_requests=2 returncode={op.returncode} "
        f"control_back_after={elapsed_s * 1000:.1f} ms"
    )


@pytest.mark.asyncio
async def test_linux_timeout_with_sigterm_ignored_escalates(tmp_path: Path) -> None:
    """The timeout path uses the same cleanup: TIMEOUT status and returncode -9."""
    marker = tmp_path / "timeout.ready"
    op = SpikeProcessOperation(ignoring_child_script(marker), grace_period_s=GRACE_S)

    started = time.perf_counter()
    result = await bounded(SpikeLoop().run_operation(op, timeout=0.4))
    elapsed_s = time.perf_counter() - started

    assert result.status == OperationStatus.TIMEOUT
    assert op.returncode == SIGKILL_RETURNCODE
    assert op.pid is not None
    assert_gone(op.pid)
    print(
        f"[linux-evidence] timeout: timeout=0.4 s returncode={op.returncode} "
        f"total={elapsed_s * 1000:.1f} ms"
    )


@pytest.mark.asyncio
async def test_linux_sequential_cycles_leave_no_experiment_process(tmp_path: Path) -> None:
    """Five cancel cycles against SIGTERM-ignoring children leave none of their PIDs alive."""
    loop = SpikeLoop()
    pids: list[int] = []
    returncodes: list[int | None] = []
    control_ms: list[float] = []

    for index in range(5):
        op, task = await start_ignoring_op(loop, tmp_path, f"cycle{index}")
        assert op.pid is not None
        pids.append(op.pid)
        started = time.perf_counter()
        task.cancel()
        result = await bounded(task)
        control_ms.append((time.perf_counter() - started) * 1000)
        assert result.status == OperationStatus.CANCELLED
        returncodes.append(op.returncode)

    assert returncodes == [SIGKILL_RETURNCODE] * 5
    for pid in pids:
        assert_gone(pid)
    assert not (set(pids) & child_pids_of_current_process()), "experiment child still listed"
    print(
        f"[linux-evidence] cycles: n=5 returncodes={returncodes} "
        f"control_back_ms={[round(v, 1) for v in control_ms]}"
    )
