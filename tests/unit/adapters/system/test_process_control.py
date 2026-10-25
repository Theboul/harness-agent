"""ProcessControl: stopping a command and everything it started (HU-01-04 / T004).

The synthetic tests run on any system with a fake process and injected system calls. The real ones
start a parent that leaves a child holding the output pipe and check that the whole tree dies.
"""

from __future__ import annotations

import os
import signal
import subprocess
from dataclasses import dataclass, field
from typing import Any

import pytest

from harness_agent.adapters.system.process_control import (
    PosixProcessControl,
    ProcessControl,
    WindowsProcessControl,
    default_process_control,
)
from tests.unit.adapters.system.process_support import (
    GRANDCHILD_PARENT_CODE,
    IS_WINDOWS,
    python_command,
    wait_until_dead,
)


@dataclass
class FakeProcess:
    pid: int = 4242
    signals: list[int] = field(default_factory=list)
    killed: int = 0
    fail_signal: bool = False
    fail_kill: bool = False

    def send_signal(self, number: int) -> None:
        if self.fail_signal:
            raise OSError("sin proceso")
        self.signals.append(number)

    def kill(self) -> None:
        if self.fail_kill:
            raise OSError("sin proceso")
        self.killed += 1


class TestPosix:
    def make(self, calls: list[tuple[int, int]], fail: type[Exception] | None = None) -> Any:
        def killpg(group: int, number: int) -> None:
            calls.append((group, number))
            if fail is not None:
                raise fail()

        return PosixProcessControl(killpg=killpg, force_signal=9)

    def test_the_command_gets_its_own_session(self) -> None:
        assert PosixProcessControl(killpg=lambda group, number: None).popen_options() == {
            "start_new_session": True
        }

    def test_request_stop_asks_the_whole_group_to_terminate(self) -> None:
        calls: list[tuple[int, int]] = []
        self.make(calls).request_stop(FakeProcess(pid=77))
        assert calls == [(77, signal.SIGTERM)]

    def test_force_stop_kills_the_whole_group(self) -> None:
        calls: list[tuple[int, int]] = []
        self.make(calls).force_stop(FakeProcess(pid=77))
        assert calls == [(77, 9)]

    def test_cleanup_kills_what_the_command_left_behind(self) -> None:
        calls: list[tuple[int, int]] = []
        self.make(calls).cleanup(FakeProcess(pid=77))
        assert [group for group, _ in calls] == [77]

    @pytest.mark.parametrize("error", [ProcessLookupError, PermissionError])
    def test_a_group_that_is_already_gone_is_not_an_error(self, error: type[Exception]) -> None:
        control = self.make([], fail=error)
        process: Any = FakeProcess()
        control.request_stop(process)
        control.force_stop(process)
        control.cleanup(process)


class TestWindows:
    def test_the_command_gets_its_own_process_group_and_no_window(self) -> None:
        options = WindowsProcessControl(run_taskkill=lambda argv: None).popen_options()
        flags = options["creationflags"]
        assert flags == 0x00000200 | 0x08000000

    def test_request_stop_sends_ctrl_break(self) -> None:
        process = FakeProcess()
        control = WindowsProcessControl(run_taskkill=lambda argv: None, ctrl_break=21)
        control.request_stop(process)  # type: ignore[arg-type]
        assert process.signals == [21]

    def test_a_process_that_cannot_be_signalled_is_not_an_error(self) -> None:
        control = WindowsProcessControl(run_taskkill=lambda argv: None, ctrl_break=21)
        control.request_stop(FakeProcess(fail_signal=True))  # type: ignore[arg-type]

    def test_force_stop_kills_the_tree_with_taskkill(self) -> None:
        argvs: list[list[str]] = []
        control = WindowsProcessControl(run_taskkill=argvs.append)
        control.force_stop(FakeProcess(pid=99))  # type: ignore[arg-type]
        assert argvs == [["taskkill", "/PID", "99", "/T", "/F"]]

    @pytest.mark.parametrize("error", [OSError, subprocess.SubprocessError])
    def test_if_taskkill_fails_the_direct_process_is_killed(self, error: type[Exception]) -> None:
        def failing(argv: list[str]) -> None:
            raise error()

        process = FakeProcess()
        WindowsProcessControl(run_taskkill=failing).force_stop(process)  # type: ignore[arg-type]
        assert process.killed == 1

    def test_if_nothing_works_force_stop_still_does_not_raise(self) -> None:
        def failing(argv: list[str]) -> None:
            raise OSError()

        process = FakeProcess(fail_kill=True)
        WindowsProcessControl(run_taskkill=failing).force_stop(process)  # type: ignore[arg-type]

    def test_cleanup_does_nothing(self) -> None:
        argvs: list[list[str]] = []
        process = FakeProcess()
        WindowsProcessControl(run_taskkill=argvs.append).cleanup(process)  # type: ignore[arg-type]
        assert argvs == []
        assert process.killed == 0


