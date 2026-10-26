"""Architecture test of the context pieces (HU-02-01 / T003).

``core/context/`` is pure: it imports only the standard library and ``harness_agent.core``, does
no I/O (not even the standard modules that do it), reads no file nor environment and does not use
the terminal. The detectors of the other core guards are reused, not copied.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

PACKAGE = "harness_agent.core.context"
MODULE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core" / "context"


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


def test_context_only_imports_stdlib_and_core_and_has_no_io() -> None:
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
        "import tiktoken\n",
    ],
    ids=[
        "sqlite",
        "subprocess",
        "pathlib",
        "adapters",
        "config",
        "entorno",
        "terminal",
        "tokenizer",
    ],
)
def test_detectors_flag_violations(source: str, tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    assert scan_package(tmp_path) != []


def test_detectors_let_pure_code_through(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(
        "import hashlib\nimport json\nimport math\nfrom dataclasses import dataclass\n",
        encoding="utf-8",
    )
    assert scan_package(tmp_path) == []
