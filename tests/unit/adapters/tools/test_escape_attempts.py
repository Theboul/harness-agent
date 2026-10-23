"""Escape attempts against the four file tools (HU-01-03 / T011, AC-03 and SC-001).

Every hostile path must be rejected as outside the area, nothing outside may change or be
revealed, and the model gets the reason. The Windows cases run synthetically everywhere
(``windows=True``) and, for real, on ``windows-latest``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools.list_files import ListFilesTool
from harness_agent.adapters.tools.read_file import ReadFileTool
from harness_agent.adapters.tools.search_text import SearchTextTool
from harness_agent.adapters.tools.write_file import WriteFileTool
from harness_agent.core import AuthorizedArea, Tool, ToolResult

SENTINEL = "VALOR-DE-PRUEBA-123"

ToolFactory = Callable[[AuthorizedArea], Tool]
ArgsFor = Callable[[str], dict[str, Any]]

TOOLS: list[tuple[str, ToolFactory, ArgsFor]] = [
    ("escribir_archivo", WriteFileTool, lambda p: {"path": p, "content": "x"}),
    ("leer_archivo", ReadFileTool, lambda p: {"path": p}),
    ("listar_archivos", ListFilesTool, lambda p: {"path": p}),
    ("buscar_texto", SearchTextTool, lambda p: {"path": p, "query": "cobrar"}),
]
TOOL_IDS = [name for name, _, _ in TOOLS]


def link(target: Path, path: Path, *, directory: bool = False) -> None:
    try:
        os.symlink(target, path, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("this system does not allow creating symbolic links")


@pytest.fixture
def world(tmp_path: Path) -> Path:
    """``tmp_path`` with an ``area`` and an ``outside`` that holds a sentinel file."""
    (tmp_path / "area" / "src").mkdir(parents=True)
    (tmp_path / "area" / "src" / "pago.py").write_text("cobrar\n", encoding="utf-8", newline="")
    (tmp_path / "area-otra").mkdir()
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.txt").write_text(
        f"cobrar {SENTINEL}", encoding="utf-8", newline=""
    )
    return tmp_path


def snapshot(folder: Path) -> dict[str, tuple[bytes | None, int]]:
    """Every entry below ``folder`` with its content and modification time, to compare later."""
    state: dict[str, tuple[bytes | None, int]] = {}
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            state[str(path)] = (path.read_bytes(), path.stat().st_mtime_ns)
        else:
            state[str(path)] = (None, 0)
    return state


def hostile_paths(world: Path) -> list[str]:
    """The paths the battery tries; the links are created by the caller before using them."""
    outside = world / "outside"
    return [
        "..",
        "../outside/secret.txt",
        "../outside/nuevo.txt",
        "src/../../outside/secret.txt",
        "../area-otra/x.txt",
        str(outside / "secret.txt"),
        str(outside / "nuevo.txt"),
        str(outside),
        str(world),
        os.path.abspath(os.sep),
        "enlace-archivo",
        "enlace-carpeta/secret.txt",
        "enlace-carpeta/nuevo/x.txt",
        "enlace-roto",
        "a\x00b",
        "",
        "   ",
        # POSIX resolves the link before ".."; Windows collapses ".." first (see the area tests)
        *([] if os.name == "nt" else ["enlace-carpeta/../x.txt"]),
    ]


@pytest.fixture
def hostile(world: Path) -> list[str]:
    area, outside = world / "area", world / "outside"
    link(outside / "secret.txt", area / "enlace-archivo")
    link(outside, area / "enlace-carpeta", directory=True)
    link(world / "no-existe-fuera", area / "enlace-roto")
    return hostile_paths(world)


class TestEveryToolRejectsEveryHostilePath:
    @pytest.mark.parametrize(("name", "factory", "args_for"), TOOLS, ids=TOOL_IDS)
    async def test_nothing_outside_changes_or_is_revealed(
        self,
        world: Path,
        hostile: list[str],
        name: str,
        factory: ToolFactory,
        args_for: ArgsFor,
    ) -> None:
        assert len(hostile) >= 15
        tool = factory(WorkspaceArea(world / "area"))
        before_outside = snapshot(world / "outside")
        before_sibling = snapshot(world / "area-otra")

        for raw in hostile:
            result = await tool.run(args_for(raw))

            assert isinstance(result, ToolResult), raw
            assert result.is_error is True, raw
            assert result.content.startswith("[fuera_del_area] "), (name, raw, result.content)
            assert SENTINEL not in result.content, raw
            # the message may repeat what the model sent, but never the real path it resolved to
            assert str(world / "outside") not in result.content.replace(raw, "[ruta recibida]"), raw
            assert "Traceback" not in result.content, raw

        assert snapshot(world / "outside") == before_outside
        assert snapshot(world / "area-otra") == before_sibling
        assert not (world / "nuevo.txt").exists()
        assert not (world / "x.txt").exists()

    async def test_the_model_gets_the_reason_in_spanish_with_a_suggestion(
        self, world: Path
    ) -> None:
        tool = WriteFileTool(WorkspaceArea(world / "area"))

        result = await tool.run({"path": "../outside/nuevo.txt", "content": "x"})

        assert "queda fuera del área de trabajo" in result.content
        assert "Usa una ruta dentro del área" in result.content


class TestWritesThroughLinks:
    async def test_a_file_link_leaving_the_area_keeps_the_target_identical(
        self, world: Path
    ) -> None:
        link(world / "outside" / "secret.txt", world / "area" / "enlace.txt")
        tool = WriteFileTool(WorkspaceArea(world / "area"))

        result = await tool.run({"path": "enlace.txt", "content": "cambiado"})

        assert result.is_error is True
        assert (world / "outside" / "secret.txt").read_text("utf-8") == f"cobrar {SENTINEL}"

    async def test_a_folder_link_leaving_the_area_creates_nothing_outside(
        self, world: Path
    ) -> None:
        link(world / "outside", world / "area" / "salida", directory=True)
        tool = WriteFileTool(WorkspaceArea(world / "area"))

        result = await tool.run({"path": "salida/a/b/c.txt", "content": "x"})

        assert result.is_error is True
        assert sorted(p.name for p in (world / "outside").iterdir()) == ["secret.txt"]

    async def test_a_link_that_stays_inside_still_works(self, world: Path) -> None:
        link(world / "area" / "src", world / "area" / "alias-src", directory=True)
        tool = WriteFileTool(WorkspaceArea(world / "area"))

        result = await tool.run({"path": "alias-src/nuevo.txt", "content": "ok"})

        assert result.is_error is False
        assert (world / "area" / "src" / "nuevo.txt").read_text("utf-8") == "ok"

    async def test_a_circular_link_never_escapes_and_never_raises(self, world: Path) -> None:
        link(world / "area" / "b", world / "area" / "a")
        link(world / "area" / "a", world / "area" / "b")
        area = WorkspaceArea(world / "area")
        before = snapshot(world / "outside")

        for name, factory, args_for in TOOLS:
            result = await factory(area).run(args_for("a"))

            assert result.is_error is True, name
            assert "Traceback" not in result.content

        assert snapshot(world / "outside") == before


WINDOWS_PATHS = [
    "\\\\servidor\\recurso\\x.txt",
    "//servidor/recurso/x.txt",
    "\\\\?\\C:\\x",
    "\\\\.\\COM1",
    "secret.txt:flujo",
    "src\\pago.py:Zone.Identifier",
    "CON",
    "nul.txt",
    "src\\com3",
    "carpeta.",
    "archivo.txt ",
]


class TestWindowsRulesOnAnySystem:
    @pytest.mark.parametrize(("name", "factory", "args_for"), TOOLS, ids=TOOL_IDS)
    @pytest.mark.parametrize("raw", WINDOWS_PATHS)
    async def test_hostile_windows_paths_are_rejected_before_the_disk(
        self,
        world: Path,
        monkeypatch: pytest.MonkeyPatch,
        name: str,
        factory: ToolFactory,
        args_for: ArgsFor,
        raw: str,
    ) -> None:
        tool = factory(WorkspaceArea(world / "area", windows=True))

        def forbidden(*_: object, **__: object) -> str:
            raise AssertionError("the disk must not be consulted for a hostile Windows path")

        monkeypatch.setattr(os.path, "realpath", forbidden)

        result = await tool.run(args_for(raw))

        assert result.is_error is True
        assert result.content.startswith("[fuera_del_area] ")


@pytest.mark.skipif(os.name != "nt", reason="needs the Windows file system")
class TestRealWindows:
    @pytest.mark.parametrize(("name", "factory", "args_for"), TOOLS, ids=TOOL_IDS)
    async def test_other_drive_unc_stream_and_case(
        self, world: Path, name: str, factory: ToolFactory, args_for: ArgsFor
    ) -> None:
        area = WorkspaceArea(world / "area")
        drive = area.root.drive.upper()
        other = "D:" if drive != "D:" else "C:"
        tool = factory(area)

        for raw in (
            other + "\\x.txt",
            "\\\\servidor\\recurso\\x.txt",
            "src\\pago.py:flujo",
            "..\\outside\\secret.txt",
        ):
            result = await tool.run(args_for(raw))

            assert result.is_error is True, raw
            assert result.content.startswith("[fuera_del_area] "), raw
