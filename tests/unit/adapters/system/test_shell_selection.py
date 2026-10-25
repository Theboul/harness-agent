"""select_shell and interpreter_for (HU-01-04 / T009)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness_agent.adapters.system.bash_shell import BashShell
from harness_agent.adapters.system.powershell_shell import PowerShellShell
from harness_agent.adapters.system.shell_selection import interpreter_for, select_shell
from tests.unit.adapters.system.shell_support import python_found


def test_windows_gets_powershell(tmp_path: Path) -> None:
    shell = select_shell("Windows", cwd=tmp_path)
    assert isinstance(shell, PowerShellShell)
    assert shell.interpreter_name == "powershell"


def test_linux_gets_bash(tmp_path: Path) -> None:
    shell = select_shell("Linux", cwd=tmp_path)
    assert isinstance(shell, BashShell)
    assert shell.interpreter_name == "bash"


@pytest.mark.parametrize("system_name", ["Darwin", "FreeBSD", "", "SunOS"])
def test_any_other_system_gets_bash(tmp_path: Path, system_name: str) -> None:
    assert isinstance(select_shell(system_name, cwd=tmp_path), BashShell)


@pytest.mark.parametrize("system_name", ["Windows", "Linux", "Darwin", ""])
def test_interpreter_for_matches_the_chosen_shell(tmp_path: Path, system_name: str) -> None:
    assert interpreter_for(system_name) == select_shell(system_name, cwd=tmp_path).interpreter_name


def test_the_folder_the_environment_and_the_removed_names_reach_the_shell(tmp_path: Path) -> None:
    environ = {"SYSTEMROOT": os.environ.get("SYSTEMROOT", ""), "QUEDA": "1", "SE_VA": "2"}
    shell = select_shell(
        "Linux",
        cwd=tmp_path,
        environ=environ,
        removed_env={"SE_VA"},
        which=python_found,
    )
    assert shell._cwd == tmp_path
    assert shell._environment.get("QUEDA") == "1"
    assert "SE_VA" not in shell._environment


def test_the_finder_and_the_limits_reach_the_shell(tmp_path: Path) -> None:
    seen: list[str] = []

    def which(name: str) -> str | None:
        seen.append(name)
        return None

    shell = select_shell(
        "Linux", cwd=tmp_path, which=which, grace_seconds=0.5, max_output_chars=500
    )
    assert shell._grace == 0.5
    assert shell._max_output == 500
    assert shell._which is which
