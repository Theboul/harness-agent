"""Helpers of the shell tests that run real processes (HU-01-04).

Liveness is checked without ``os.kill(pid, 0)`` on Windows, where any signal other than the console
events terminates the process.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

IS_WINDOWS = os.name == "nt"

GRANDCHILD_PARENT_CODE = (
    "import subprocess, sys, time\n"
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    "print(child.pid, flush=True)\n"
    "time.sleep(60)\n"
)
"""A parent that prints the pid of a child that keeps the output pipe open, then sleeps."""


def pid_alive(pid: int) -> bool:
    """True if a process with this pid is running (a zombie does not count)."""
    if IS_WINDOWS:
        listing = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        return f'"{pid}"' in listing
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        try:
            return stat.read_text(encoding="utf-8").rsplit(")", 1)[1].split()[0] != "Z"
        except OSError:
            return False
    return True


def wait_until_dead(pid: int, timeout: float = 8.0) -> bool:
    """Wait up to ``timeout`` seconds for the process to disappear."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            return True
        time.sleep(0.05)
    return not pid_alive(pid)


def python_command(code: str) -> list[str]:
    """Argv that runs ``code`` with the interpreter running the tests."""
    return [sys.executable, "-c", code]
