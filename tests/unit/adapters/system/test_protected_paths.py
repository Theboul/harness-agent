"""ProtectedPaths: the files and folders of the harness that tools must not touch (HU-11-01 / T008).

``contains`` answers *True when the path is protected*; anything that cannot be judged is
protected (fail closed).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import ProtectedPaths
from harness_agent.core import AuthorizedArea


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / ".harness" / "tareas" / "s1").mkdir(parents=True)
    (tmp_path / ".harness" / "sessions.db").write_text("db")
    (tmp_path / "src").mkdir()
    return tmp_path


@pytest.fixture
def area(workspace: Path) -> ProtectedPaths:
    return ProtectedPaths(workspace, directories=[workspace / ".harness"])


def test_it_is_an_authorized_area_rooted_at_the_workspace(
    area: ProtectedPaths, workspace: Path
) -> None:
    assert isinstance(area, AuthorizedArea)
    assert area.root == Path(os.path.realpath(workspace))


@pytest.mark.parametrize(
    "path",
    [
        ".harness",
        ".harness/",
        ".harness/sessions.db",
        ".harness/tareas/s1/criterios.json",
        "./.harness/tareas",
        "src/../.harness/sessions.db",
        ".harness/tareas/../../.harness",
        ".harness/does/not/exist/yet",
    ],
)
def test_paths_inside_a_protected_folder_are_protected(area: ProtectedPaths, path: str) -> None:
    assert area.contains(path) is True


def test_absolute_and_path_objects_are_judged_too(area: ProtectedPaths, workspace: Path) -> None:
    assert area.contains(str(workspace / ".harness" / "sessions.db")) is True
    assert area.contains(workspace / ".harness" / "tareas") is True


@pytest.mark.parametrize(
    "path", ["src", "src/main.py", "README.md", ".harness2/x", ".harnessx", "a/.harness-b"]
)
def test_other_paths_are_not_protected(area: ProtectedPaths, path: str) -> None:
    assert area.contains(path) is False


def test_an_absolute_path_outside_the_workspace_is_not_protected(
    area: ProtectedPaths, tmp_path_factory: pytest.TempPathFactory
) -> None:
    assert area.contains(str(tmp_path_factory.mktemp("elsewhere") / "x")) is False


def test_single_files_are_protected_exactly_and_their_neighbours_are_not(workspace: Path) -> None:
    db = workspace / "data" / "s.db"
    area = ProtectedPaths(workspace, files=[db, Path(str(db) + "-wal")])

    assert area.contains("data/s.db") is True
    assert area.contains("data/s.db-wal") is True
    assert area.contains("data/s.db-shm") is False
    assert area.contains("data") is False
    assert area.contains("data/s.dbx") is False
    assert area.contains("data/other.db") is False


def test_a_folder_that_does_not_exist_yet_is_protected_when_created(workspace: Path) -> None:
    area = ProtectedPaths(workspace, directories=[workspace / "later"])
    assert area.contains("later/x") is True
    (workspace / "later").mkdir()
    assert area.contains("later/x") is True


def test_windows_comparison_ignores_case(workspace: Path) -> None:
    area = ProtectedPaths(workspace, directories=[workspace / ".harness"], windows=True)

    assert area.contains(".HARNESS/Sessions.DB") is True
    assert area.contains("SRC") is False


@pytest.mark.parametrize(
    "path",
    [
        ".harness.",
        ".harness ",
        ".harness::$DATA",
        ".harness/sessions.db:stream",
        "\\\\server\\share\\x",
        "//server/share/x",
        "CON",
    ],
)
def test_windows_only_tricks_are_protected_when_windows_rules_apply(
    workspace: Path, path: str
) -> None:
    area = ProtectedPaths(workspace, directories=[workspace / ".harness"], windows=True)

    assert area.contains(path) is True


@pytest.mark.parametrize("path", ["", "   ", "a\x00b", 42, None])
def test_what_cannot_be_judged_is_protected(area: ProtectedPaths, path: Any) -> None:
    assert area.contains(path) is True


def test_an_unexpected_failure_is_protected(
    area: ProtectedPaths, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_path: str) -> str:
        raise OSError

    monkeypatch.setattr(os.path, "realpath", broken)

    assert area.contains("src/main.py") is True


def test_a_link_from_the_workspace_to_a_protected_folder_is_protected(
    area: ProtectedPaths, workspace: Path
) -> None:
    link = workspace / "atajo"
    try:
        link.symlink_to(workspace / ".harness", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available")

    assert area.contains("atajo/sessions.db") is True
    assert area.contains("atajo") is True


def test_constructor_rejects_a_workspace_that_is_not_a_folder(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ProtectedPaths(tmp_path / "missing")
    with pytest.raises(ValueError):
        ProtectedPaths("")
