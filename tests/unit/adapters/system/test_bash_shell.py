"""BashShell: command line and, where bash exists, real behavior (HU-01-04 / T007)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from harness_agent.adapters.system.bash_shell import BashShell
from harness_agent.adapters.system.shell_errors import ShellStartError

needs_bash = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None,
    reason="bash real: the shell chosen on Windows is PowerShell, and bash there may be WSL",
)


def test_it_is_called_bash(tmp_path: Path) -> None:
    assert BashShell(tmp_path).interpreter_name == "bash"


def test_the_command_line_has_no_profiles_and_the_command_intact(tmp_path: Path) -> None:
    shell = BashShell(tmp_path)
    argv = shell._argv("/usr/bin/bash", "echo 'a b' && ls")
    assert argv == ["/usr/bin/bash", "--noprofile", "--norc", "-c", "echo 'a b' && ls"]


def test_only_bash_is_looked_for(tmp_path: Path) -> None:
    asked: list[str] = []

    def which(name: str) -> str | None:
        asked.append(name)
        return None

    with pytest.raises(ShellStartError, match="bash"):
        BashShell(tmp_path, which=which).execute("echo hola", 5)
    assert asked == ["bash"]


@needs_bash
class TestRealBash:
    def test_the_interpreter_is_bash(self, tmp_path: Path) -> None:
        result = BashShell(tmp_path).execute("echo $BASH_VERSION", 20)
        assert result.exit_code == 0
        assert result.output.strip() != ""

    def test_echo(self, tmp_path: Path) -> None:
        assert BashShell(tmp_path).execute("echo hola", 20).output.strip() == "hola"

    def test_exit_code(self, tmp_path: Path) -> None:
        assert BashShell(tmp_path).execute("exit 3", 20).exit_code == 3

    def test_quotes_and_operators(self, tmp_path: Path) -> None:
        result = BashShell(tmp_path).execute("echo \"a 'b'\" && echo 'c \"d\"'", 20)
        assert result.output.split("\n")[:2] == ["a 'b'", 'c "d"']

    def test_profiles_are_not_loaded(self, tmp_path: Path) -> None:
        (tmp_path / ".bashrc").write_text("export PERFIL_CARGADO=si\n", encoding="utf-8")
        (tmp_path / ".bash_profile").write_text("export PERFIL_CARGADO=si\n", encoding="utf-8")
        environ = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
        result = BashShell(tmp_path, environ=environ).execute("echo [$PERFIL_CARGADO]", 20)
        assert result.output.strip() == "[]"

    def test_the_folder_is_the_given_one(self, tmp_path: Path) -> None:
        assert Path(BashShell(tmp_path).execute("pwd", 20).output.strip()).samefile(tmp_path)
