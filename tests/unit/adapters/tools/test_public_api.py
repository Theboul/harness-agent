"""Public API of ``adapters.tools`` and ``adapters.system`` (HU-01-03 / T015, HU-01-04)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import harness_agent.adapters.system as system
import harness_agent.adapters.tools as tools
from harness_agent.adapters.system.workspace_area import WorkspaceArea, windows_path_problem
from harness_agent.adapters.tools import _limits
from harness_agent.adapters.tools.list_files import ListFilesTool
from harness_agent.adapters.tools.read_file import ReadFileTool
from harness_agent.adapters.tools.search_text import SearchTextTool
from harness_agent.adapters.tools.shell import ShellTool
from harness_agent.adapters.tools.write_file import WriteFileTool

SRC = Path(__file__).resolve().parents[4] / "src"
TOOLS_API = {
    "ReadFileTool",
    "WriteFileTool",
    "ListFilesTool",
    "SearchTextTool",
    "ShellTool",
    "MAX_READ_BYTES",
    "MAX_WRITE_BYTES",
    "MAX_LIST_ENTRIES",
    "MAX_MATCHES",
    "MAX_LINE_CHARS",
    "MAX_QUERY_CHARS",
    "MAX_RESULT_CHARS",
    "DEFAULT_SHELL_TIMEOUT_SECONDS",
    "MAX_SHELL_TIMEOUT_SECONDS",
    "MAX_COMMAND_CHARS",
}
SYSTEM_API = {
    "BashShell",
    "DEFAULT_DENIED_COMMANDS",
    "DeniedCommand",
    "PowerShellShell",
    "ShellStartError",
    "SubprocessShell",
    "WorkspaceArea",
    "denied_commands_for",
    "environment_notice",
    "interpreter_for",
    "select_shell",
    "windows_path_problem",
}


def _clean_environment() -> dict[str, str]:
    """The environment of the test without the variables that make a child process write coverage
    data into the repository (pytest-cov), plus the source path. Windows needs its own variables
    (``SYSTEMROOT``) for Python to start, so the rest is kept."""
    kept = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COV_CORE", "COVERAGE"))
    }
    return {**kept, "PYTHONPATH": str(SRC)}


def test_tools_expose_the_tools_and_the_limits() -> None:
    assert set(tools.__all__) == TOOLS_API
    assert len(tools.__all__) == len(TOOLS_API)
    assert tools.ReadFileTool is ReadFileTool
    assert tools.WriteFileTool is WriteFileTool
    assert tools.ListFilesTool is ListFilesTool
    assert tools.SearchTextTool is SearchTextTool
    assert tools.ShellTool is ShellTool
    for name in TOOLS_API:
        assert hasattr(tools, name), name
    assert tools.MAX_READ_BYTES == _limits.MAX_READ_BYTES


def test_system_exposes_the_area_and_the_windows_check() -> None:
    assert set(system.__all__) == SYSTEM_API
    assert system.WorkspaceArea is WorkspaceArea
    assert system.windows_path_problem is windows_path_problem


def test_the_helpers_of_the_package_are_not_public_api() -> None:
    for name in ("error_result", "resolve_in_area", "bounded_path", "bounded_text", "_paths"):
        assert name not in tools.__all__
    assert not hasattr(tools, "resolve_in_area")
    assert not hasattr(tools, "error_result")


@pytest.mark.parametrize(
    "statement",
    [
        "import harness_agent.adapters.system",
        "import harness_agent.adapters.tools",
        "from harness_agent.adapters.tools import ReadFileTool, WriteFileTool",
        "from harness_agent.adapters.system import WorkspaceArea",
        "import harness_agent.adapters.tools._paths",
        "import harness_agent.adapters.tools.search_text",
    ],
)
def test_every_module_imports_on_its_own_in_a_fresh_interpreter(statement: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        env=_clean_environment(),
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
