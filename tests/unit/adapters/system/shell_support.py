"""A shell for the tests of the common engine: it runs Python code on every system (HU-01-04).

``PythonShell`` is a minimal ``SubprocessShell`` whose "interpreter" is the Python running the
tests, so the engine (timeout, output, environment, termination) is exercised with real processes
and without depending on bash or PowerShell.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Collection, Mapping
from pathlib import Path

from harness_agent.adapters.system.process_control import ProcessControl
from harness_agent.adapters.system.subprocess_shell import SubprocessShell


def python_found(name: str) -> str | None:
    """A ``which`` that always finds the Python running the tests."""
    return sys.executable


class PythonShell(SubprocessShell):
    """Runs the command as Python code."""

    @property
    def interpreter_name(self) -> str:
        return "python"

    @property
    def _executable_names(self) -> tuple[str, ...]:
        return ("python-test",)

    def _argv(self, executable: str, command: str) -> list[str]:
        return [executable, "-c", command]


def make_shell(
    cwd: Path,
    *,
    environ: Mapping[str, str] | None = None,
    removed_env: Collection[str] = (),
    grace_seconds: float = 0.3,
    max_output_chars: int = 20_000,
    which: Callable[[str], str | None] = python_found,
    control: ProcessControl | None = None,
) -> PythonShell:
    """A ``PythonShell`` with the real environment of the tests unless told otherwise."""
    return PythonShell(
        cwd,
        environ=dict(os.environ) if environ is None else environ,
        removed_env=removed_env,
        grace_seconds=grace_seconds,
        max_output_chars=max_output_chars,
        which=which,
        control=control,
    )
