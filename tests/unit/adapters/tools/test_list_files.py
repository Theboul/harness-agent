"""ListFilesTool (``listar_archivos``): lists a folder of the area, bounded and ordered (T007)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools import _limits
from harness_agent.adapters.tools.list_files import ListFilesTool
from harness_agent.core import RiskLevel, Tool, ToolResult

SENTINEL = "VALOR-DE-PRUEBA-123"


@pytest.fixture
def area_dir(tmp_path: Path) -> Path:
    area = tmp_path / "area"
    (area / "src" / "paquete").mkdir(parents=True)
    (area / "src" / "main.py").write_text("x", encoding="utf-8", newline="")
    (area / "README.md").write_text("x", encoding="utf-8", newline="")
    (area / "carpeta vacía").mkdir()
    (area / "ñandú.txt").write_text("x", encoding="utf-8", newline="")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.txt").write_text(SENTINEL, encoding="utf-8", newline="")
    return area


@pytest.fixture
def tool(area_dir: Path) -> ListFilesTool:
    return ListFilesTool(WorkspaceArea(area_dir))


async def ls(tool: Tool, path: Any) -> ToolResult:
    return await tool.run({"path": path})


class TestDeclaration:
    def test_it_is_a_tool_named_in_spanish_with_low_risk(self, tool: ListFilesTool) -> None:
        assert isinstance(tool, Tool)
        assert tool.name == "listar_archivos"
        assert tool.risk is RiskLevel.LOW
        assert tool.description.strip() != ""

    def test_the_schema_has_one_path_argument_and_nothing_else(self, tool: ListFilesTool) -> None:
        schema = tool.schema

        assert schema["required"] == ["path"]
        assert schema["additionalProperties"] is False
        assert list(schema["properties"]) == ["path"]
        assert schema["properties"]["path"]["minLength"] == 1


class TestListing:
    async def test_it_lists_files_and_folders_in_order(self, tool: ListFilesTool) -> None:
        result = await ls(tool, ".")

        assert result.is_error is False
        assert result.content.splitlines() == [
            "[carpeta] carpeta vacía",
            "[archivo] README.md",
            "[carpeta] src",
            "[archivo] ñandú.txt",
        ]

    async def test_a_subfolder_is_listed_without_recursion(self, tool: ListFilesTool) -> None:
        result = await ls(tool, "src")

        assert result.content.splitlines() == ["[archivo] main.py", "[carpeta] paquete"]

    async def test_the_root_can_be_named_by_its_absolute_path(
        self, tool: ListFilesTool, area_dir: Path
    ) -> None:
        result = await ls(tool, str(area_dir / "src"))

        assert result.is_error is False
        assert "[archivo] main.py" in result.content

    async def test_an_empty_folder_is_a_notice_not_an_error(self, tool: ListFilesTool) -> None:
        result = await ls(tool, "carpeta vacía")

        assert result.is_error is False
        assert result.content == "La carpeta está vacía."

    async def test_the_order_is_stable_across_calls(self, tool: ListFilesTool) -> None:
        first = (await ls(tool, ".")).content

        for _ in range(5):
            assert (await ls(tool, ".")).content == first

    async def test_a_link_is_listed_as_a_link_without_following_it(
        self, tool: ListFilesTool, area_dir: Path
    ) -> None:
        try:
            os.symlink(area_dir.parent / "outside", area_dir / "salida", target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("this system does not allow creating symbolic links")

        result = await ls(tool, ".")

        assert "[enlace] salida" in result.content
        assert "secret.txt" not in result.content

    async def test_control_characters_in_a_name_cannot_forge_lines(
        self, tool: ListFilesTool, area_dir: Path
    ) -> None:
        try:
            (area_dir / "a\n[archivo] falso").write_text("x", encoding="utf-8", newline="")
        except (OSError, ValueError):
            pytest.skip("this system does not allow control characters in names")

        result = await ls(tool, ".")

        assert "\n[archivo] falso" not in result.content
        assert len(result.content.splitlines()) == 5

    async def test_more_than_the_limit_is_cut_and_says_so(
        self, tool: ListFilesTool, area_dir: Path
    ) -> None:
        many = area_dir / "muchos"
        many.mkdir()
        for number in range(_limits.MAX_LIST_ENTRIES + 25):
            (many / f"f{number:04d}.txt").write_text("", encoding="utf-8", newline="")

        result = await ls(tool, "muchos")

        lines = result.content.splitlines()
        assert result.is_error is False
        assert len(lines) == _limits.MAX_LIST_ENTRIES + 1
        assert lines[0] == "[archivo] f0000.txt"
        assert "25 entradas más" in lines[-1]

    async def test_the_answer_never_exceeds_the_result_limit(
        self, tool: ListFilesTool, area_dir: Path
    ) -> None:
        wide = area_dir / "anchos"
        wide.mkdir()
        for number in range(_limits.MAX_LIST_ENTRIES):
            (wide / (f"{number:03d}-" + "n" * 200)).write_text("", encoding="utf-8", newline="")

        result = await ls(tool, "anchos")

        assert len(result.content) <= _limits.MAX_RESULT_CHARS


class TestErrors:
    async def test_a_missing_path_is_a_clear_error(self, tool: ListFilesTool) -> None:
        result = await ls(tool, "no/existe")

        assert result.is_error is True
        assert result.content.startswith("[no_existe] ")
        assert "no/existe" in result.content

    async def test_a_file_is_not_a_folder(self, tool: ListFilesTool) -> None:
        result = await ls(tool, "README.md")

        assert result.is_error is True
        assert result.content.startswith("[no_es_carpeta] ")
        assert "leer_archivo" in result.content

    async def test_a_path_outside_is_rejected(self, tool: ListFilesTool) -> None:
        result = await ls(tool, "../outside")

        assert result.is_error is True
        assert result.content.startswith("[fuera_del_area] ")
        assert "secret.txt" not in result.content

    async def test_without_an_area_nothing_is_listed(self, area_dir: Path) -> None:
        result = await ls(ListFilesTool(None), str(area_dir))

        assert result.is_error is True
        assert result.content.startswith("[sin_area] ")

    async def test_a_system_error_is_reported_without_a_trace(
        self, tool: ListFilesTool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def denied(self: Path) -> Any:
            raise PermissionError(13, "Permission denied", str(self))

        monkeypatch.setattr(Path, "iterdir", denied)

        result = await ls(tool, ".")

        assert result.is_error is True
        assert result.content.startswith("[error_de_archivo] ")
        assert "Permission denied" not in result.content

    @pytest.mark.parametrize("raw", [None, 42, "", "a\x00b"])
    async def test_a_path_that_is_not_usable_never_raises(
        self, tool: ListFilesTool, raw: Any
    ) -> None:
        result = await ls(tool, raw)

        assert result.is_error is True
        assert result.content.startswith("[fuera_del_area] ")
