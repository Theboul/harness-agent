"""SubprocessShell: the common engine, with real processes (HU-01-04 / T005, T006).

The shell under test is a ``PythonShell`` whose "interpreter" is the Python running the tests, so
the same tests run on Linux and Windows without bash or PowerShell.
"""

from __future__ import annotations

import io
import subprocess
import threading
import time
from pathlib import Path

import pytest

from harness_agent.adapters.system import subprocess_shell
from harness_agent.adapters.system.process_control import PosixProcessControl, ProcessControl
from harness_agent.adapters.system.shell_errors import ShellStartError
from harness_agent.adapters.system.shell_output import OutputCollector
from harness_agent.adapters.system.subprocess_shell import SubprocessShell
from tests.unit.adapters.system.process_support import IS_WINDOWS, wait_until_dead
from tests.unit.adapters.system.shell_support import make_shell

SENTINEL = "VALOR-DE-PRUEBA-123"


class TestResult:
    def test_exit_code_zero(self, tmp_path: Path) -> None:
        result = make_shell(tmp_path).execute("print('hola')", 10)
        assert (result.exit_code, result.timed_out) == (0, False)
        assert result.output.strip() == "hola"

    def test_exit_code_not_zero(self, tmp_path: Path) -> None:
        result = make_shell(tmp_path).execute("import sys; sys.exit(3)", 10)
        assert (result.exit_code, result.timed_out) == (3, False)

    def test_error_output_is_merged_with_standard_output(self, tmp_path: Path) -> None:
        code = "import sys; print('uno'); sys.stdout.flush(); print('dos', file=sys.stderr)"
        output = make_shell(tmp_path).execute(code, 10).output
        assert "uno" in output
        assert "dos" in output

    def test_non_ascii_output_is_decoded(self, tmp_path: Path) -> None:
        code = "import sys; sys.stdout.buffer.write('canción ñ €'.encode('utf-8'))"
        assert make_shell(tmp_path).execute(code, 10).output == "canción ñ €"

    def test_the_command_starts_in_the_given_folder(self, tmp_path: Path) -> None:
        output = make_shell(tmp_path).execute("import os; print(os.getcwd())", 10).output
        assert Path(output.strip()).resolve() == tmp_path.resolve()

    def test_the_input_is_closed(self, tmp_path: Path) -> None:
        code = "import sys; print(repr(sys.stdin.read()))"
        assert make_shell(tmp_path).execute(code, 10).output.strip() == "''"

    def test_a_command_that_ends_early_does_not_wait_for_the_limit(self, tmp_path: Path) -> None:
        started = time.monotonic()
        make_shell(tmp_path).execute("pass", 30)
        assert time.monotonic() - started < 10


class TestEnvironment:
    def test_the_command_sees_the_given_environment_without_the_removed_names(
        self, tmp_path: Path
    ) -> None:
        import os

        environ = {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "VISIBLE": "si",
            "SECRET_VAR": SENTINEL,
        }
        shell = make_shell(tmp_path, environ=environ, removed_env={"SECRET_VAR"})
        code = "import os; print(os.environ.get('VISIBLE'), os.environ.get('SECRET_VAR'))"
        assert shell.execute(code, 10).output.strip() == "si None"

    def test_the_value_of_a_removed_variable_never_reaches_the_output(self, tmp_path: Path) -> None:
        import os

        environ = {"SYSTEMROOT": os.environ.get("SYSTEMROOT", ""), "SECRET_VAR": SENTINEL}
        shell = make_shell(tmp_path, environ=environ, removed_env={"SECRET_VAR"})
        code = "import os; print(sorted(os.environ.items()))"
        assert SENTINEL not in shell.execute(code, 10).output


