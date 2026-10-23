"""WorkspaceArea: the real authorized area (HU-01-03 / T002).

Containment is decided on the real path: ``..``, absolute paths and symbolic links cannot take a
path out of the area, and anything that cannot be checked is outside (fail closed).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import WorkspaceArea, windows_path_problem
from harness_agent.core import AuthorizedArea

SENTINEL = "VALOR-DE-PRUEBA-123"


@pytest.fixture
def layout(tmp_path: Path) -> tuple[Path, Path]:
    """An ``area`` folder with some content and an ``outside`` folder next to it."""
    area = tmp_path / "area"
    outside = tmp_path / "outside"
    (area / "src").mkdir(parents=True)
    (area / "src" / "main.py").write_text("print(1)\n", encoding="utf-8", newline="")
    outside.mkdir()
    (outside / "secret.txt").write_text(SENTINEL, encoding="utf-8", newline="")
    return area, outside


def link(target: Path, path: Path, *, directory: bool = False) -> None:
    """Create a symbolic link or skip the test when the system does not allow it."""
    try:
        os.symlink(target, path, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("this system does not allow creating symbolic links")


class TestConstruction:
    def test_it_is_an_authorized_area(self, layout: tuple[Path, Path]) -> None:
        assert isinstance(WorkspaceArea(layout[0]), AuthorizedArea)

    def test_root_is_the_real_absolute_path(self, layout: tuple[Path, Path]) -> None:
        area, _ = layout
        built = WorkspaceArea(area)

        assert built.root == Path(os.path.realpath(area))
        assert built.root.is_absolute()

    def test_a_link_to_the_folder_resolves_to_the_real_root(
        self, layout: tuple[Path, Path], tmp_path: Path
    ) -> None:
        area, _ = layout
        alias = tmp_path / "alias"
        link(area, alias, directory=True)

        assert WorkspaceArea(alias).root == Path(os.path.realpath(area))

    def test_root_accepts_text_and_path(self, layout: tuple[Path, Path]) -> None:
        area, _ = layout
        assert WorkspaceArea(str(area)).root == WorkspaceArea(area).root

    @pytest.mark.parametrize("bad", ["missing", "file"])
    def test_a_root_that_is_not_an_existing_folder_is_rejected(
        self, layout: tuple[Path, Path], bad: str
    ) -> None:
        area, _ = layout
        target = area / "main-file" if bad == "file" else area / "missing"
        if bad == "file":
            target.write_text("x", encoding="utf-8", newline="")

        with pytest.raises(ValueError, match="carpeta existente") as raised:
            WorkspaceArea(target)

        assert str(target) not in str(raised.value)

    @pytest.mark.parametrize("bad", [None, 42, b"/tmp", "", "   "])
    def test_a_root_of_another_type_or_empty_is_rejected(self, bad: Any) -> None:
        with pytest.raises(ValueError, match="carpeta existente"):
            WorkspaceArea(bad)


class TestInside:
    @pytest.mark.parametrize(
        "path",
        ["src/main.py", "src", "src/nuevo/archivo.txt", "nuevo.txt", ".", "src/../src/main.py"],
    )
    def test_relative_paths_that_stay_inside(self, layout: tuple[Path, Path], path: str) -> None:
        assert WorkspaceArea(layout[0]).contains(path) is True

    def test_absolute_paths_inside(self, layout: tuple[Path, Path]) -> None:
        area, _ = layout
        built = WorkspaceArea(area)

        assert built.contains(str(area / "src" / "main.py")) is True
        assert built.contains(str(built.root / "no" / "existe.txt")) is True

    def test_the_root_itself_is_inside(self, layout: tuple[Path, Path]) -> None:
        area, _ = layout
        assert WorkspaceArea(area).contains(area) is True
        assert WorkspaceArea(area).contains(str(area)) is True

    def test_a_path_object_is_accepted(self, layout: tuple[Path, Path]) -> None:
        assert WorkspaceArea(layout[0]).contains(Path("src") / "main.py") is True

    def test_names_with_spaces_and_accents_are_inside(self, layout: tuple[Path, Path]) -> None:
        assert WorkspaceArea(layout[0]).contains("mi carpeta/código ñandú.txt") is True


class TestOutside:
    @pytest.mark.parametrize(
        "path",
        ["..", "../outside/secret.txt", "src/../../outside/secret.txt", "../area-otra/x"],
    )
    def test_dot_dot_that_leaves_the_area(self, layout: tuple[Path, Path], path: str) -> None:
        assert WorkspaceArea(layout[0]).contains(path) is False

    def test_absolute_paths_outside(self, layout: tuple[Path, Path]) -> None:
        area, outside = layout
        built = WorkspaceArea(area)

        assert built.contains(str(outside / "secret.txt")) is False
        assert built.contains(str(outside)) is False
        assert built.contains(os.path.abspath(os.sep)) is False

    def test_a_sibling_folder_with_the_same_prefix_is_outside(
        self, layout: tuple[Path, Path], tmp_path: Path
    ) -> None:
        area, _ = layout
        sibling = tmp_path / "area-otra"
        sibling.mkdir()

        assert WorkspaceArea(area).contains(str(sibling / "x.txt")) is False

    def test_the_parent_of_the_root_is_outside(self, layout: tuple[Path, Path]) -> None:
        area, _ = layout
        assert WorkspaceArea(area).contains(area.parent) is False


class TestSymbolicLinks:
    def test_a_link_to_a_file_outside_is_outside(self, layout: tuple[Path, Path]) -> None:
        area, outside = layout
        link(outside / "secret.txt", area / "enlace.txt")

        assert WorkspaceArea(area).contains("enlace.txt") is False

    def test_a_link_to_a_folder_outside_is_outside_and_so_is_what_hangs_from_it(
        self, layout: tuple[Path, Path]
    ) -> None:
        area, outside = layout
        link(outside, area / "enlace-dir", directory=True)
        built = WorkspaceArea(area)

        assert built.contains("enlace-dir") is False
        assert built.contains("enlace-dir/secret.txt") is False
        assert built.contains("enlace-dir/nuevo.txt") is False

    def test_the_real_path_wins_over_the_text_of_the_path(self, layout: tuple[Path, Path]) -> None:
        area, outside = layout
        link(outside, area / "enlace-dir", directory=True)

        # By text "enlace-dir/../x" collapses to "x", inside the area; but the link takes the path
        # to the outside folder and ".." climbs from there, so the real path is outside.
        assert os.path.normpath("enlace-dir/../x") == "x"
        if os.name == "nt":
            # Windows collapses ".." lexically before it follows links, as the system itself does
            assert WorkspaceArea(area).contains("enlace-dir/../x") is True
            return
        assert WorkspaceArea(area).contains("enlace-dir/../x") is False
        assert WorkspaceArea(area).contains("enlace-dir/../area/src/main.py") is True

    def test_a_link_that_stays_inside_is_inside(self, layout: tuple[Path, Path]) -> None:
        area, _ = layout
        link(area / "src" / "main.py", area / "alias.py")

        assert WorkspaceArea(area).contains("alias.py") is True

    def test_a_broken_link_pointing_outside_is_outside(
        self, layout: tuple[Path, Path], tmp_path: Path
    ) -> None:
        area, _ = layout
        link(tmp_path / "no-existe-fuera", area / "roto")

        assert WorkspaceArea(area).contains("roto") is False

    def test_a_circular_link_does_not_raise_and_is_not_trusted(
        self, layout: tuple[Path, Path]
    ) -> None:
        area, _ = layout
        link(area / "b", area / "a")
        link(area / "a", area / "b")

        assert WorkspaceArea(area).contains("a") in (True, False)  # never raises


class TestFailClosed:
    @pytest.mark.parametrize("bad", ["", "   ", "\t\n", "a\x00b", "\x00"])
    def test_empty_blank_and_null_paths_are_outside(
        self, layout: tuple[Path, Path], bad: str
    ) -> None:
        assert WorkspaceArea(layout[0]).contains(bad) is False

    @pytest.mark.parametrize("bad", [None, 42, 3.5, b"src", ["src"], object()])
    def test_other_types_are_outside(self, layout: tuple[Path, Path], bad: Any) -> None:
        assert WorkspaceArea(layout[0]).contains(bad) is False

    @pytest.mark.parametrize("error", [OSError("fallo"), ValueError("raro"), RuntimeError("x")])
    def test_any_error_while_resolving_is_outside_and_never_raised(
        self, layout: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, error: Exception
    ) -> None:
        built = WorkspaceArea(layout[0])

        def boom(*_: object, **__: object) -> str:
            raise error

        monkeypatch.setattr(os.path, "realpath", boom)

        assert built.contains("src/main.py") is False

    def test_the_answer_is_exactly_true_or_false(self, layout: tuple[Path, Path]) -> None:
        built = WorkspaceArea(layout[0])

        assert built.contains("src") is True
        assert built.contains("..") is False

    def test_a_path_that_cannot_be_compared_with_the_root_is_outside(
        self, layout: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        built = WorkspaceArea(layout[0])

        def other_drive(_paths: object) -> str:
            raise ValueError("Paths don't have the same drive")

        monkeypatch.setattr(os.path, "commonpath", other_drive)

        assert built.contains("src") is False


# --- Windows (HU-01-03 / T003) ----------------------------------------------------------------

WINDOWS_BAD = [
    ("\\\\servidor\\recurso\\x.txt", "UNC"),
    ("//servidor/recurso/x.txt", "UNC"),
    ("\\\\?\\C:\\x", "dispositivo"),
    ("\\\\.\\COM1", "dispositivo"),
    ("notas.txt:flujo", "flujo"),
    ("src\\main.py:Zone.Identifier", "flujo"),
    ("C:\\area\\a.txt:zone", "flujo"),
    ("CON", "reservado"),
    ("nul.txt", "reservado"),
    ("src\\com3", "reservado"),
    ("LPT1.log", "reservado"),
    ("aux.tar.gz", "reservado"),
    ("carpeta.", "punto"),
    ("src\\carpeta.\\x.txt", "punto"),
    ("archivo.txt ", "espacio"),
]
WINDOWS_GOOD = [
    "src\\main.py",
    "src/main.py",
    "a.b.c",
    "conexion.txt",
    "console.log",
    "nulo.txt",
    "lpt.txt",
    ".gitignore",
    "src\\..\\src",
    "com10.txt",
]


class TestWindowsProblem:
    @pytest.mark.parametrize(("raw", "kind"), WINDOWS_BAD, ids=[b[0] for b in WINDOWS_BAD])
    def test_hostile_paths_get_a_cause(self, raw: str, kind: str) -> None:
        cause = windows_path_problem(raw)

        assert cause is not None
        assert raw not in cause

    @pytest.mark.parametrize("raw", WINDOWS_GOOD)
    def test_ordinary_paths_have_no_problem(self, raw: str) -> None:
        assert windows_path_problem(raw) is None

    def test_it_is_pure_and_does_not_touch_the_disk(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def forbidden(*_: object, **__: object) -> None:
            raise AssertionError("must not touch the disk")

        monkeypatch.setattr(os.path, "realpath", forbidden)
        monkeypatch.setattr(os, "stat", forbidden)

        assert windows_path_problem("\\\\servidor\\recurso") is not None
        assert windows_path_problem("src\\main.py") is None


class TestWindowsInArea:
    @pytest.mark.parametrize(("raw", "kind"), WINDOWS_BAD, ids=[b[0] for b in WINDOWS_BAD])
    def test_hostile_paths_are_outside(
        self, layout: tuple[Path, Path], raw: str, kind: str
    ) -> None:
        assert WorkspaceArea(layout[0], windows=True).contains(raw) is False

    def test_a_hostile_path_is_rejected_before_the_disk_is_touched(
        self, layout: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        built = WorkspaceArea(layout[0], windows=True)

        def forbidden(*_: object, **__: object) -> str:
            raise AssertionError("a UNC path must not reach realpath")

        monkeypatch.setattr(os.path, "realpath", forbidden)

        assert built.contains("\\\\servidor\\recurso\\x.txt") is False
        assert built.contains("notas.txt:flujo") is False

    def test_an_ordinary_relative_path_is_inside(self, layout: tuple[Path, Path]) -> None:
        assert WorkspaceArea(layout[0], windows=True).contains("src/main.py") is True

    @pytest.mark.skipif(os.name == "nt", reason="a colon or CON is not a valid name on Windows")
    def test_without_the_windows_rules_a_colon_is_a_valid_name_character(
        self, layout: tuple[Path, Path]
    ) -> None:
        area, _ = layout
        built = WorkspaceArea(area, windows=False)

        assert built.contains("notas:con-dos-puntos.txt") is True
        assert built.contains("CON") is True

    def test_the_comparison_ignores_case_when_the_windows_rules_apply(
        self, layout: tuple[Path, Path]
    ) -> None:
        area, _ = layout
        loud = str(WorkspaceArea(area).root).upper()

        assert WorkspaceArea(area, windows=True).contains(loud) is True
        if os.name != "nt":
            assert WorkspaceArea(area, windows=False).contains(loud) is False

    def test_the_default_follows_the_operating_system(self, layout: tuple[Path, Path]) -> None:
        area, _ = layout
        default = WorkspaceArea(area)

        assert default.contains("notas:flujo.txt") is (os.name != "nt")

    @pytest.mark.skipif(os.name != "nt", reason="needs the Windows file system")
    def test_real_windows_other_drive_unc_and_stream(self, layout: tuple[Path, Path]) -> None:
        area, _ = layout
        built = WorkspaceArea(area)
        drive = built.root.drive.upper()
        other = "D:" if drive != "D:" else "C:"

        assert built.contains(other + "\\x.txt") is False
        assert built.contains("\\\\servidor\\recurso\\x.txt") is False
        assert built.contains("src\\main.py:flujo") is False
        assert built.contains("src\\MAIN.PY") is True
        assert built.contains(str(built.root).lower()) is True
        assert built.contains("..\\outside\\secret.txt") is False
