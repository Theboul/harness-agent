"""Plantilla: guarda AST de un módulo nuevo de ``core/`` (copiar a tests/architecture/).

Renombrar a ``tests/architecture/test_<modulo>_boundaries.py`` y ajustar ``PACKAGE`` y
``MODULE_DIR``. Reutiliza los detectores existentes (no los copies): mismo patrón que
``tests/architecture/test_permissions_boundaries.py``. Añade al final las reglas propias del
módulo (como ``unguarded_allows`` en permisos) con su autoprueba sobre fragmentos sintéticos.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports

PACKAGE = "harness_agent.core.<modulo>"
MODULE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core" / "<modulo>"
# Standard-library modules that do I/O: ``forbidden_imports`` accepts them because they are stdlib.
IO_STDLIB = {"sqlite3", "subprocess", "socket", "http", "urllib", "shutil", "tempfile"}


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


def test_module_only_imports_stdlib_and_core_and_has_no_io() -> None:
    assert scan_package(MODULE_DIR) == []


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3\n",
        "from harness_agent.adapters import x\n",
        "from harness_agent.config import load_config\n",
        "import os\nos.environ['X']\n",
        "print('hola')\n",
    ],
)
def test_detectors_flag_violations(source: str, tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    assert scan_package(tmp_path) != []
