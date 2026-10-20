"""Architecture test: ``core/tools/`` may import only stdlib and ``harness_agent.core``.

Enforces FR-016 / RNF-13 / Principio III for the tool registry package (HU-01-02 / T002).
The existing boundary test only looks for a blacklist of provider SDKs; this one is a
whitelist, so any third-party package (for example ``jsonschema``) or any project layer
outside the core (``adapters``, ``cli``, ``observability``) is rejected.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core" / "tools"
CORE_PACKAGE = "harness_agent.core"


def _is_allowed(module: str) -> bool:
    """Allow the standard library and ``harness_agent.core`` (but not the bare project root)."""
    if module.split(".")[0] in sys.stdlib_module_names:
        return True
    return module == CORE_PACKAGE or module.startswith(CORE_PACKAGE + ".")


def find_import_violations(source: str, filename: str = "<source>") -> list[str]:
    """Return one message per absolute import that is neither stdlib nor ``harness_agent.core``.

    Relative imports stay inside the package being checked, so they are always allowed.
    """
    violations: list[str] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules = [node.module or ""]
        else:
            continue
        violations.extend(
            f"{filename}:{node.lineno}: imports '{module}'"
            for module in modules
            if not _is_allowed(module)
        )
    return violations


def test_core_tools_imports_only_stdlib_and_core() -> None:
    python_files = sorted(TOOLS_DIR.rglob("*.py"))
    assert python_files, f"No Python files found under {TOOLS_DIR}"

    violations: list[str] = []
    for file_path in python_files:
        violations.extend(
            find_import_violations(file_path.read_text(encoding="utf-8"), file_path.name)
        )

    assert not violations, "core/tools/ imports outside stdlib and harness_agent.core:\n" + (
        "\n".join(violations)
    )


@pytest.mark.parametrize(
    "source, offender",
    [
        ("import jsonschema\n", "jsonschema"),
        ("from jsonschema import validate\n", "jsonschema"),
        ("import litellm.utils\n", "litellm.utils"),
        ("from harness_agent.adapters import x\n", "harness_agent.adapters"),
        ("from harness_agent.cli.app import main\n", "harness_agent.cli.app"),
        ("import harness_agent.observability\n", "harness_agent.observability"),
        ("import harness_agent\n", "harness_agent"),
        ("from harness_agent import core\n", "harness_agent"),
    ],
)
def test_checker_flags_imports_outside_stdlib_and_core(source: str, offender: str) -> None:
    violations = find_import_violations(source)

    assert len(violations) == 1
    assert offender in violations[0]


@pytest.mark.parametrize(
    "source",
    [
        "import json\n",
        "import os.path\n",
        "from dataclasses import dataclass\n",
        "from __future__ import annotations\n",
        "from harness_agent.core import ToolResult\n",
        "from harness_agent.core.interfaces.tool import Tool\n",
        "import harness_agent.core.entities\n",
        "from .errors import Violation\n",
        "from . import registry\n",
        "from ..interfaces import tool\n",
    ],
)
def test_checker_allows_stdlib_core_and_relative_imports(source: str) -> None:
    assert find_import_violations(source) == []


def test_checker_finds_imports_nested_in_functions_and_blocks() -> None:
    source = "def f() -> None:\n    if True:\n        import requests\n"

    violations = find_import_violations(source)

    assert len(violations) == 1
    assert "requests" in violations[0]


def test_checker_reports_filename_and_line_number() -> None:
    violations = find_import_violations("import json\nimport jsonschema\n", "registry.py")

    assert violations == ["registry.py:2: imports 'jsonschema'"]