class TestSystemKillpg:
    def test_with_os_killpg_the_posix_control_uses_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[int, int]] = []
        monkeypatch.setattr(
            os, "killpg", lambda group, number: calls.append((group, number)), raising=False
        )
        PosixProcessControl(force_signal=9).force_stop(FakeProcess(pid=5))  # type: ignore[arg-type]
        assert calls == [(5, 9)]

    def test_without_os_killpg_the_posix_control_cannot_be_built(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delattr(os, "killpg", raising=False)
        with pytest.raises(NotImplementedError, match="grupos de procesos"):
            PosixProcessControl()


class TestSelection:
    def test_windows_gets_the_windows_control(self) -> None:
        assert isinstance(default_process_control(windows=True), WindowsProcessControl)

    def test_other_systems_get_the_posix_control(self) -> None:
        assert isinstance(
            default_process_control(windows=False, killpg=lambda group, number: None),
            PosixProcessControl,
        )

    def test_both_are_process_controls(self) -> None:
        assert issubclass(PosixProcessControl, ProcessControl)
        assert issubclass(WindowsProcessControl, ProcessControl)


class TestRealProcesses:
    """The native control stops a parent and the child that keeps the pipe open."""

    def test_force_stop_kills_the_parent_and_its_child(self) -> None:
        control = default_process_control(windows=IS_WINDOWS)
        process = subprocess.Popen(
            python_command(GRANDCHILD_PARENT_CODE),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **control.popen_options(),
        )
        try:
            assert process.stdout is not None
            child_pid = int(process.stdout.readline().strip())
            control.force_stop(process)
            process.wait(timeout=8)
            assert wait_until_dead(child_pid), "the child of the command survived"
        finally:
            process.kill()
            if process.stdout is not None:
                process.stdout.close()

    @pytest.mark.skipif(IS_WINDOWS, reason="POSIX only: a polite SIGTERM to the process group")
    def test_request_stop_terminates_the_group_on_posix(self) -> None:
        control = default_process_control(windows=False)
        process = subprocess.Popen(
            python_command(GRANDCHILD_PARENT_CODE),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            **control.popen_options(),
        )
        try:
            assert process.stdout is not None
            child_pid = int(process.stdout.readline().strip())
            control.request_stop(process)
            assert process.wait(timeout=8) == -signal.SIGTERM
            assert wait_until_dead(child_pid)
        finally:
            process.kill()
            if process.stdout is not None:
                process.stdout.close()

    @pytest.mark.skipif(not IS_WINDOWS, reason="Windows only: CTRL_BREAK to the process group")
    def test_request_stop_is_best_effort_on_windows(self) -> None:
        # CTRL_BREAK needs a console attached to this process; runners and tools often have none.
        # The polite step may therefore do nothing, and force_stop is what guarantees the end.
        control = default_process_control(windows=True)
        process = subprocess.Popen(
            python_command("import time; time.sleep(60)"),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            **control.popen_options(),
        )
        try:
            control.request_stop(process)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                control.force_stop(process)
                process.wait(timeout=8)
            assert process.returncode is not None
        finally:
            process.kill()
            if process.stdout is not None:
                process.stdout.close()
