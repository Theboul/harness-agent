"""ReadFileTool (``leer_archivo``): reads text inside the area, with clear errors (T006)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools import _limits
from harness_agent.adapters.tools.read_file import ReadFileTool
from harness_agent.core import RiskLevel, Tool, ToolResult

SENTINEL = "VALOR-DE-PRUEBA-123"


@pytest.fixture
def area_dir(tmp_path: Path) -> Path:
    area = tmp_path / "area"
    (area / "src").mkdir(parents=True)
    (area / "src" / "main.py").write_text("print('hola')\nsegunda línea ñandú\n", encoding="utf-8")
    (area / "vacio.txt").write_text("", encoding="utf-8")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.txt").write_text(SENTINEL, encoding="utf-8")
    return area


@pytest.fixture
def tool(area_dir: Path) -> ReadFileTool:
    return ReadFileTool(WorkspaceArea(area_dir))


async def read(tool: Tool, path: Any) -> ToolResult:
    return await tool.run({"path": path})


class TestDeclaration:
    def test_it_is_a_tool_named_in_spanish_with_low_risk(self, tool: ReadFileTool) -> None:
        assert isinstance(tool, Tool)
        assert tool.name == "leer_archivo"
        assert tool.risk is RiskLevel.LOW
        assert tool.description.strip() != ""

    def test_the_schema_has_one_path_argument_and_nothing_else(self, tool: ReadFileTool) -> None:
        schema = tool.schema

        assert schema["type"] == "object"
        assert schema["required"] == ["path"]
        assert schema["additionalProperties"] is False
        assert list(schema["properties"]) == ["path"]
        assert schema["properties"]["path"]["type"] == "string"
        assert schema["properties"]["path"]["minLength"] == 1


class TestReading:
    async def test_it_reads_a_file_by_relative_path(self, tool: ReadFileTool) -> None:
        result = await read(tool, "src/main.py")

        assert result.is_error is False
        assert result.content == "print('hola')\nsegunda línea ñandú\n"

    async def test_it_reads_a_file_by_absolute_path(
        self, tool: ReadFileTool, area_dir: Path
    ) -> None:
        result = await read(tool, str(area_dir / "src" / "main.py"))

        assert result.is_error is False
        assert "ñandú" in result.content

    async def test_an_empty_file_is_empty_text_not_an_error(self, tool: ReadFileTool) -> None:
        result = await read(tool, "vacio.txt")

        assert result.is_error is False
        assert result.content == ""

    async def test_line_endings_are_kept_as_written(
        self, tool: ReadFileTool, area_dir: Path
    ) -> None:
        (area_dir / "crlf.txt").write_bytes(b"uno\r\ndos\r\n")

        assert (await read(tool, "crlf.txt")).content == "uno\r\ndos\r\n"

    async def test_a_file_exactly_at_the_limit_is_read(
        self, tool: ReadFileTool, area_dir: Path
    ) -> None:
        (area_dir / "justo.txt").write_bytes(b"a" * _limits.MAX_READ_BYTES)

        result = await read(tool, "justo.txt")

        assert result.is_error is False
        assert len(result.content) == _limits.MAX_READ_BYTES


class TestErrors:
    async def test_a_missing_path_is_a_clear_error_with_a_suggestion(
        self, tool: ReadFileTool
    ) -> None:
        result = await read(tool, "src/pago.py")

        assert result.is_error is True
        assert result.content.startswith("[no_existe] ")
        assert "src/pago.py" in result.content
        assert "listar_archivos" in result.content

    async def test_a_folder_is_not_a_file(self, tool: ReadFileTool) -> None:
        result = await read(tool, "src")

        assert result.is_error is True
        assert result.content.startswith("[no_es_archivo] ")
        assert "listar_archivos" in result.content

    async def test_a_file_over_the_limit_is_too_big(
        self, tool: ReadFileTool, area_dir: Path
    ) -> None:
        (area_dir / "grande.txt").write_bytes(b"a" * (_limits.MAX_READ_BYTES + 1))

        result = await read(tool, "grande.txt")

        assert result.is_error is True
        assert result.content.startswith("[demasiado_grande] ")
        assert str(_limits.MAX_READ_BYTES) in result.content

    async def test_a_binary_file_is_not_text(self, tool: ReadFileTool, area_dir: Path) -> None:
        (area_dir / "datos.bin").write_bytes(b"abc\x00def")

        result = await read(tool, "datos.bin")

        assert result.is_error is True
        assert result.content.startswith("[no_es_texto] ")

    async def test_bytes_that_are_not_utf8_are_not_text(
        self, tool: ReadFileTool, area_dir: Path
    ) -> None:
        (area_dir / "latin.txt").write_bytes("canción".encode("latin-1"))

        result = await read(tool, "latin.txt")

        assert result.is_error is True
        assert result.content.startswith("[no_es_texto] ")
        assert "UTF-8" in result.content

    async def test_a_path_outside_is_rejected_without_reading(
        self, tool: ReadFileTool, area_dir: Path
    ) -> None:
        result = await read(tool, "../outside/secret.txt")

        assert result.is_error is True
        assert result.content.startswith("[fuera_del_area] ")
        assert SENTINEL not in result.content

    async def test_without_an_area_nothing_is_read(self, area_dir: Path) -> None:
        result = await read(ReadFileTool(None), str(area_dir / "src" / "main.py"))

        assert result.is_error is True
        assert result.content.startswith("[sin_area] ")

    async def test_a_system_error_is_reported_without_a_trace_or_the_real_path(
        self, tool: ReadFileTool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def denied(self: Path, *args: Any, **kwargs: Any) -> Any:
            raise PermissionError(13, "Permission denied", str(self))

        monkeypatch.setattr(Path, "open", denied)

        result = await read(tool, "src/main.py")

        assert result.is_error is True
        assert result.content.startswith("[error_de_archivo] ")
        assert "Traceback" not in result.content
        assert "Permission denied" not in result.content

    @pytest.mark.parametrize("raw", [None, 42, "", "a\x00b"])
    async def test_a_path_that_is_not_usable_is_outside_and_never_raises(
        self, tool: ReadFileTool, raw: Any
    ) -> None:
        result = await read(tool, raw)

        assert result.is_error is True
        assert result.content.startswith("[fuera_del_area] ")

    async def test_a_call_without_path_is_an_error_not_an_exception(
        self, tool: ReadFileTool
    ) -> None:
        result = await tool.run({})

        assert result.is_error is True

    async def test_it_reads_at_most_the_limit_plus_one_byte(
        self, tool: ReadFileTool, area_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (area_dir / "grande.txt").write_bytes(b"a" * (_limits.MAX_READ_BYTES * 3))
        requested: list[int] = []
        real_open = Path.open

        class Spy:
            def __init__(self, handle: Any) -> None:
                self._handle = handle

            def __enter__(self) -> Spy:
                return self

            def __exit__(self, *exc: object) -> None:
                self._handle.close()

            def read(self, size: int = -1) -> bytes:
                requested.append(size)
                data: bytes = self._handle.read(size)
                return data

        def spy_open(self: Path, *args: Any, **kwargs: Any) -> Spy:
            return Spy(real_open(self, *args, **kwargs))

        monkeypatch.setattr(Path, "open", spy_open)

        result = await read(tool, "grande.txt")

        assert result.content.startswith("[demasiado_grande] ")
        assert requested == [_limits.MAX_READ_BYTES + 1]

    @pytest.mark.skipif(os.name == "nt", reason="needs POSIX named pipes")
    async def test_a_special_file_is_not_opened(self, tool: ReadFileTool, area_dir: Path) -> None:
        fifo = area_dir / "tuberia"
        os.mkfifo(fifo)

        result = await read(tool, "tuberia")

        assert result.is_error is True
        assert result.content.startswith("[no_es_archivo] ")
