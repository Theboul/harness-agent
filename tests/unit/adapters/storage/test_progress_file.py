"""Atomic write of the progress file (HU-11-08.1): it is complete or it is the previous one."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from harness_agent.adapters.storage import ProgressFile, ProgressWriteError

SENTINEL = "VALOR-DE-PRUEBA-123"
NAME = "progreso-TAREA-14.md"


def read_when_unlocked(path: Path) -> str:
    """Read ``path``; on Windows the system may hold it for a moment after a process is killed."""
    deadline = time.monotonic() + 5.0
    while True:
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.02)


def names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


class TestWrite:
    def test_it_creates_the_file_when_it_does_not_exist(self, tmp_path: Path) -> None:
        ProgressFile(tmp_path).write(NAME, "uno\n")
        assert (tmp_path / NAME).read_text(encoding="utf-8") == "uno\n"
        assert names(tmp_path) == [NAME]

    def test_it_replaces_the_whole_content_and_leaves_no_temporary(self, tmp_path: Path) -> None:
        sink = ProgressFile(tmp_path)
        sink.write(NAME, "uno largo\n" * 50)
        sink.write(NAME, "dos\n")
        assert (tmp_path / NAME).read_text(encoding="utf-8") == "dos\n"
        assert names(tmp_path) == [NAME]

    def test_text_is_written_as_utf8_with_unix_newlines(self, tmp_path: Path) -> None:
        ProgressFile(tmp_path).write(NAME, "Sesión\nañ\n")
        assert (tmp_path / NAME).read_bytes() == "Sesión\nañ\n".encode()

    def test_a_failure_before_the_rename_keeps_the_previous_file_and_cleans_up(
        self, tmp_path: Path
    ) -> None:
        ProgressFile(tmp_path).write(NAME, "anterior\n")

        def broken(source: str | Path, destination: str | Path) -> None:
            raise OSError(f"disco lleno {SENTINEL}")

        with pytest.raises(ProgressWriteError) as caught:
            ProgressFile(tmp_path, replace=broken).write(NAME, "nuevo\n")

        assert (tmp_path / NAME).read_text(encoding="utf-8") == "anterior\n"
        assert names(tmp_path) == [NAME]
        assert SENTINEL not in str(caught.value) and str(tmp_path) not in str(caught.value)

    def test_a_failure_with_no_previous_file_leaves_nothing(self, tmp_path: Path) -> None:
        def broken(source: str | Path, destination: str | Path) -> None:
            raise OSError("x")

        with pytest.raises(ProgressWriteError):
            ProgressFile(tmp_path, replace=broken).write(NAME, "nuevo\n")
        assert names(tmp_path) == []

    def test_a_stale_temporary_from_a_killed_process_does_not_get_in_the_way(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / f".{NAME}.tmp").write_text("a medias", encoding="utf-8")
        ProgressFile(tmp_path).write(NAME, "bueno\n")
        assert (tmp_path / NAME).read_text(encoding="utf-8") == "bueno\n"
        assert names(tmp_path) == [NAME]

    def test_a_missing_folder_is_an_error_not_a_new_folder(self, tmp_path: Path) -> None:
        with pytest.raises(ProgressWriteError):
            ProgressFile(tmp_path / "no-existe").write(NAME, "x\n")
        assert names(tmp_path) == []

    def test_a_symbolic_link_is_replaced_not_written_through(self, tmp_path: Path) -> None:
        outside = tmp_path / "fuera.txt"
        outside.write_text("fuera", encoding="utf-8")
        folder = tmp_path / "area"
        folder.mkdir()
        try:
            (folder / NAME).symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip("symbolic links are not available")
        ProgressFile(folder).write(NAME, "dentro\n")
        assert outside.read_text(encoding="utf-8") == "fuera"
        assert not (folder / NAME).is_symlink()
        assert (folder / NAME).read_text(encoding="utf-8") == "dentro\n"

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "../fuera.md",
            "a/b.md",
            "a\\b.md",
            ".oculto.md",
            "sin-extension",
            "x.md\x00",
            "C:x.md",
        ],
    )
    def test_a_name_that_is_not_a_plain_markdown_file_name_is_refused(
        self, tmp_path: Path, name: str
    ) -> None:
        with pytest.raises(ProgressWriteError):
            ProgressFile(tmp_path).write(name, "x\n")
        assert names(tmp_path) == []


class TestRead:
    def test_it_returns_the_text_or_none(self, tmp_path: Path) -> None:
        sink = ProgressFile(tmp_path)
        assert sink.read(NAME) is None
        sink.write(NAME, "Sesión\n")
        assert sink.read(NAME) == "Sesión\n"

    def test_an_invalid_name_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ProgressWriteError):
            ProgressFile(tmp_path).read("../x.md")

    def test_a_directory_with_that_name_is_an_error(self, tmp_path: Path) -> None:
        (tmp_path / NAME).mkdir()
        with pytest.raises(ProgressWriteError):
            ProgressFile(tmp_path).read(NAME)


WRITER = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    from harness_agent.adapters.storage import ProgressFile

    sink = ProgressFile(Path(sys.argv[1]))
    count = 0
    while True:
        count += 1
        sink.write(sys.argv[2], f"{count}\\n" + "x" * 300_000 + f"\\n{count}\\n")
        if count == 3:
            print("ready", flush=True)
    """
)


class TestAProcessKilledMidWay:
    def test_the_file_is_always_a_complete_checkpoint(self, tmp_path: Path) -> None:
        process = subprocess.Popen(
            [sys.executable, "-c", WRITER, str(tmp_path), NAME],
            stdout=subprocess.PIPE,
            env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
            text=True,
        )
        try:
            assert process.stdout is not None
            assert process.stdout.readline().strip() == "ready"
        finally:
            process.kill()
            process.wait(timeout=10)

        text = read_when_unlocked(tmp_path / NAME)
        first, body, last = text.rstrip("\n").split("\n")
        assert first == last and int(first) >= 3
        assert body == "x" * 300_000


class TestCleanupPaths:
    def test_an_interrupt_during_the_rename_cleans_up_and_goes_through(
        self, tmp_path: Path
    ) -> None:
        def interrupted(source: str | Path, destination: str | Path) -> None:
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            ProgressFile(tmp_path, replace=interrupted).write(NAME, "x\n")
        assert names(tmp_path) == []

    def test_a_temporary_that_cannot_be_removed_does_not_hide_the_real_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def broken(source: str | Path, destination: str | Path) -> None:
            raise OSError("x")

        def locked(self: Path, missing_ok: bool = False) -> None:
            raise PermissionError("bloqueado")

        monkeypatch.setattr(Path, "unlink", locked)
        with pytest.raises(ProgressWriteError):
            ProgressFile(tmp_path, replace=broken).write(NAME, "x\n")
