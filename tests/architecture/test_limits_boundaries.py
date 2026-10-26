"""Architecture test: ``core/limits.py`` is pure domain logic (HU-01-06 / T002).

The module that counts turns, tokens and time imports only the standard library and
``harness_agent.core``, does no I/O, reads no configuration or environment, does not use the
terminal and does not publish events (the loop publishes ``LIMIT_REACHED``).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_core_tools_stdlib_only import find_import_violations
from tests.architecture.test_loop_boundaries import forbidden_imports

PACKAGE = "harness_agent.core"
MODULE = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core" / "limits.py"
# Standard-library modules that do I/O: ``forbidden_imports`` accepts them because they are stdlib.
IO_STDLIB = {"sqlite3", "subprocess", "socket", "http", "urllib", "shutil", "tempfile", "os"}


def io_stdlib_imports(source: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules = [node.module]
        else:
            continue
        found.extend(
            f"{module} (stdlib I/O) at line {node.lineno}"
            for module in modules
            if module.split(".")[0] in IO_STDLIB
        )
    return found


def event_uses(source: str) -> list[str]:
    """Return uses of ``EventType`` / ``Event``: this module never publishes anything."""
    return [
        f"{node.id} at line {node.lineno}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Name) and node.id in {"EventType", "Event", "EventBus"}
    ]


def scan(source: str, name: str = "limits.py") -> list[str]:
    violations: list[str] = []
    violations.extend(forbidden_imports(source))
    violations.extend(find_import_violations(source, name))
    violations.extend(io_stdlib_imports(source))
    violations.extend(find_config_reads(source, name, PACKAGE))
    violations.extend(terminal_uses(source))
    violations.extend(event_uses(source))
    return violations


def test_the_module_exists() -> None:
    assert MODULE.is_file()


def test_the_module_is_pure_domain_logic() -> None:
    assert scan(MODULE.read_text(encoding="utf-8")) == []


def test_the_module_only_imports_the_entities_of_the_core() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
    }
    assert {m for m in imported if m.startswith("harness_agent")} == {"harness_agent.core.entities"}


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3\n",
        "import os\n",
        "from harness_agent.adapters.system import shell_output\n",
        "from harness_agent.config import load_config\n",
        "import litellm\n",
        "import os\nos.environ['X']\n",
        "print('hola')\n",
        "from harness_agent.core.events import EventType\nx = EventType.LIMIT_REACHED\n",
    ],
)
def test_the_scan_flags_violations(source: str) -> None:
    assert scan(source) != []
