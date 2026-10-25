"""The default list of denied commands is plain data that nothing applies here (T013)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from harness_agent.adapters.system.denied_commands import (
    DEFAULT_DENIED_COMMANDS,
    DeniedCommand,
    denied_commands_for,
)

SYSTEM_DIR = Path(__file__).resolve().parents[4] / "src" / "harness_agent" / "adapters" / "system"
TOOLS_DIR = SYSTEM_DIR.parent / "tools"


@pytest.mark.parametrize("interpreter", ["bash", "powershell"])
def test_each_interpreter_has_a_non_empty_list_of_complete_entries(interpreter: str) -> None:
    entries = denied_commands_for(interpreter)
    assert isinstance(entries, tuple)
    assert entries
    for entry in entries:
        assert isinstance(entry, DeniedCommand)
        assert entry.pattern.strip()
        assert entry.reason.strip()


def test_the_two_lists_differ() -> None:
    assert denied_commands_for("bash") != denied_commands_for("powershell")


def test_an_unknown_interpreter_has_an_empty_list() -> None:
    assert denied_commands_for("zsh") == ()


def test_the_mapping_is_read_only() -> None:
    with pytest.raises(TypeError):
        DEFAULT_DENIED_COMMANDS["bash"] = ()  # type: ignore[index]


def test_an_entry_cannot_be_changed() -> None:
    entry = denied_commands_for("bash")[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.pattern = "otra"  # type: ignore[misc]


@pytest.mark.parametrize(
    "path",
    [
        SYSTEM_DIR / "subprocess_shell.py",
        SYSTEM_DIR / "bash_shell.py",
        SYSTEM_DIR / "powershell_shell.py",
        TOOLS_DIR / "shell.py",
    ],
)
def test_nothing_in_the_shell_applies_the_list(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any("denied_commands" in name for name in imported)
