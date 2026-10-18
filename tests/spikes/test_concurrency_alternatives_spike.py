"""Minimal experiments comparing concurrency models for tool cancellation (SPK-02, Sp1-49).

Compares three ways of running a cancellable long operation, measuring only the properties
the decision depends on:

A. asyncio coroutines + ``asyncio.create_subprocess_exec``.
B. Threads: (B1) pure Python work in a worker thread, (B2) a thread owning a ``Popen``.
C. Processes: ``multiprocessing`` (spawn) child, terminated from the parent.

For each model the experiment records: non-blocking wait (the caller keeps running), time to
regain control after the cancel request, whether the underlying work really stops, exit code,
and whether the PID is gone from the operating system.

These are single-machine measurements (Windows 10 with CPython 3.12.10, and a local WSL2 Ubuntu
with CPython 3.12.15; neither is a GitHub Actions runner). They are evidence of
behaviour, not performance benchmarks: tests assert qualitative properties with generous limits.
Run ``python -m tests.spikes.test_concurrency_alternatives_spike`` to print the raw numbers.
"""

from __future__ import annotations

import asyncio
import json
import multiprocessing
import statistics
import subprocess
import sys
import threading
import time
from typing import Any

import pytest

from tests.spikes.test_async_cancellation_spike import is_pid_alive, terminate_then_kill

SLEEP_SCRIPT = "import time; time.sleep(5)"
OBSERVE_S = 0.15
TICK_S = 0.01

Measurement = dict[str, Any]


async def measure_asyncio() -> Measurement:
    """A. Coroutine awaiting an asyncio subprocess, cancelled with the two-phase protocol."""
    ticks = 0
    stop = asyncio.Event()

    async def heartbeat() -> None:
        nonlocal ticks
        while not stop.is_set():
            await asyncio.sleep(TICK_S)
            ticks += 1

    beat = asyncio.create_task(heartbeat())
    t0 = time.perf_counter()
    proc = await asyncio.create_subprocess_exec(sys.executable, "-c", SLEEP_SCRIPT)
    spawn_ms = (time.perf_counter() - t0) * 1000
    pid = proc.pid

    waiter = asyncio.create_task(proc.wait())  # the awaiting side of the operation
    ticks_before = ticks
    await asyncio.sleep(OBSERVE_S)
    ticks_while_waiting = ticks - ticks_before

    t1 = time.perf_counter()
    waiter.cancel()
    await terminate_then_kill(proc, grace_period_s=0.15)
    cancel_to_exit_ms = (time.perf_counter() - t1) * 1000

    stop.set()
    await beat
    return {
        "spawn_ms": spawn_ms,
        "ticks_while_waiting": ticks_while_waiting,
        "cancel_to_exit_ms": cancel_to_exit_ms,
        "returncode": proc.returncode,
        "pid_alive_after": is_pid_alive(pid),
    }


async def measure_thread_pure_work() -> Measurement:
    """B1. Blocking Python work in a worker thread; the awaiting side times out."""
    finished = threading.Event()

    def blocking_work() -> None:
        time.sleep(1.0)
        finished.set()

    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(asyncio.to_thread(blocking_work), timeout=OBSERVE_S)
    except TimeoutError:
        pass
    else:
        raise AssertionError("the blocking work must outlive the timeout")
    control_returned_ms = (time.perf_counter() - t0) * 1000
    work_still_running = not finished.is_set()

    t1 = time.perf_counter()
    await asyncio.to_thread(finished.wait, 5.0)  # only to let the thread end before teardown
    residual_after_cancel_ms = (time.perf_counter() - t1) * 1000
    return {
        "control_returned_ms": control_returned_ms,
        "work_still_running_after_cancel": work_still_running,
        "residual_after_cancel_ms": residual_after_cancel_ms,
    }


