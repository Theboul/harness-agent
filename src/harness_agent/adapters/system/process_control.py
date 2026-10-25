"""Stopping a command and everything it started, per platform (HU-01-04).

``Popen.kill`` only ends the direct child, so a command that launched other processes would leave
them running. POSIX puts the command in its own session and signals the whole group; Windows puts
it in its own process group and ends the tree with ``taskkill /T``. The system calls are injectable
so both strategies can be exercised on any system.
"""

from __future__ import annotations

import os
import signal
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000
_TASKKILL_TIMEOUT_SECONDS = 10

SignalGroup = Callable[[int, int], None]
"""Sends a signal number to a process group: ``(group id, signal number)``."""

RunTaskkill = Callable[[list[str]], object]
"""Runs ``taskkill`` with the given argv."""


class ProcessControl(ABC):
    """How to start a command so it can be stopped as a tree, and how to stop it."""

    @abstractmethod
    def popen_options(self) -> dict[str, Any]:
        """Extra ``Popen`` keyword arguments that put the command in its own group."""

    @abstractmethod
    def request_stop(self, process: subprocess.Popen[bytes]) -> None:
        """Ask the command and its tree to end (polite). Never raises."""

    @abstractmethod
    def force_stop(self, process: subprocess.Popen[bytes]) -> None:
        """End the command and its tree without asking. Never raises."""

    def cleanup(self, process: subprocess.Popen[bytes]) -> None:
        """Remove what the command left behind after it ended by itself. Never raises."""


class PosixProcessControl(ProcessControl):
    """Own session per command; signals go to the whole process group."""

    def __init__(
        self, *, killpg: SignalGroup | None = None, force_signal: int | None = None
    ) -> None:
        """Create the control.

        Args:
            killpg: Sends a signal to a group; defaults to ``os.killpg``.
            force_signal: The signal that cannot be ignored; defaults to ``SIGKILL``.
        """
        self._killpg: SignalGroup = killpg if killpg is not None else _os_killpg()
        self._force_signal: int = (
            force_signal if force_signal is not None else getattr(signal, "SIGKILL", 9)
        )

    def popen_options(self) -> dict[str, Any]:
        return {"start_new_session": True}

    def request_stop(self, process: subprocess.Popen[bytes]) -> None:
        self._signal(process, signal.SIGTERM)

    def force_stop(self, process: subprocess.Popen[bytes]) -> None:
        self._signal(process, self._force_signal)

    def cleanup(self, process: subprocess.Popen[bytes]) -> None:
        self._signal(process, self._force_signal)

    def _signal(self, process: subprocess.Popen[bytes], number: int) -> None:
        # The command is the leader of its own group, so the group id is its pid.
        try:
            self._killpg(process.pid, number)
        except (ProcessLookupError, PermissionError):
            pass


class WindowsProcessControl(ProcessControl):
    """Own process group per command; the tree ends with ``taskkill /T /F``."""

    def __init__(
        self, *, run_taskkill: RunTaskkill | None = None, ctrl_break: int | None = None
    ) -> None:
        """Create the control.

        Args:
            run_taskkill: Runs ``taskkill``; defaults to a quiet ``subprocess.run`` with a timeout.
            ctrl_break: The console event for the polite stop; defaults to ``CTRL_BREAK_EVENT``.
        """
        self._run_taskkill: RunTaskkill = run_taskkill if run_taskkill is not None else _run_quietly
        self._ctrl_break = (
            ctrl_break if ctrl_break is not None else getattr(signal, "CTRL_BREAK_EVENT", 1)
        )

    def popen_options(self) -> dict[str, Any]:
        return {"creationflags": _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW}

    def request_stop(self, process: subprocess.Popen[bytes]) -> None:
        try:
            process.send_signal(self._ctrl_break)
        except (OSError, ValueError):
            pass

    def force_stop(self, process: subprocess.Popen[bytes]) -> None:
        try:
            self._run_taskkill(["taskkill", "/PID", str(process.pid), "/T", "/F"])
        except (OSError, subprocess.SubprocessError):
            try:
                process.kill()
            except OSError:
                pass


def _os_killpg() -> SignalGroup:
    # Looked up by name: ``os.killpg`` does not exist on Windows and must still type-check there.
    killpg: SignalGroup | None = getattr(os, "killpg", None)
    if killpg is None:
        raise NotImplementedError("Este sistema no tiene grupos de procesos POSIX.")
    return killpg


def _run_quietly(argv: list[str]) -> object:
    return subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=_TASKKILL_TIMEOUT_SECONDS,
        check=False,
        creationflags=_CREATE_NO_WINDOW,
    )


def default_process_control(*, windows: bool, killpg: SignalGroup | None = None) -> ProcessControl:
    """The control for the platform: Windows, or POSIX for everything else."""
    if windows:
        return WindowsProcessControl()
    return PosixProcessControl(killpg=killpg)
