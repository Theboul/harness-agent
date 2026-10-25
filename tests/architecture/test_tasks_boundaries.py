"""Architecture test of the task rules (HU-11-01 / T012).

``core/tasks/`` is pure: it imports only the standard library and ``harness_agent.core``, does
no I/O (not even the standard modules that do it), reads no file nor environment and does not use
the terminal. The detectors of the other core guards are reused, not copied.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports

PACKAGE = "harness_agent.core.tasks"
MODULE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core" / "tasks"
# Standard-library modules that do I/O: ``forbidden_imports`` accepts them because they are stdlib.
IO_STDLIB = {"sqlite3", "subprocess", "socket", "http", "urllib", "shutil", "tempfile", "pathlib"}


def io_stdlib_imports(source: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules = [node.module]
        else:
            continue
        for module in modules:
            if module.split(".")[0] in IO_STDLIB:
                found.append(f"{module} (stdlib I/O) at line {node.lineno}")
    return found


def scan_package(directory: Path) -> list[str]:
    files = sorted(directory.rglob("*.py"))
    assert files, f"No Python files found under {directory}"
    violations: list[str] = []
    for file_path in files:
        source = file_path.read_text(encoding="utf-8")
        name = file_path.name
        violations.extend(f"{name}: {m}" for m in forbidden_imports(source))
        violations.extend(f"{name}: {m}" for m in io_stdlib_imports(source))
        violations.extend(f"{name}: {m}" for m in find_config_reads(source, name, PACKAGE))
        violations.extend(f"{name}: {m}" for m in terminal_uses(source))
    return violations


def test_tasks_only_import_stdlib_and_core_and_have_no_io() -> None:
    assert scan_package(MODULE_DIR) == []


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3\n",
        "import subprocess\n",
        "from pathlib import Path\n",
        "from harness_agent.adapters import x\n",
        "from harness_agent.config import load_config\n",
        "import os\nos.environ['X']\n",
        "print('hola')\n",
    ],
    ids=["sqlite", "subprocess", "pathlib", "adapters", "config", "entorno", "terminal"],
)
def test_detectors_flag_violations(source: str, tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    assert scan_package(tmp_path) != []


def test_detectors_let_pure_code_through(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(
        "import re\nfrom dataclasses import dataclass\nfrom enum import Enum\n", encoding="utf-8"
    )
    assert scan_package(tmp_path) == []
