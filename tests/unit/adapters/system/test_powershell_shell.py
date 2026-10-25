"""PowerShellShell: command line and, on Windows, real behavior (HU-01-04 / T008)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from harness_agent.adapters.system.powershell_shell import PowerShellShell, build_script
from harness_agent.adapters.system.shell_errors import ShellStartError

needs_powershell = pytest.mark.skipif(
    sys.platform != "win32" or shutil.which("powershell") is None,
    reason="PowerShell real: Windows PowerShell only exists on Windows",
)


def windows_environ() -> dict[str, str]:
    return dict(os.environ)


def test_it_is_called_powershell(tmp_path: Path) -> None:
    assert PowerShellShell(tmp_path).interpreter_name == "powershell"


def test_pwsh_is_preferred_and_windows_powershell_is_the_fallback(tmp_path: Path) -> None:
    both = PowerShellShell(tmp_path, which=lambda name: f"/x/{name}")
    assert both._find_executable() == "/x/pwsh"
    only_old = PowerShellShell(
        tmp_path, which=lambda name: None if name == "pwsh" else f"/x/{name}"
    )
    assert only_old._find_executable() == "/x/powershell"


def test_without_any_powershell_it_is_a_start_error(tmp_path: Path) -> None:
    with pytest.raises(ShellStartError, match="powershell"):
        PowerShellShell(tmp_path, which=lambda name: None).execute("echo hola", 5)


def test_the_command_line_is_non_interactive_and_has_no_profile(tmp_path: Path) -> None:
    argv = PowerShellShell(tmp_path)._argv("pwsh", "Get-Date")
    assert argv[:6] == ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", argv[5]]
    assert len(argv) == 6
    assert "-EncodedCommand" not in argv


class TestScript:
    def test_the_command_is_intact_on_its_own_line(self) -> None:
        command = "Write-Output 'a' # comentario"
        lines = build_script(command).split("\n")
        assert command in lines

    def test_it_starts_with_the_utf8_prelude_and_ends_with_the_exit_code_epilogue(self) -> None:
        lines = build_script("x").split("\n")
        assert "UTF8" in lines[0]
        assert "ProgressPreference" in lines[0]
        assert "exit" in lines[-1]
        assert "LASTEXITCODE" in lines[-1]

    def test_a_multiline_command_is_kept(self) -> None:
        command = "$a = 1\n$a + 1"
        assert command in build_script(command)


@needs_powershell
class TestRealPowerShell:
    def shell(self, tmp_path: Path) -> PowerShellShell:
        return PowerShellShell(tmp_path, environ=windows_environ())

    def test_echo(self, tmp_path: Path) -> None:
        result = self.shell(tmp_path).execute("echo hola", 60)
        assert (result.exit_code, result.output.strip()) == (0, "hola")

    def test_exit_code(self, tmp_path: Path) -> None:
        assert self.shell(tmp_path).execute("exit 3", 60).exit_code == 3

    def test_a_native_executable_reports_its_code(self, tmp_path: Path) -> None:
        python = sys.executable
        result = self.shell(tmp_path).execute(f"& '{python}' -c 'import sys; sys.exit(7)'", 60)
        assert result.exit_code == 7

    def test_a_failing_cmdlet_is_a_failure_with_readable_text(self, tmp_path: Path) -> None:
        result = self.shell(tmp_path).execute("Get-Item .\\no-existe-nunca", 60)
        assert result.exit_code == 1
        assert "no-existe-nunca" in result.output
        assert "#< CLIXML" not in result.output

    def test_accents_survive(self, tmp_path: Path) -> None:
        result = self.shell(tmp_path).execute("echo 'áéñ ü'", 60)
        assert result.output.strip() == "áéñ ü"

    def test_single_and_double_quotes(self, tmp_path: Path) -> None:
        result = self.shell(tmp_path).execute("echo \"dos 'uno'\"; echo 'tres \"cuatro\"'", 60)
        assert result.output.splitlines()[:2] == ["dos 'uno'", 'tres "cuatro"']

    def test_a_command_ending_in_a_comment_still_reports_failure(self, tmp_path: Path) -> None:
        result = self.shell(tmp_path).execute("Get-Item .\\no-existe-nunca # nota", 60)
        assert result.exit_code == 1

    def test_the_folder_is_the_given_one(self, tmp_path: Path) -> None:
        result = self.shell(tmp_path).execute("(Get-Location).Path", 60)
        assert Path(result.output.strip()).samefile(tmp_path)

    def test_the_interpreter_is_powershell(self, tmp_path: Path) -> None:
        result = self.shell(tmp_path).execute("$PSVersionTable.PSVersion.Major", 60)
        assert int(result.output.strip()) >= 5
