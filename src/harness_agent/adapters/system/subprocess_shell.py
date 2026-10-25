"""SubprocessShell: the common engine of the shell implementations (HU-01-04).

It runs one command in a child process with a maximum time, merges standard output and error into a
bounded text, and ends the whole process tree when the time runs out or when ``terminate_running``
is called. Subclasses only say which interpreter they are and how to build its command line.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import threading
from abc import abstractmethod
from collections.abc import Callable, Collection, Mapping
from pathlib import Path
from typing import IO

from harness_agent.adapters.system.process_control import ProcessControl, default_process_control
from harness_agent.adapters.system.shell_environment import child_environment
from harness_agent.adapters.system.shell_errors import ShellStartError
from harness_agent.adapters.system.shell_limits import (
    GRACE_SECONDS,
    MAX_OUTPUT_CHARS,
    NOTICE_RESERVE_CHARS,
    READER_JOIN_SECONDS,
)
from harness_agent.adapters.system.shell_output import OutputCollector
from harness_agent.core import Shell, ShellResult

_READ_CHUNK_BYTES = 65_536
_FALLBACK_EXIT_CODE = -1
_FORCE_WAIT_SECONDS = 5.0


class SubprocessShell(Shell):
    """Run commands through an interpreter found on the system."""

    def __init__(
        self,
        cwd: Path,
        *,
        environ: Mapping[str, str] | None = None,
        removed_env: Collection[str] = (),
        grace_seconds: float = GRACE_SECONDS,
        max_output_chars: int = MAX_OUTPUT_CHARS,
        which: Callable[[str], str | None] = shutil.which,
        control: ProcessControl | None = None,
    ) -> None:
        """Create the shell.

        Args:
            cwd: Folder every command starts in; it must exist when a command runs.
            environ: Environment to start from (empty when omitted); it is not modified.
            removed_env: Names of the variables the command must not see.
            grace_seconds: Wait between the polite stop request and the forced one.
            max_output_chars: Longest output returned.
            which: Finds an executable by name; injectable for tests.
            control: How to stop a process tree; the one of the running system when omitted.

        Raises:
            ValueError: ``grace_seconds`` is not positive or ``max_output_chars`` cannot hold
                the notice of a cut output.
        """
        if not grace_seconds > 0:
            raise ValueError("El tiempo de gracia debe ser mayor que cero.")
        if max_output_chars <= NOTICE_RESERVE_CHARS:
            raise ValueError(
                f"El máximo de salida debe ser mayor que {NOTICE_RESERVE_CHARS} caracteres."
            )
        windows = os.name == "nt"
        self._cwd = cwd
        self._environment = child_environment(environ or {}, removed_env, windows=windows)
        self._grace = grace_seconds
        self._max_output = max_output_chars
        self._which = which
        self._control = control if control is not None else default_process_control(windows=windows)
        self._lock = threading.Lock()
        self._running: subprocess.Popen[bytes] | None = None

    @property
    @abstractmethod
    def _executable_names(self) -> tuple[str, ...]:
        """Candidate executables, in order of preference."""

    @abstractmethod
    def _argv(self, executable: str, command: str) -> list[str]:
        """The argument vector that makes the interpreter run ``command``."""

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        """Run ``command`` and wait at most ``timeout_seconds``.

        Raises:
            ValueError: The time is not a positive, finite number.
            ShellStartError: The interpreter was not found or could not be started.
        """
        _check_timeout(timeout_seconds)
        executable = self._find_executable()
        process = self._start(self._argv(executable, command))
        collector = OutputCollector(self._max_output)
        reader = threading.Thread(
            target=_pump, args=(process.stdout, collector), name="shell-output", daemon=True
        )
        reader.start()
        timed_out = False
        try:
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                # The command may have ended between the timeout and now: that is not a timeout.
                timed_out = process.poll() is None
                if timed_out:
                    self._stop_tree(process)
            self._control.cleanup(process)
            self._drain(reader, process)
        finally:
            with self._lock:
                self._running = None
        code = process.returncode if process.returncode is not None else _FALLBACK_EXIT_CODE
        return ShellResult(exit_code=code, output=collector.finish(), timed_out=timed_out)

    def terminate_running(self) -> None:
        """End the command in progress and its tree; ``execute`` then returns. Thread-safe."""
        with self._lock:
            process = self._running
            if process is None:
                return
        self._control.force_stop(process)

    def _find_executable(self) -> str:
        for name in self._executable_names:
            found = self._which(name)
            if found:
                return found
        raise ShellStartError(f"No se encontró el intérprete ({self.interpreter_name}).")

    def _start(self, argv: list[str]) -> subprocess.Popen[bytes]:
        try:
            process = subprocess.Popen(
                argv,
                cwd=self._cwd,
                env=self._environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
                **self._control.popen_options(),
            )
        except OSError as error:
            # The message names the interpreter only: the path and the command stay out of it.
            raise ShellStartError(
                f"No se pudo iniciar el intérprete ({self.interpreter_name})."
            ) from error
        with self._lock:
            self._running = process
        return process

    def _stop_tree(self, process: subprocess.Popen[bytes]) -> None:
        self._control.request_stop(process)
        try:
            process.wait(timeout=self._grace)
        except subprocess.TimeoutExpired:
            pass
        # Forced even if the leader ended: its children may still hold the output open.
        self._control.force_stop(process)
        try:
            process.wait(timeout=_FORCE_WAIT_SECONDS)
        except subprocess.TimeoutExpired:
            pass

    def _drain(self, reader: threading.Thread, process: subprocess.Popen[bytes]) -> None:
        reader.join(READER_JOIN_SECONDS)
        if reader.is_alive():
            # A survivor keeps the pipe open: end the tree and stop waiting for the rest.
            self._control.force_stop(process)
            reader.join(READER_JOIN_SECONDS)


def _check_timeout(value: float) -> None:
    ok = (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )
    if not ok:
        raise ValueError("El tiempo máximo debe ser un número mayor que cero.")


def _pump(stream: IO[bytes] | None, collector: OutputCollector) -> None:
    if stream is None:
        return
    try:
        while True:
            chunk = stream.read(_READ_CHUNK_BYTES)
            if not chunk:
                break
            collector.feed(chunk)
    except (OSError, ValueError):
        pass
