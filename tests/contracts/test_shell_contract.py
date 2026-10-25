"""Contract of the ``Shell`` port, run against the real native shell and both implementations.

The same battery checks the native shell of the system running the tests (real processes, no
skips) and ``BashShell`` and ``PowerShellShell`` with a fake finder and a fake process, so the
behavior the port promises is the same wherever it runs (HU-01-04 / T009, AC-02, AC-04).
"""

from __future__ import annotations

import io
import os
import platform
import shutil
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system.process_control import ProcessControl
from harness_agent.adapters.system.shell_errors import ShellStartError
from harness_agent.adapters.system.shell_selection import select_shell
from harness_agent.core import Shell, ShellResult

NATIVE = platform.system()
IS_WINDOWS = NATIVE == "Windows"

NATIVE_COMMANDS = {
    "ok": "echo hola",
    "exit3": "exit 3",
    "combined": (
        "echo uno; [Console]::Error.WriteLine('dos')" if IS_WINDOWS else "echo uno; echo dos 1>&2"
    ),
    "hang": "Start-Sleep -Seconds 60" if IS_WINDOWS else "sleep 60",
}
TIMEOUT_LIMIT = 4 if IS_WINDOWS else 1
GENEROUS = 90


@dataclass
class Scenario:
    output: bytes = b""
    exit_code: int = 0
    hangs: bool = False


class FakeProcess:
    """Stands in for ``subprocess.Popen``: scripted output, and a hang that ends when stopped."""

    def __init__(self, scenario: Scenario) -> None:
        self.pid = 4242
        self.stdout = io.BytesIO(scenario.output)
        self.returncode: int | None = None
        self._scenario = scenario
        self.stopped = False

    def wait(self, timeout: float | None = None) -> int:
        if self._scenario.hangs and not self.stopped:
            raise subprocess.TimeoutExpired("fake", timeout or 0)
        self.returncode = -9 if self.stopped else self._scenario.exit_code
        return self.returncode

    def poll(self) -> int | None:
        return self.returncode


class FakeControl(ProcessControl):
    def popen_options(self) -> dict[str, Any]:
        return {}

    def request_stop(self, process: subprocess.Popen[bytes]) -> None:
        process.stopped = True  # type: ignore[attr-defined]

    def force_stop(self, process: subprocess.Popen[bytes]) -> None:
        process.stopped = True  # type: ignore[attr-defined]


@dataclass
class Rig:
    """One way of running the battery."""

    name: str
    system_name: str
    cwd: Path
    monkeypatch: pytest.MonkeyPatch
    native: bool
    scenarios: dict[str, Scenario] = field(default_factory=dict)

    def shell(self, *, found: bool = True) -> Shell:
        if self.native:
            finder = shutil.which if found else _nothing
            return select_shell(
                self.system_name, cwd=self.cwd, environ=dict(os.environ), which=finder
            )
        return select_shell(
            self.system_name,
            cwd=self.cwd,
            which=_fake_path if found else _nothing,
            grace_seconds=0.1,
            control=FakeControl(),
        )

    def run(self, case: str, limit: float = GENEROUS) -> ShellResult:
        if self.native:
            return self.shell().execute(NATIVE_COMMANDS[case], limit)
        scenario = self.scenarios[case]
        self.monkeypatch.setattr(subprocess, "Popen", lambda argv, **kw: FakeProcess(scenario))
        return self.shell().execute("ignored", limit)


def _nothing(name: str) -> str | None:
    return None


def _fake_path(name: str) -> str | None:
    return f"/fake/{name}"


FAKE_SCENARIOS = {
    "ok": Scenario(output=b"hola\n"),
    "exit3": Scenario(exit_code=3),
    "combined": Scenario(output=b"uno\ndos\n"),
    "hang": Scenario(output=b"antes\n", hangs=True),
}


@pytest.fixture(params=["native", "bash-fake", "powershell-fake"])
def rig(
    request: pytest.FixtureRequest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Rig]:
    name = request.param
    if name == "native":
        yield Rig(name, NATIVE, tmp_path, monkeypatch, native=True)
    else:
        system_name = "Linux" if name == "bash-fake" else "Windows"
        yield Rig(name, system_name, tmp_path, monkeypatch, native=False, scenarios=FAKE_SCENARIOS)


def test_the_result_has_the_shape_of_the_port(rig: Rig) -> None:
    result = rig.run("ok")
    assert isinstance(result, ShellResult)
    assert isinstance(result.exit_code, int)
    assert isinstance(result.output, str)
    assert isinstance(result.timed_out, bool)
    assert "hola" in result.output
    assert result.timed_out is False


def test_the_exit_code_is_reported(rig: Rig) -> None:
    result = rig.run("exit3")
    assert (result.exit_code, result.timed_out) == (3, False)


def test_a_success_has_exit_code_zero(rig: Rig) -> None:
    assert rig.run("ok").exit_code == 0


def test_standard_output_and_error_come_back_together(rig: Rig) -> None:
    output = rig.run("combined").output
    assert "uno" in output
    assert "dos" in output


def test_a_command_over_the_limit_is_marked_and_the_call_returns(rig: Rig) -> None:
    started = time.monotonic()
    result = rig.run("hang", TIMEOUT_LIMIT)
    assert result.timed_out is True
    assert time.monotonic() - started < TIMEOUT_LIMIT + 15


def test_a_missing_interpreter_is_a_start_error(rig: Rig) -> None:
    with pytest.raises(ShellStartError):
        rig.shell(found=False).execute("echo hola", 5)


def test_the_interpreter_name_is_not_empty(rig: Rig) -> None:
    assert rig.shell().interpreter_name in {"bash", "powershell"}


def test_a_bad_limit_is_a_value_error(rig: Rig) -> None:
    with pytest.raises(ValueError):
        rig.shell().execute("echo hola", 0)


def test_the_shell_is_a_port_implementation(rig: Rig) -> None:
    assert isinstance(rig.shell(), Shell)
