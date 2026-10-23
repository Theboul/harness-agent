"""Without a configured area the file tools never act (HU-01-03 / T012, AC-04)."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.tools.list_files import ListFilesTool
from harness_agent.adapters.tools.read_file import ReadFileTool
from harness_agent.adapters.tools.search_text import SearchTextTool
from harness_agent.adapters.tools.write_file import WriteFileTool
from harness_agent.core import Tool

TOOLS: list[tuple[Callable[[None], Tool], dict[str, Any]]] = [
    (WriteFileTool, {"path": "x.txt", "content": "x"}),
    (ReadFileTool, {"path": "x.txt"}),
    (ListFilesTool, {"path": "."}),
    (SearchTextTool, {"path": ".", "query": "x"}),
]


@pytest.mark.parametrize(("factory", "args"), TOOLS, ids=[f.__name__ for f, _ in TOOLS])
async def test_every_tool_without_an_area_explains_and_does_nothing(
    factory: Callable[[None], Tool],
    args: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_: object, **__: object) -> None:
        raise AssertionError("without an area the disk must not be touched")

    monkeypatch.chdir(tmp_path)
    for target in (Path.open, Path.exists, Path.mkdir, Path.write_bytes, Path.iterdir):
        monkeypatch.setattr(Path, target.__name__, forbidden)
    monkeypatch.setattr(os, "scandir", forbidden)
    monkeypatch.setattr(os.path, "realpath", forbidden)

    result = await factory(None).run(args)

    assert result.is_error is True
    assert result.content.startswith("[sin_area] ")
    assert "workspace_root" in result.content


@pytest.mark.parametrize(("factory", "args"), TOOLS, ids=[f.__name__ for f, _ in TOOLS])
async def test_the_current_directory_is_never_used_as_a_default_area(
    factory: Callable[[None], Tool],
    args: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "x.txt").write_text("x", encoding="utf-8", newline="")
    monkeypatch.chdir(tmp_path)

    result = await factory(None).run(args)

    assert result.content.startswith("[sin_area] ")
    assert (tmp_path / "x.txt").read_text(encoding="utf-8") == "x"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["x.txt"]