def measure_thread_popen() -> Measurement:
    """B2. A worker thread blocked in ``Popen.communicate``; terminate() from another thread."""
    holder: dict[str, subprocess.Popen[bytes]] = {}
    started = threading.Event()

    def worker() -> None:
        proc = subprocess.Popen(
            [sys.executable, "-c", SLEEP_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        holder["proc"] = proc
        started.set()
        proc.communicate()

    t0 = time.perf_counter()
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    started.wait(5.0)
    spawn_ms = (time.perf_counter() - t0) * 1000
    proc = holder["proc"]
    pid = proc.pid

    ticks = 0
    end = time.perf_counter() + OBSERVE_S
    while time.perf_counter() < end:  # the calling thread stays free while the worker blocks
        time.sleep(TICK_S)
        ticks += 1

    t1 = time.perf_counter()
    proc.terminate()
    thread.join(5.0)
    cancel_to_exit_ms = (time.perf_counter() - t1) * 1000
    return {
        "spawn_ms": spawn_ms,
        "ticks_while_waiting": ticks,
        "cancel_to_exit_ms": cancel_to_exit_ms,
        "thread_joined": not thread.is_alive(),
        "returncode": proc.returncode,
        "pid_alive_after": is_pid_alive(pid),
    }


def measure_multiprocessing() -> Measurement:
    """C. ``multiprocessing`` spawn child running ``time.sleep``; terminate() from the parent."""
    ctx = multiprocessing.get_context("spawn")
    child = ctx.Process(target=time.sleep, args=(5,), daemon=True)

    t0 = time.perf_counter()
    child.start()
    spawn_ms = (time.perf_counter() - t0) * 1000
    pid = child.pid
    assert pid is not None

    ticks = 0
    end = time.perf_counter() + OBSERVE_S
    while time.perf_counter() < end:
        time.sleep(TICK_S)
        ticks += 1
    alive_before = child.is_alive()

    t1 = time.perf_counter()
    child.terminate()
    child.join(5.0)
    cancel_to_exit_ms = (time.perf_counter() - t1) * 1000
    exitcode = child.exitcode
    pid_alive_after = is_pid_alive(pid)
    child.close()
    return {
        "spawn_ms": spawn_ms,
        "ticks_while_waiting": ticks,
        "alive_before_cancel": alive_before,
        "cancel_to_exit_ms": cancel_to_exit_ms,
        "exitcode": exitcode,
        "pid_alive_after": pid_alive_after,
    }


@pytest.mark.asyncio
async def test_alt_a_asyncio_waits_cancels_and_terminates() -> None:
    m = await asyncio.wait_for(measure_asyncio(), timeout=15)
    assert m["ticks_while_waiting"] >= 5, "the loop must keep running while the process is awaited"
    assert m["cancel_to_exit_ms"] < 500
    assert m["returncode"] not in (None, 0)
    assert m["pid_alive_after"] is False


@pytest.mark.asyncio
async def test_alt_b1_thread_work_cannot_be_cancelled() -> None:
    m = await asyncio.wait_for(measure_thread_pure_work(), timeout=15)
    assert m["control_returned_ms"] < 500, "the awaiting side can give up quickly"
    assert m["work_still_running_after_cancel"] is True, "but the thread keeps running"
    assert m["residual_after_cancel_ms"] > 300, "until it finishes by itself"


def test_alt_b2_thread_owning_popen_can_terminate_but_needs_manual_plumbing() -> None:
    m = measure_thread_popen()
    assert m["ticks_while_waiting"] >= 5
    assert m["thread_joined"] is True
    assert m["cancel_to_exit_ms"] < 2000
    assert m["returncode"] not in (None, 0)
    assert m["pid_alive_after"] is False


def test_alt_c_multiprocessing_child_terminates_with_higher_startup_cost() -> None:
    m = measure_multiprocessing()
    assert m["alive_before_cancel"] is True
    assert m["cancel_to_exit_ms"] < 3000
    assert m["exitcode"] not in (None, 0)
    assert m["pid_alive_after"] is False


def _summary(runs: list[Measurement]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in runs[0]:
        values = [r[key] for r in runs]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            out[key] = {
                "min": round(min(values), 1),
                "median": round(statistics.median(values), 1),
                "max": round(max(values), 1),
            }
        else:
            out[key] = sorted({str(v) for v in values})
    return out


def main(repeats: int = 5) -> None:
    """Print raw measurements (min/median/max over ``repeats`` runs) as JSON."""
    results: dict[str, Any] = {
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "repeats": repeats,
    }
    results["A_asyncio_subprocess"] = _summary(
        [asyncio.run(measure_asyncio()) for _ in range(repeats)]
    )
    results["B1_thread_pure_work"] = _summary(
        [asyncio.run(measure_thread_pure_work()) for _ in range(repeats)]
    )
    results["B2_thread_popen"] = _summary([measure_thread_popen() for _ in range(repeats)])
    results["C_multiprocessing_spawn"] = _summary(
        [measure_multiprocessing() for _ in range(repeats)]
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
