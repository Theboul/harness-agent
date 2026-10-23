"""AuthorizedArea contract: the double and the real area agree on what both must honour.

``DummyAuthorizedArea`` is a lexical stand-in; ``WorkspaceArea`` is the real implementation
(HU-01-03). The same battery runs against both. Where the real area is stricter (symbolic links,
Windows rules, malformed input) the difference is documented in its own test.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from harness_agent.adapters.system import WorkspaceArea
from harness_agent.core import AuthorizedArea
from tests.doubles.dummy_authorized_area import DummyAuthorizedArea

Factory = Callable[[Path], AuthorizedArea]

FACTORIES: list[tuple[str, Factory]] = [
    ("DummyAuthorizedArea", DummyAuthorizedArea),
    ("WorkspaceArea", WorkspaceArea),
]


@pytest.fixture(params=FACTORIES, ids=[name for name, _ in FACTORIES])
def area(request: pytest.FixtureRequest, tmp_path: Path) -> AuthorizedArea:
    (tmp_path / "area" / "src").mkdir(parents=True)
    (tmp_path / "area-otra").mkdir()
    factory: Factory = request.param[1]
    return factory(tmp_path / "area")


def test_it_is_an_authorized_area(area: AuthorizedArea) -> None:
    assert isinstance(area, AuthorizedArea)


def test_root_is_an_absolute_path(area: AuthorizedArea) -> None:
    assert isinstance(area.root, Path)
    assert area.root.is_absolute()
    assert area.root.name == "area"


@pytest.mark.parametrize(
    "path", ["src", "src/main.py", "nuevo.txt", "src/../src/x.py", ".", "a/b/c/d.txt"]
)
def test_relative_paths_inside(area: AuthorizedArea, path: str) -> None:
    assert area.contains(path) is True


def test_absolute_paths_inside(area: AuthorizedArea) -> None:
    assert area.contains(str(area.root / "src" / "main.py")) is True
    assert area.contains(area.root / "src") is True


def test_the_root_itself_is_inside(area: AuthorizedArea) -> None:
    assert area.contains(area.root) is True


@pytest.mark.parametrize("path", ["..", "../x.txt", "src/../../x.txt", "../area-otra/x.txt"])
def test_relative_paths_that_leave_the_area(area: AuthorizedArea, path: str) -> None:
    assert area.contains(path) is False


def test_absolute_paths_outside(area: AuthorizedArea, tmp_path: Path) -> None:
    assert area.contains(str(tmp_path / "otro.txt")) is False
    assert area.contains(str(area.root.parent)) is False
    assert area.contains(os.path.abspath(os.sep)) is False


def test_a_sibling_with_the_same_prefix_is_outside(area: AuthorizedArea, tmp_path: Path) -> None:
    assert area.contains(str(tmp_path / "area-otra" / "x.txt")) is False


def test_the_answer_is_exactly_a_bool(area: AuthorizedArea) -> None:
    assert area.contains("src") is True
    assert area.contains("..") is False


class TestWhereTheRealAreaIsStricter:
    """The double is lexical (plus ``Path.resolve``); the real area also fails closed."""

    def test_a_link_leaving_the_area_is_outside_for_both(self, tmp_path: Path) -> None:
        area_dir = tmp_path / "area"
        outside = tmp_path / "outside"
        area_dir.mkdir()
        outside.mkdir()
        try:
            os.symlink(outside, area_dir / "enlace", target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("this system does not allow creating symbolic links")

        assert WorkspaceArea(area_dir).contains("enlace/x.txt") is False
        assert DummyAuthorizedArea(area_dir).contains("enlace/x.txt") is False

    def test_the_real_area_never_raises_on_malformed_input(self, tmp_path: Path) -> None:
        (tmp_path / "area").mkdir()
        real = WorkspaceArea(tmp_path / "area")

        assert real.contains("a\x00b") is False
        assert real.contains("") is False
        assert real.contains("   ") is False

    def test_the_real_area_rejects_a_root_that_is_not_a_folder(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            WorkspaceArea(tmp_path / "no-existe")
