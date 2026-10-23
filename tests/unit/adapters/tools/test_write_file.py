"""WriteFileTool (``escribir_archivo``): creates or replaces files only inside the area (T009)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools import _limits
from harness_agent.adapters.tools.write_file import WriteFileTool
from harness_agent.core import AuthorizedArea, RiskLevel, Tool, ToolResult

SENTINEL = "VALOR-DE-PRUEBA-123"


@pytest.fixture
def area_dir(tmp_path: Path) -> Path:
    area = tmp_path / "area"
    (area / "src").mkdir(parents=True)
    (area / "src" / "existente.txt").write_text("contenido anterior", encoding="utf-8", newline="")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.txt").write_text(SENTINEL, encoding="utf-8", newline="")
    return area


@pytest.fixture
def tool(area_dir: Path) -> WriteFileTool:
    return WriteFileTool(WorkspaceArea(area_dir))


async def write(tool: Tool, path: Any, content: Any) -> ToolResult:
    return await tool.run({"path": path, "content": content})


def outside_untouched(area_dir: Path) -> bool:
    outside = area_dir.parent / "outside"
    return (
        sorted(p.name for p in outside.iterdir()) == ["secret.txt"]
        and (outside / "secret.txt").read_text(encoding="utf-8") == SENTINEL
    )


def link(target: Path, path: Path, *, directory: bool = False) -> None:
    try:
        os.symlink(target, path, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("this system does not allow creating symbolic links")


class TestDeclaration:
    def test_it_is_a_tool_named_in_spanish_with_medium_risk(self, tool: WriteFileTool) -> None:
        assert isinstance(tool, Tool)
        assert tool.name == "escribir_archivo"
        assert tool.risk is RiskLevel.MEDIUM
        assert tool.description.strip() != ""

    def test_the_schema_has_path_and_content_and_nothing_else(self, tool: WriteFileTool) -> None:
        schema = tool.schema

        assert schema["required"] == ["path", "content"]
        assert schema["additionalProperties"] is False
        assert list(schema["properties"]) == ["path", "content"]
        assert schema["properties"]["path"]["minLength"] == 1
        assert schema["properties"]["content"]["type"] == "string"


class TestWriting:
    async def test_it_creates_a_new_file(self, tool: WriteFileTool, area_dir: Path) -> None:
        result = await write(tool, "notas.txt", "hola ñandú\n")

        assert result.is_error is False
        assert "notas.txt" in result.content
        assert "creado" in result.content
        assert (area_dir / "notas.txt").read_text(encoding="utf-8") == "hola ñandú\n"

    async def test_it_replaces_an_existing_file_completely(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        result = await write(tool, "src/existente.txt", "nuevo")

        assert result.is_error is False
        assert "reemplazado" in result.content
        assert (area_dir / "src" / "existente.txt").read_text(encoding="utf-8") == "nuevo"

    async def test_it_reports_the_bytes_written(self, tool: WriteFileTool) -> None:
        result = await write(tool, "n.txt", "ñ")

        assert "2 bytes" in result.content

    async def test_it_writes_by_absolute_path_inside_the_area(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        result = await write(tool, str(area_dir / "abs.txt"), "x")

        assert result.is_error is False
        assert (area_dir / "abs.txt").read_text(encoding="utf-8") == "x"

    async def test_it_creates_the_missing_folders_inside_the_area(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        result = await write(tool, "a/b/c/archivo.txt", "profundo")

        assert result.is_error is False
        assert (area_dir / "a" / "b" / "c" / "archivo.txt").read_text(encoding="utf-8") == (
            "profundo"
        )

    async def test_line_endings_are_written_as_given(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        await write(tool, "crlf.txt", "uno\r\ndos\n")

        assert (area_dir / "crlf.txt").read_bytes() == b"uno\r\ndos\n"

    async def test_empty_content_creates_an_empty_file(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        result = await write(tool, "vacio.txt", "")

        assert result.is_error is False
        assert (area_dir / "vacio.txt").read_bytes() == b""

    async def test_a_file_exactly_at_the_limit_is_written(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        result = await write(tool, "justo.txt", "a" * _limits.MAX_WRITE_BYTES)

        assert result.is_error is False
        assert (area_dir / "justo.txt").stat().st_size == _limits.MAX_WRITE_BYTES


class TestRejectedBeforeTouchingTheDisk:
    @pytest.mark.parametrize(
        "path", ["../nuevo.txt", "../outside/nuevo.txt", "src/../../outside/nuevo.txt"]
    )
    async def test_dot_dot_that_leaves_the_area(
        self, tool: WriteFileTool, area_dir: Path, path: str
    ) -> None:
        result = await write(tool, path, "x")

        assert result.is_error is True
        assert result.content.startswith("[fuera_del_area] ")
        assert outside_untouched(area_dir)
        assert not (area_dir.parent / "nuevo.txt").exists()

    async def test_an_absolute_path_outside(self, tool: WriteFileTool, area_dir: Path) -> None:
        target = area_dir.parent / "outside" / "nuevo.txt"

        result = await write(tool, str(target), "x")

        assert result.content.startswith("[fuera_del_area] ")
        assert not target.exists()

    async def test_a_file_link_leaving_the_area_is_not_written_through(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        link(area_dir.parent / "outside" / "secret.txt", area_dir / "enlace.txt")

        result = await write(tool, "enlace.txt", "cambiado")

        assert result.content.startswith("[fuera_del_area] ")
        assert outside_untouched(area_dir)

    async def test_a_folder_link_leaving_the_area_creates_nothing_outside(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        link(area_dir.parent / "outside", area_dir / "salida", directory=True)

        result = await write(tool, "salida/nueva/carpeta/x.txt", "x")

        assert result.content.startswith("[fuera_del_area] ")
        assert outside_untouched(area_dir)

    async def test_without_an_area_nothing_is_written(self, area_dir: Path) -> None:
        result = await write(WriteFileTool(None), str(area_dir / "x.txt"), "x")

        assert result.content.startswith("[sin_area] ")
        assert not (area_dir / "x.txt").exists()

    async def test_too_much_content_is_rejected_before_the_disk(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        result = await write(tool, "enorme/x.txt", "a" * (_limits.MAX_WRITE_BYTES + 1))

        assert result.is_error is True
        assert result.content.startswith("[demasiado_grande] ")
        assert not (area_dir / "enorme").exists()

    async def test_the_limit_counts_bytes_not_characters(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        result = await write(tool, "bytes.txt", "ñ" * (_limits.MAX_WRITE_BYTES // 2 + 1))

        assert result.content.startswith("[demasiado_grande] ")
        assert not (area_dir / "bytes.txt").exists()

    @pytest.mark.parametrize("content", [None, 42, b"bytes", ["x"]])
    async def test_content_that_is_not_text_is_an_error(
        self, tool: WriteFileTool, area_dir: Path, content: Any
    ) -> None:
        result = await write(tool, "mal.txt", content)

        assert result.is_error is True
        assert result.content.startswith("[contenido_invalido] ")
        assert not (area_dir / "mal.txt").exists()

    async def test_text_that_cannot_be_encoded_as_utf8_is_an_error(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        result = await write(tool, "sustituto.txt", "a\ud800b")

        assert result.content.startswith("[contenido_invalido] ")
        assert not (area_dir / "sustituto.txt").exists()

    @pytest.mark.parametrize("raw", [None, 42, "", "a\x00b"])
    async def test_a_path_that_is_not_usable_never_raises(
        self, tool: WriteFileTool, raw: Any
    ) -> None:
        result = await write(tool, raw, "x")

        assert result.is_error is True
        assert result.content.startswith("[fuera_del_area] ")


class TestOtherErrors:
    async def test_a_folder_is_not_a_file_to_write(
        self, tool: WriteFileTool, area_dir: Path
    ) -> None:
        result = await write(tool, "src", "x")

        assert result.is_error is True
        assert result.content.startswith("[no_es_archivo] ")
        assert (area_dir / "src" / "existente.txt").exists()

    async def test_a_file_in_the_place_of_a_parent_folder_is_a_clear_error(
        self, tool: WriteFileTool
    ) -> None:
        result = await write(tool, "src/existente.txt/dentro.txt", "x")

        assert result.is_error is True
        assert result.content.startswith("[error_de_archivo] ")

    async def test_a_system_error_is_reported_without_a_trace(
        self, tool: WriteFileTool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def full(self: Path, data: bytes) -> int:
            raise OSError(28, "No space left on device", str(self))

        monkeypatch.setattr(Path, "write_bytes", full)

        result = await write(tool, "n.txt", "x")

        assert result.is_error is True
        assert result.content.startswith("[error_de_archivo] ")
        assert "No space left" not in result.content
        assert "Traceback" not in result.content

    async def test_the_path_is_checked_again_just_before_writing(self, area_dir: Path) -> None:
        class Flipping(AuthorizedArea):
            """Accepts the first checks, then says the path moved outside the area."""

            def __init__(self, root: Path) -> None:
                self._real = WorkspaceArea(root)
                self.calls = 0

            @property
            def root(self) -> Path:
                return self._real.root

            def contains(self, path: Path | str) -> bool:
                self.calls += 1
                return self.calls <= 2 and self._real.contains(path)

        result = await write(WriteFileTool(Flipping(area_dir)), "nuevo.txt", "x")

        assert result.is_error is True
        assert result.content.startswith("[fuera_del_area] ")
        assert not (area_dir / "nuevo.txt").exists()
