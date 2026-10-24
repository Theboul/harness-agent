"""Boundaries of ``adapters/`` (HU-01-03 / T014).

Closes the known gap "nothing checks that ``adapters/`` does not import ``cli/``" and guards the
two packages HU-01-03 creates: ``adapters/system/`` (the real authorized area) and
``adapters/tools/`` (the file tools). Each of them imports only the standard library, the public
API of the core (``from harness_agent.core import ...``) and its own package: no ``config``, no
``cli``, no ``observability``, no ``bootstrap``, no other adapter and no third party. They do not
read configuration or the environment and do not use the terminal. The detectors of the core guards
are reused, not copied.
"""

from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

import pytest

from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads

ADAPTERS_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "adapters"
ROOT_PACKAGE = "harness_agent.adapters"
GUARDED = ("system", "tools", "storage")
STDLIB = set(sys.stdlib_module_names) | {"__future__"}
CORE_API = "harness_agent.core"


def imported_modules(source: str, package: str) -> list[tuple[str, int]]:
    """Absolute dotted names imported by ``source`` (relative imports resolved from ``package``)."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[: len(package.split(".")) - node.level + 1]
                module = ".".join([*base, node.module] if node.module else base)
            else:
                module = node.module or ""
            found.append((module, node.lineno))
    return found


def cli_imports(source: str, package: str) -> list[str]:
    """Imports of ``harness_agent.cli`` (an adapter must never depend on the terminal layer)."""
    return [
        f"{module} at line {line}"
        for module, line in imported_modules(source, package)
        if module == "harness_agent.cli" or module.startswith("harness_agent.cli.")
    ]


def guarded_imports(source: str, own_package: str) -> list[str]:
    """Imports that are neither the standard library, the core API nor the own package."""
    found: list[str] = []
    for module, line in imported_modules(source, own_package):
        if module.split(".")[0] in STDLIB:
            continue
        if module == CORE_API:
            continue
        if module == own_package or module.startswith(own_package + "."):
            continue
        found.append(f"{module} at line {line}")
    return found


def scan_all_adapters(directory: Path) -> list[str]:
    """Rule for every adapter: no import of ``cli``."""
    files = sorted(directory.rglob("*.py"))
    assert files, f"No Python files found under {directory}"
    violations: list[str] = []
    for path in files:
        package = ROOT_PACKAGE + "".join(
            "." + part for part in path.relative_to(directory).parts[:-1]
        )
        violations.extend(
            f"{path.name}: {m}" for m in cli_imports(path.read_text("utf-8"), package)
        )
    return violations


def scan_guarded(directory: Path, subpackage: str) -> list[str]:
    """Rules for ``system/`` and ``tools/``: allowed imports, no config reads, no terminal."""
    files = sorted(directory.rglob("*.py"))
    assert files, f"No Python files found under {directory}"
    package = f"{ROOT_PACKAGE}.{subpackage}"
    violations: list[str] = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        violations.extend(f"{path.name}: {m}" for m in guarded_imports(source, package))
        violations.extend(
            f"{path.name}: {m}" for m in find_config_reads(source, path.name, package)
        )
        violations.extend(f"{path.name}: {m}" for m in terminal_uses(source))
    return violations


def test_no_adapter_imports_the_terminal_layer() -> None:
    assert scan_all_adapters(ADAPTERS_DIR) == []


@pytest.mark.parametrize("subpackage", GUARDED)
def test_system_and_tools_import_only_stdlib_core_api_and_themselves(subpackage: str) -> None:
    directory = ADAPTERS_DIR / subpackage

    assert len(list(directory.rglob("*.py"))) >= 2
    assert scan_guarded(directory, subpackage) == []


def test_the_baseline_covers_at_least_eight_modules() -> None:
    modules = [p for name in GUARDED for p in (ADAPTERS_DIR / name).rglob("*.py")]

    assert len(modules) >= 8


def test_tools_and_system_do_not_depend_on_each_other() -> None:
    for subpackage, other in (("tools", "system"), ("system", "tools")):
        for path in (ADAPTERS_DIR / subpackage).rglob("*.py"):
            modules = [
                m
                for m, _ in imported_modules(
                    path.read_text("utf-8"), f"{ROOT_PACKAGE}.{subpackage}"
                )
            ]
            assert not [m for m in modules if m.startswith(f"{ROOT_PACKAGE}.{other}")], path.name


# --- detector self-tests: each rule must catch what it claims to catch ---------------------------

PKG = "harness_agent.adapters.tools"


@pytest.mark.parametrize(
    "source",
    [
        "import harness_agent.cli\n",
        "from harness_agent.cli import render\n",
        "from harness_agent.cli.app import run_cli\n",
        "from ...cli import app\n",
    ],
)
def test_the_cli_detector_flags_each_form(source: str) -> None:
    assert cli_imports(source, PKG) != []


@pytest.mark.parametrize(
    "source",
    [
        "import litellm\n",
        "from openai import OpenAI\n",
        "from harness_agent.config import load_config\n",
        "from harness_agent.core.loop import AgentLoop\n",
        "from harness_agent.core.interfaces import Tool\n",
        "import harness_agent.observability\n",
        "from harness_agent.bootstrap import build\n",
        "from harness_agent.adapters.converters import base\n",
        "from harness_agent.adapters.system import WorkspaceArea\n",
        "from harness_agent.cli import render\n",
    ],
)
def test_the_import_detector_flags_each_forbidden_form(source: str) -> None:
    assert guarded_imports(source, PKG) != []


@pytest.mark.parametrize(
    "source",
    [
        "import os\n",
        "from pathlib import Path\n",
        "from __future__ import annotations\n",
        "from harness_agent.core import Tool, ToolResult\n",
        "from harness_agent.adapters.tools._limits import MAX_READ_BYTES\n",
        "from ._limits import MAX_READ_BYTES\n",
        "from . import _paths\n",
    ],
)
def test_the_import_detector_lets_the_allowed_forms_through(source: str) -> None:
    assert guarded_imports(source, PKG) == []


@pytest.mark.parametrize(
    "source",
    [
        "import os\nos.environ['X']\n",
        "from harness_agent.config import load_config\n",
        "print('hola')\n",
        "input()\n",
        "import sys\nsys.stdout.write('x')\n",
    ],
)
def test_the_guard_flags_config_reads_and_terminal_use(source: str, tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")

    assert scan_guarded(tmp_path, "tools") != []


def test_mutation_a_forbidden_import_added_to_a_copy_of_the_real_package_is_caught(
    tmp_path: Path,
) -> None:
    copy = tmp_path / "tools"
    shutil.copytree(ADAPTERS_DIR / "tools", copy, ignore=shutil.ignore_patterns("__pycache__"))
    target = copy / "read_file.py"
    target.write_text("from harness_agent.cli import render\n" + target.read_text("utf-8"), "utf-8")

    assert scan_guarded(copy, "tools") != []
    assert scan_all_adapters(tmp_path) != []


def test_the_real_sources_were_not_edited_by_the_mutation() -> None:
    assert "harness_agent.cli" not in (ADAPTERS_DIR / "tools" / "read_file.py").read_text("utf-8")


# --- storage (HU-03-01 / T009) -------------------------------------------------------------------

STORAGE_PKG = "harness_agent.adapters.storage"
CORE_DIR = ADAPTERS_DIR.parent / "core"


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3\n",
        "import uuid\n",
        "from harness_agent.core import SessionSummary\n",
        "from harness_agent.adapters.storage.errors import SessionStoreError\n",
        "from .errors import SessionStoreError\n",
    ],
)
def test_storage_may_use_sqlite_the_core_api_and_its_own_package(source: str) -> None:
    assert guarded_imports(source, STORAGE_PKG) == []


@pytest.mark.parametrize(
    "source",
    [
        "from harness_agent.adapters.tools import ReadFileTool\n",
        "from harness_agent.adapters.system import WorkspaceArea\n",
        "from harness_agent.config import load_config\n",
        "from harness_agent.core.interfaces.storage import SessionStore\n",
    ],
)
def test_storage_may_not_reach_other_adapters_config_or_core_internals(source: str) -> None:
    assert guarded_imports(source, STORAGE_PKG) != []


def test_storage_does_not_depend_on_the_other_adapters() -> None:
    for path in (ADAPTERS_DIR / "storage").rglob("*.py"):
        modules = [m for m, _ in imported_modules(path.read_text("utf-8"), STORAGE_PKG)]
        others = (f"{ROOT_PACKAGE}.tools", f"{ROOT_PACKAGE}.system", f"{ROOT_PACKAGE}.converters")
        assert not [m for m in modules if m.startswith(others)], path.name


def test_the_core_does_not_import_sqlite3() -> None:
    """Closes the known gap for the one stdlib I/O module the storage adapter owns."""
    offenders = [
        f"{path.relative_to(CORE_DIR)}: {module} at line {line}"
        for path in sorted(CORE_DIR.rglob("*.py"))
        for module, line in imported_modules(path.read_text("utf-8"), "harness_agent.core")
        if module.split(".")[0] == "sqlite3"
    ]

    assert offenders == []