class TestValidation:
    @pytest.mark.parametrize("value", [0, -1, -0.5, float("nan"), float("inf"), "5", None, True])
    def test_an_invalid_time_is_rejected(self, tmp_path: Path, value: object) -> None:
        with pytest.raises(ValueError, match="tiempo máximo"):
            make_shell(tmp_path).execute("pass", value)  # type: ignore[arg-type]

    @pytest.mark.parametrize("grace", [0, -1.0, float("nan")])
    def test_an_invalid_grace_is_rejected(self, tmp_path: Path, grace: float) -> None:
        with pytest.raises(ValueError, match="gracia"):
            make_shell(tmp_path, grace_seconds=grace)

    def test_an_output_limit_without_room_for_the_notice_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="máximo de salida"):
            make_shell(tmp_path, max_output_chars=100)

    def test_a_missing_interpreter_is_a_start_error_without_paths(self, tmp_path: Path) -> None:
        shell = make_shell(tmp_path, which=lambda name: None)
        with pytest.raises(ShellStartError) as caught:
            shell.execute(SENTINEL, 10)
        message = str(caught.value)
        assert "python" in message
        assert SENTINEL not in message
        assert str(tmp_path) not in message

    def test_a_system_failure_when_starting_is_a_start_error(self, tmp_path: Path) -> None:
        shell = make_shell(tmp_path, which=lambda name: str(tmp_path / "no-existe.exe"))
        with pytest.raises(ShellStartError) as caught:
            shell.execute(SENTINEL, 10)
        message = str(caught.value)
        assert SENTINEL not in message
        assert str(tmp_path) not in message

    def test_a_missing_folder_is_a_start_error(self, tmp_path: Path) -> None:
        with pytest.raises(ShellStartError):
            make_shell(tmp_path / "no-existe").execute("pass", 10)

    def test_the_first_candidate_that_exists_wins(self, tmp_path: Path) -> None:
        import sys

        class TwoNames(type(make_shell(tmp_path))):  # type: ignore[misc]
            @property
            def _executable_names(self) -> tuple[str, ...]:
                return ("first", "second")

        asked: list[str] = []

        def which(name: str) -> str | None:
            asked.append(name)
            return sys.executable if name == "second" else None

        shell = TwoNames(tmp_path, which=which)
        assert shell.execute("print(1)", 10).output.strip() == "1"
        assert asked == ["first", "second"]

    def test_no_shell_string_is_used(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, object] = {}
        real = subprocess.Popen

        def spy(argv: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
            seen.update(kwargs)
            seen["argv"] = argv
            return real(argv, **kwargs)  # type: ignore[call-overload,no-any-return]

        monkeypatch.setattr(subprocess, "Popen", spy)
        make_shell(tmp_path).execute("pass", 10)
        assert isinstance(seen["argv"], list)
        assert not seen.get("shell")


class TestTimeout:
    def test_a_command_that_exceeds_the_limit_is_marked_and_ended(self, tmp_path: Path) -> None:
        started = time.monotonic()
        result = make_shell(tmp_path).execute("import time; time.sleep(60)", 1)
        assert result.timed_out is True
        assert time.monotonic() - started < 1 + 5

    def test_partial_output_before_the_hang_is_kept(self, tmp_path: Path) -> None:
        code = "import time; print('antes', flush=True); time.sleep(60)"
        result = make_shell(tmp_path).execute(code, 1)
        assert result.timed_out is True
        assert "antes" in result.output

    def test_the_grandchild_dies_with_the_command(self, tmp_path: Path) -> None:
        code = (
            "import subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "print(child.pid, flush=True)\n"
            "time.sleep(60)\n"
        )
        result = make_shell(tmp_path).execute(code, 2)
        assert result.timed_out is True
        assert wait_until_dead(int(result.output.split()[0])), "the grandchild survived"

    def test_a_background_process_left_by_a_finished_command_is_cleaned_up(
        self, tmp_path: Path
    ) -> None:
        code = (
            "import subprocess, sys\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],\n"
            "                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,\n"
            "                         stderr=subprocess.DEVNULL)\n"
            "print(child.pid, flush=True)\n"
        )
        result = make_shell(tmp_path).execute(code, 10)
        assert result.timed_out is False
        if IS_WINDOWS:
            pytest.skip("Windows cannot reach a child already detached from its parent")
        assert wait_until_dead(int(result.output.split()[0])), "the background process survived"

    def test_a_command_just_under_the_limit_is_not_marked(self, tmp_path: Path) -> None:
        result = make_shell(tmp_path).execute("import time; time.sleep(0.3)", 5)
        assert (result.exit_code, result.timed_out) == (0, False)

    @pytest.mark.skipif(IS_WINDOWS, reason="POSIX only: SIGTERM ignored, then SIGKILL")
    def test_a_command_that_ignores_sigterm_is_killed(self, tmp_path: Path) -> None:
        code = (
            "import signal, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "print('listo', flush=True)\n"
            "time.sleep(60)\n"
        )
        shell = make_shell(tmp_path, grace_seconds=0.3, control=PosixProcessControl())
        started = time.monotonic()
        result = shell.execute(code, 1.5)
        assert result.timed_out is True
        assert result.exit_code == -9
        assert time.monotonic() - started < 6

    @pytest.mark.skipif(not IS_WINDOWS, reason="Windows only: taskkill ends the tree")
    def test_windows_ends_the_tree_with_taskkill(self, tmp_path: Path) -> None:
        result = make_shell(tmp_path).execute("import time; time.sleep(60)", 1)
        assert result.timed_out is True
        assert result.exit_code != 0


class TestTerminateRunning:
    def test_without_a_running_command_it_does_nothing(self, tmp_path: Path) -> None:
        make_shell(tmp_path).terminate_running()

    def test_it_ends_the_command_in_progress_from_another_thread(self, tmp_path: Path) -> None:
        shell = make_shell(tmp_path)
        threading.Timer(1.0, shell.terminate_running).start()
        started = time.monotonic()
        result = shell.execute("import time; time.sleep(60)", 60)
        assert time.monotonic() - started < 10
        assert result.timed_out is False
        assert result.exit_code != 0

    def test_it_ends_the_tree_too(self, tmp_path: Path) -> None:
        code = (
            "import subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "print(child.pid, flush=True)\n"
            "time.sleep(60)\n"
        )
        shell = make_shell(tmp_path)
        threading.Timer(1.5, shell.terminate_running).start()
        result = shell.execute(code, 60)
        assert wait_until_dead(int(result.output.split()[0])), "the grandchild survived"

    def test_the_shell_is_reusable_after_a_termination(self, tmp_path: Path) -> None:
        shell = make_shell(tmp_path)
        threading.Timer(0.5, shell.terminate_running).start()
        shell.execute("import time; time.sleep(60)", 60)
        assert shell.execute("print('otra')", 10).output.strip() == "otra"


def test_the_base_class_is_abstract(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        SubprocessShell(tmp_path)  # type: ignore[abstract]


class _DoNothingControl(ProcessControl):
    """A control that cannot stop anything; the test ends the process itself."""

    def __init__(self) -> None:
        self.processes: list[subprocess.Popen[bytes]] = []

    def popen_options(self) -> dict[str, object]:
        return {}

    def request_stop(self, process: subprocess.Popen[bytes]) -> None:
        self.processes.append(process)

    def force_stop(self, process: subprocess.Popen[bytes]) -> None:
        self.processes.append(process)


class TestStopThatDoesNotWork:
    def test_execute_gives_up_waiting_instead_of_hanging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(subprocess_shell, "READER_JOIN_SECONDS", 0.2)
        monkeypatch.setattr(subprocess_shell, "_FORCE_WAIT_SECONDS", 0.2)
        control = _DoNothingControl()
        shell = make_shell(tmp_path, grace_seconds=0.1, control=control)
        try:
            started = time.monotonic()
            result = shell.execute("import time; time.sleep(60)", 0.3)
            assert time.monotonic() - started < 5
            assert result.timed_out is True
            assert result.exit_code == -1
        finally:
            for process in control.processes:
                process.kill()
                if process.stdout is not None:
                    process.stdout.close()


class _BrokenStream(io.RawIOBase):
    def readinto(self, buffer: object) -> int:
        raise OSError("tubería rota")

    def read(self, size: int = -1) -> bytes:
        raise ValueError("flujo cerrado")


class TestPump:
    def test_a_missing_stream_is_ignored(self) -> None:
        subprocess_shell._pump(None, OutputCollector())

    def test_a_stream_that_fails_ends_the_reading_quietly(self) -> None:
        collector = OutputCollector()
        subprocess_shell._pump(_BrokenStream(), collector)  # type: ignore[arg-type]
        assert collector.total_chars == 0


class TestEndsAtTheLimit:
    def test_a_command_that_ends_as_the_limit_expires_is_not_a_timeout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class LatePopen(subprocess.Popen):  # type: ignore[type-arg]
            """The first wait reports the limit even though the command has just ended."""

            late = True

            def wait(self, timeout: float | None = None) -> int:
                if LatePopen.late:
                    LatePopen.late = False
                    super().wait()
                    raise subprocess.TimeoutExpired("cmd", timeout or 0)
                return int(super().wait(timeout))

        monkeypatch.setattr(subprocess, "Popen", LatePopen)
        result = make_shell(tmp_path).execute("print('fin')", 5)
        assert (result.exit_code, result.timed_out) == (0, False)
        assert result.output.strip() == "fin"


HUGE_MEGABYTES = 100
WRITE_HUGE = (
    "import sys\n"
    "out = sys.stdout.buffer\n"
    "out.write(b'INICIO\\n')\n"
    "line = b'x' * 1023 + b'\\n'\n"
    f"for _ in range({HUGE_MEGABYTES} * 1024):\n"
    "    out.write(line)\n"
    "out.write(b'FINAL\\n')\n"
    "out.flush()\n"
)


class TestBoundedOutput:
    def test_a_huge_output_is_cut_with_head_tail_and_notice(self, tmp_path: Path) -> None:
        import re
        import tracemalloc

        tracemalloc.start()
        try:
            started = time.monotonic()
            result = make_shell(tmp_path).execute(WRITE_HUGE, 120)
            elapsed = time.monotonic() - started
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert (result.exit_code, result.timed_out) == (0, False)
        assert len(result.output) <= 20_000
        assert result.output.startswith("INICIO")
        assert result.output.endswith("FINAL\n")
        match = re.search(r"\[salida recortada: se omitieron (\d+) caracteres\]", result.output)
        assert match is not None
        total = len("INICIO\n") + HUGE_MEGABYTES * 1024 * 1024 + len("FINAL\n")
        shown = len(result.output) - len(match.group(0)) - 2
        assert int(match.group(1)) + shown == total
        assert peak < 20 * 1024 * 1024, f"retained {peak} bytes"
        assert elapsed < 60

    def test_a_short_output_has_no_notice(self, tmp_path: Path) -> None:
        output = make_shell(tmp_path).execute("print('corto')", 10).output
        assert "salida recortada" not in output

    def test_invalid_bytes_become_replacement_characters(self, tmp_path: Path) -> None:
        code = "import sys; sys.stdout.buffer.write(b'a\\xff\\xfeb')"
        result = make_shell(tmp_path).execute(code, 10)
        assert result.exit_code == 0
        assert result.output == "a\ufffd\ufffdb"

    def test_the_notice_also_appears_with_a_non_zero_exit_code(self, tmp_path: Path) -> None:
        code = "import sys; sys.stdout.write('x' * 100000); sys.exit(3)"
        result = make_shell(tmp_path).execute(code, 10)
        assert result.exit_code == 3
        assert "salida recortada" in result.output
        assert len(result.output) <= 20_000

    def test_the_notice_also_appears_with_a_timeout(self, tmp_path: Path) -> None:
        code = (
            "import sys, time\nsys.stdout.write('x' * 100000); sys.stdout.flush()\ntime.sleep(60)\n"
        )
        result = make_shell(tmp_path).execute(code, 2)
        assert result.timed_out is True
        assert "salida recortada" in result.output
        assert len(result.output) <= 20_000
