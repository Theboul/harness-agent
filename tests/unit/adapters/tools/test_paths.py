"""Shared helpers of the file tools: limits, error results and real-path resolution (T005)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools import _limits
from harness_agent.adapters.tools._paths import (
    TRUNCATED,
    bounded_path,
    bounded_text,
    error_result,
    resolve_in_area,
)
from harness_agent.core import AuthorizedArea, ToolResult

SENTINEL = "VALOR-DE-PRUEBA-123"


class ScriptedArea(AuthorizedArea):
    """An area whose answers are scripted, to test how the helper uses the port."""

    def __init__(self, root: Path, answers: list[Any]) -> None:
        self._root = root
        self._answers = list(answers)
        self.asked: list[Any] = []

    @property
    def root(self) -> Path:
        return self._root

    def contains(self, path: Path | str) -> bool:
        self.asked.append(path)
        answer = self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer  # type: ignore[no-any-return]


class TestLimits:
    def test_the_documented_values(self) -> None:
        assert _limits.MAX_READ_BYTES == 262_144
        assert _limits.MAX_WRITE_BYTES == 1_048_576
        assert _limits.MAX_LIST_ENTRIES == 200
        assert _limits.MAX_MATCHES == 50
        assert _limits.MAX_LINE_CHARS == 200
        assert _limits.MAX_QUERY_CHARS == 200
        assert _limits.MAX_RESULT_CHARS == 20_000


class TestErrorResult:
    def test_it_is_a_structured_error_with_the_category_label(self) -> None:
        result = error_result("no_existe", "La ruta 'x' no existe. Usa 'listar_archivos'.")

        assert isinstance(result, ToolResult)
        assert result.is_error is True
        assert result.call_id == ""
        assert result.content == "[no_existe] La ruta 'x' no existe. Usa 'listar_archivos'."


class TestBounded:
    def test_a_short_path_is_kept(self) -> None:
        assert bounded_path("src/main.py") == "src/main.py"

    def test_a_long_path_is_cut_to_100_characters_with_an_ellipsis(self) -> None:
        text = bounded_path("a" * 500)

        assert len(text) == 100
        assert text.endswith("...")

    def test_control_characters_are_replaced(self) -> None:
        assert bounded_path("a\x00b\x1b[31mc\nd") == "a?b?[31mc?d"

    def test_other_types_are_shown_as_text(self) -> None:
        assert bounded_path(42) == "42"
        assert bounded_path(None) == "None"

    def test_text_within_the_limit_is_untouched(self) -> None:
        assert bounded_text("hola", 10) == "hola"
        assert bounded_text("x" * 10, 10) == "x" * 10

    def test_text_over_the_limit_is_cut_with_a_notice_and_never_exceeds_it(self) -> None:
        cut = bounded_text("x" * 100, 40)

        assert len(cut) == 40
        assert cut.endswith(TRUNCATED)

    def test_the_default_limit_is_the_result_limit(self) -> None:
        assert len(bounded_text("x" * (_limits.MAX_RESULT_CHARS + 5))) == _limits.MAX_RESULT_CHARS


class TestResolveInArea:
    @pytest.fixture
    def area_dir(self, tmp_path: Path) -> Path:
        (tmp_path / "area" / "src").mkdir(parents=True)
        (tmp_path / "area" / "src" / "main.py").write_text("x", encoding="utf-8")
        (tmp_path / "outside").mkdir()
        (tmp_path / "outside" / "secret.txt").write_text(SENTINEL, encoding="utf-8")
        return tmp_path / "area"

    def test_without_an_area_the_result_is_sin_area(self) -> None:
        result = resolve_in_area(None, "src/main.py")

        assert isinstance(result, ToolResult)
        assert result.is_error is True
        assert result.content.startswith("[sin_area] ")
        assert "workspace_root" in result.content

    def test_a_path_inside_gives_its_real_path(self, area_dir: Path) -> None:
        area = WorkspaceArea(area_dir)

        result = resolve_in_area(area, "src/main.py")

        assert result == area.root / "src" / "main.py"

    def test_a_path_that_does_not_exist_yet_is_still_resolved(self, area_dir: Path) -> None:
        area = WorkspaceArea(area_dir)

        assert resolve_in_area(area, "nuevo/archivo.txt") == area.root / "nuevo" / "archivo.txt"

    def test_an_absolute_path_inside_is_resolved(self, area_dir: Path) -> None:
        area = WorkspaceArea(area_dir)

        assert resolve_in_area(area, str(area.root / "src")) == area.root / "src"

    @pytest.mark.parametrize("raw", ["../outside/secret.txt", "/etc/hosts", "src/../../x"])
    def test_a_path_outside_is_rejected_and_the_message_hides_the_real_path(
        self, area_dir: Path, raw: str
    ) -> None:
        result = resolve_in_area(WorkspaceArea(area_dir), raw)

        assert isinstance(result, ToolResult)
        assert result.content.startswith("[fuera_del_area] ")
        assert str(area_dir.parent) not in result.content
        assert os.path.realpath(area_dir.parent) not in result.content
        assert SENTINEL not in result.content

    def test_the_message_echoes_only_the_bounded_path_that_was_received(
        self, area_dir: Path
    ) -> None:
        result = resolve_in_area(WorkspaceArea(area_dir), "../" + "z" * 300)

        assert isinstance(result, ToolResult)
        assert "z" * 50 in result.content
        assert "z" * 150 not in result.content

    def test_the_text_is_checked_before_the_disk_is_touched(
        self, area_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        area = ScriptedArea(area_dir, [False])

        def forbidden(*_: object, **__: object) -> str:
            raise AssertionError("realpath must not run when the text is already outside")

        monkeypatch.setattr(os.path, "realpath", forbidden)

        result = resolve_in_area(area, "\\\\servidor\\recurso")

        assert isinstance(result, ToolResult)
        assert area.asked == ["\\\\servidor\\recurso"]

    def test_the_area_is_asked_twice_first_the_text_then_the_real_path(
        self, area_dir: Path
    ) -> None:
        area = ScriptedArea(area_dir, [True, True])

        result = resolve_in_area(area, "src/main.py")

        assert result == Path(os.path.realpath(area_dir / "src" / "main.py"))
        assert area.asked == ["src/main.py", result]

    def test_if_the_real_path_is_outside_it_is_rejected_even_if_the_text_was_not(
        self, area_dir: Path
    ) -> None:
        area = ScriptedArea(area_dir, [True, False])

        result = resolve_in_area(area, "src/main.py")

        assert isinstance(result, ToolResult)
        assert result.content.startswith("[fuera_del_area] ")

    @pytest.mark.parametrize("answer", [1, "yes", None, [True]])
    def test_only_an_exact_true_is_accepted(self, area_dir: Path, answer: Any) -> None:
        result = resolve_in_area(ScriptedArea(area_dir, [answer]), "src")

        assert isinstance(result, ToolResult)

    def test_an_area_that_raises_means_outside(self, area_dir: Path) -> None:
        result = resolve_in_area(ScriptedArea(area_dir, [RuntimeError("boom")]), "src")

        assert isinstance(result, ToolResult)
        assert result.content.startswith("[fuera_del_area] ")
        assert "boom" not in result.content

    @pytest.mark.parametrize("raw", [None, 42, b"src", ["src"], "a\x00b", "", "   "])
    def test_a_path_that_is_not_usable_text_is_outside_and_never_raises(
        self, area_dir: Path, raw: Any
    ) -> None:
        result = resolve_in_area(WorkspaceArea(area_dir), raw)

        assert isinstance(result, ToolResult)
        assert result.content.startswith("[fuera_del_area] ")
