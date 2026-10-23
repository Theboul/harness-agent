"""SearchTextTool (``buscar_texto``): literal search inside the area, bounded and ordered (T008)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools import _limits
from harness_agent.adapters.tools.search_text import SearchTextTool
from harness_agent.core import RiskLevel, Tool, ToolResult

SENTINEL = "VALOR-DE-PRUEBA-123"


@pytest.fixture
def area_dir(tmp_path: Path) -> Path:
    area = tmp_path / "area"
    (area / "src" / "paquete").mkdir(parents=True)
    (area / "src" / "pago.py").write_text(
        "import os\n\ndef cobrar(monto):\n    return monto\n", encoding="utf-8"
    )
    (area / "src" / "paquete" / "util.py").write_text(
        "# cobrar aquí también\nx = 1\n", encoding="utf-8"
    )
    (area / "README.md").write_text("Se puede COBRAR y cobrar.\n", encoding="utf-8")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.txt").write_text(f"cobrar {SENTINEL}\n", encoding="utf-8")
    return area


@pytest.fixture
def tool(area_dir: Path) -> SearchTextTool:
    return SearchTextTool(WorkspaceArea(area_dir))


async def grep(tool: Tool, path: Any, query: Any) -> ToolResult:
    return await tool.run({"path": path, "query": query})


def link(target: Path, path: Path, *, directory: bool = False) -> None:
    try:
        os.symlink(target, path, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("this system does not allow creating symbolic links")


class TestDeclaration:
    def test_it_is_a_tool_named_in_spanish_with_low_risk(self, tool: SearchTextTool) -> None:
        assert isinstance(tool, Tool)
        assert tool.name == "buscar_texto"
        assert tool.risk is RiskLevel.LOW
        assert tool.description.strip() != ""

    def test_the_schema_has_path_and_a_bounded_query_and_nothing_else(
        self, tool: SearchTextTool
    ) -> None:
        schema = tool.schema

        assert schema["required"] == ["path", "query"]
        assert schema["additionalProperties"] is False
        assert list(schema["properties"]) == ["path", "query"]
        assert schema["properties"]["path"]["minLength"] == 1
        assert schema["properties"]["query"]["minLength"] == 1
        assert schema["properties"]["query"]["maxLength"] == _limits.MAX_QUERY_CHARS


class TestSearching:
    async def test_it_finds_text_in_a_file_with_file_line_and_text(
        self, tool: SearchTextTool
    ) -> None:
        result = await grep(tool, "src/pago.py", "cobrar")

        assert result.is_error is False
        assert result.content == "src/pago.py:3: def cobrar(monto):"

    async def test_it_searches_a_folder_recursively_in_a_stable_order(
        self, tool: SearchTextTool
    ) -> None:
        result = await grep(tool, ".", "cobrar")

        assert result.is_error is False
        assert result.content.splitlines() == [
            "README.md:1: Se puede COBRAR y cobrar.",
            "src/pago.py:3: def cobrar(monto):",
            "src/paquete/util.py:1: # cobrar aquí también",
        ]
        assert (await grep(tool, ".", "cobrar")).content == result.content

    async def test_the_search_is_case_sensitive(self, tool: SearchTextTool) -> None:
        result = await grep(tool, "README.md", "COBRAR")

        assert result.content == "README.md:1: Se puede COBRAR y cobrar."
        assert "no hay coincidencias" in (await grep(tool, "src/pago.py", "COBRAR")).content.lower()

    async def test_a_regex_looking_query_is_literal_text(
        self, tool: SearchTextTool, area_dir: Path
    ) -> None:
        (area_dir / "re.txt").write_text("a.*b\nxyz\n(grupo\n", encoding="utf-8")

        assert (await grep(tool, "re.txt", ".*")).content == "re.txt:1: a.*b"
        assert (await grep(tool, "re.txt", "(grupo")).content == "re.txt:3: (grupo"

    async def test_no_matches_is_a_notice_not_an_error(self, tool: SearchTextTool) -> None:
        result = await grep(tool, ".", "texto-que-no-esta")

        assert result.is_error is False
        assert result.content.lower().startswith("no hay coincidencias")

    async def test_an_absolute_folder_inside_the_area_works(
        self, tool: SearchTextTool, area_dir: Path
    ) -> None:
        result = await grep(tool, str(area_dir / "src"), "x = 1")

        assert result.content == "src/paquete/util.py:2: x = 1"

    async def test_more_than_the_limit_is_cut_and_says_so(
        self, tool: SearchTextTool, area_dir: Path
    ) -> None:
        (area_dir / "mucho.txt").write_text("hallazgo\n" * (_limits.MAX_MATCHES + 10), "utf-8")

        result = await grep(tool, "mucho.txt", "hallazgo")

        lines = result.content.splitlines()
        assert len(lines) == _limits.MAX_MATCHES + 1
        assert str(_limits.MAX_MATCHES) in lines[-1]

    async def test_a_long_line_is_cut(self, tool: SearchTextTool, area_dir: Path) -> None:
        (area_dir / "larga.txt").write_text("ancla " + "z" * 1000 + "\n", encoding="utf-8")

        result = await grep(tool, "larga.txt", "ancla")

        assert len(result.content) < _limits.MAX_LINE_CHARS + 40
        assert result.content.endswith("...")

    async def test_the_answer_never_exceeds_the_result_limit(
        self, tool: SearchTextTool, area_dir: Path
    ) -> None:
        (area_dir / "tantos").mkdir()
        for number in range(30):
            (area_dir / "tantos" / f"a{number:02d}.txt").write_text(
                ("hallazgo " + "w" * 190 + "\n") * 40, encoding="utf-8"
            )

        result = await grep(tool, "tantos", "hallazgo")

        assert len(result.content) <= _limits.MAX_RESULT_CHARS

    async def test_control_characters_in_a_line_are_neutralised(
        self, tool: SearchTextTool, area_dir: Path
    ) -> None:
        (area_dir / "ctl.txt").write_bytes(b"dato \x1b[31m rojo \rfalso\n")

        result = await grep(tool, "ctl.txt", "dato")

        assert "\x1b" not in result.content
        assert "\r" not in result.content


class TestSkippedFiles:
    async def test_binary_non_utf8_and_big_files_are_skipped_in_a_folder(
        self, tool: SearchTextTool, area_dir: Path
    ) -> None:
        (area_dir / "bin.dat").write_bytes(b"cobrar\x00\x01")
        (area_dir / "latin.txt").write_bytes("cobrar canción".encode("latin-1"))
        (area_dir / "grande.txt").write_bytes(b"cobrar " + b"a" * _limits.MAX_READ_BYTES)

        result = await grep(tool, ".", "cobrar")

        assert "bin.dat" not in result.content
        assert "latin.txt" not in result.content
        assert "grande.txt" not in result.content
        assert "src/pago.py:3" in result.content

    @pytest.mark.parametrize(
        ("name", "content", "category"),
        [
            ("bin.dat", b"cobrar\x00", "[no_es_texto] "),
            ("latin.txt", "cobrar ñ".encode("latin-1"), "[no_es_texto] "),
            ("grande.txt", b"cobrar" + b"a" * _limits.MAX_READ_BYTES, "[demasiado_grande] "),
        ],
    )
    async def test_naming_such_a_file_directly_explains_why_it_cannot_be_searched(
        self, tool: SearchTextTool, area_dir: Path, name: str, content: bytes, category: str
    ) -> None:
        (area_dir / name).write_bytes(content)

        result = await grep(tool, name, "cobrar")

        assert result.is_error is True
        assert result.content.startswith(category)

    async def test_a_file_link_leaving_the_area_is_not_read(
        self, tool: SearchTextTool, area_dir: Path
    ) -> None:
        link(area_dir.parent / "outside" / "secret.txt", area_dir / "enlace.txt")

        result = await grep(tool, ".", "cobrar")

        assert "enlace.txt" not in result.content
        assert SENTINEL not in result.content

    async def test_a_folder_link_is_not_followed_even_if_it_leaves_the_area(
        self, tool: SearchTextTool, area_dir: Path
    ) -> None:
        link(area_dir.parent / "outside", area_dir / "salida", directory=True)

        result = await grep(tool, ".", "cobrar")

        assert "salida" not in result.content
        assert SENTINEL not in result.content

    async def test_a_file_link_staying_inside_the_area_is_searched(
        self, tool: SearchTextTool, area_dir: Path
    ) -> None:
        link(area_dir / "src" / "pago.py", area_dir / "alias.py")

        result = await grep(tool, "alias.py", "cobrar")

        assert result.is_error is False
        assert result.content.endswith("def cobrar(monto):")

    async def test_an_unreadable_subfolder_is_skipped_not_fatal(
        self, tool: SearchTextTool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_scandir = os.scandir

        def flaky(path: Any = ".") -> Any:
            if str(path).endswith("paquete"):
                raise PermissionError(13, "Permission denied", str(path))
            return real_scandir(path)

        monkeypatch.setattr(os, "scandir", flaky)

        result = await grep(tool, ".", "cobrar")

        assert result.is_error is False
        assert "src/pago.py:3" in result.content
        assert "paquete" not in result.content

    async def test_a_file_that_fails_to_open_is_skipped(
        self, tool: SearchTextTool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_open = Path.open

        def flaky(self: Path, *args: Any, **kwargs: Any) -> Any:
            if self.name == "pago.py":
                raise PermissionError(13, "Permission denied", str(self))
            return real_open(self, *args, **kwargs)

        monkeypatch.setattr(Path, "open", flaky)

        result = await grep(tool, ".", "cobrar")

        assert "pago.py" not in result.content
        assert "README.md:1" in result.content


class FlakyEntry:
    """A directory entry whose type check fails for one name, like a vanished file."""

    def __init__(self, entry: Any) -> None:
        self._entry = entry
        self.name: str = entry.name
        self.path: str = entry.path

    def is_symlink(self) -> bool:
        if self.name == "pago.py":
            raise OSError("vanished")
        return bool(self._entry.is_symlink())

    def is_dir(self, **kwargs: Any) -> bool:
        return bool(self._entry.is_dir(**kwargs))

    def is_file(self, **kwargs: Any) -> bool:
        return bool(self._entry.is_file(**kwargs))


class FlakyScan:
    def __init__(self, scanner: Any) -> None:
        self._scanner = scanner

    def __enter__(self) -> Any:
        return iter([FlakyEntry(entry) for entry in self._scanner])

    def __exit__(self, *exc: object) -> None:
        self._scanner.close()


class TestOddEntries:
    async def test_an_entry_that_cannot_be_inspected_is_skipped(
        self, tool: SearchTextTool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_scandir = os.scandir
        monkeypatch.setattr(os, "scandir", lambda path=".": FlakyScan(real_scandir(path)))

        result = await grep(tool, ".", "cobrar")

        assert result.is_error is False
        assert "pago.py" not in result.content
        assert "README.md:1" in result.content

    @pytest.mark.skipif(os.name == "nt", reason="needs POSIX named pipes")
    async def test_a_named_pipe_in_a_folder_is_neither_opened_nor_followed(
        self, tool: SearchTextTool, area_dir: Path
    ) -> None:
        os.mkfifo(area_dir / "tuberia")

        result = await grep(tool, ".", "cobrar")

        assert result.is_error is False
        assert "tuberia" not in result.content


class TestErrors:
    async def test_a_missing_path_is_a_clear_error(self, tool: SearchTextTool) -> None:
        result = await grep(tool, "no/existe", "x")

        assert result.is_error is True
        assert result.content.startswith("[no_existe] ")

    @pytest.mark.parametrize("query", ["", None, 42, "x" * (_limits.MAX_QUERY_CHARS + 1)])
    async def test_an_invalid_query_is_an_error_not_an_exception(
        self, tool: SearchTextTool, query: Any
    ) -> None:
        result = await grep(tool, ".", query)

        assert result.is_error is True
        assert result.content.startswith("[consulta_invalida] ")

    async def test_a_path_outside_is_rejected_and_nothing_leaks(self, tool: SearchTextTool) -> None:
        result = await grep(tool, "../outside", "cobrar")

        assert result.is_error is True
        assert result.content.startswith("[fuera_del_area] ")
        assert SENTINEL not in result.content

    async def test_without_an_area_nothing_is_searched(self, area_dir: Path) -> None:
        result = await grep(SearchTextTool(None), str(area_dir), "cobrar")

        assert result.is_error is True
        assert result.content.startswith("[sin_area] ")

    async def test_an_unexpected_failure_is_reported_without_a_trace(
        self, tool: SearchTextTool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def broken(self: Path) -> bool:
            raise RuntimeError("boom")

        monkeypatch.setattr(Path, "exists", broken)

        result = await grep(tool, ".", "cobrar")

        assert result.is_error is True
        assert result.content.startswith("[error_de_archivo] ")
        assert "boom" not in result.content

    @pytest.mark.parametrize("raw", [None, 42, "", "a\x00b"])
    async def test_a_path_that_is_not_usable_never_raises(
        self, tool: SearchTextTool, raw: Any
    ) -> None:
        result = await grep(tool, raw, "x")

        assert result.is_error is True
        assert result.content.startswith("[fuera_del_area] ")
