"""Choosing the shell that fits the operating system (HU-01-04)."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Collection, Mapping
from pathlib import Path

from harness_agent.adapters.system.bash_shell import BashShell
from harness_agent.adapters.system.powershell_shell import PowerShellShell
from harness_agent.adapters.system.process_control import ProcessControl
from harness_agent.adapters.system.shell_limits import GRACE_SECONDS, MAX_OUTPUT_CHARS
from harness_agent.adapters.system.subprocess_shell import SubprocessShell

_WINDOWS = "Windows"
_POWERSHELL = "powershell"
_BASH = "bash"


def interpreter_for(system_name: str) -> str:
    """Name of the interpreter used on ``system_name`` (``platform.system()``)."""
    return _POWERSHELL if system_name == _WINDOWS else _BASH


def select_shell(
    system_name: str,
    *,
    cwd: Path,
    environ: Mapping[str, str] | None = None,
    removed_env: Collection[str] = (),
    grace_seconds: float = GRACE_SECONDS,
    max_output_chars: int = MAX_OUTPUT_CHARS,
    which: Callable[[str], str | None] = shutil.which,
    control: ProcessControl | None = None,
) -> SubprocessShell:
    """PowerShell on Windows, bash on everything else.

    Args:
        system_name: The name ``platform.system()`` returns.
        cwd: Folder every command starts in.
        environ: Environment the commands start from.
        removed_env: Variables the commands must not see.
        grace_seconds: Wait between the polite and the forced stop.
        max_output_chars: Longest output returned.
        which: Finds an executable by name.
        control: How to stop a process tree; the one of the running system when omitted.
    """
    shell_class = PowerShellShell if interpreter_for(system_name) == _POWERSHELL else BashShell
    return shell_class(
        cwd,
        environ=environ,
        removed_env=removed_env,
        grace_seconds=grace_seconds,
        max_output_chars=max_output_chars,
        which=which,
        control=control,
    )
