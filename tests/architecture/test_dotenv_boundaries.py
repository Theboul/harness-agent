"""Boundaries of the ``.env`` reader ``adapters/system/dotenv.py`` (proposed HU-00-08.1).

The reader is the only place that opens the file; it must stay a small, leak-free adapter:

* it imports only the standard library (not even the package: it needs no domain type);
* it does not read the environment (``bootstrap.py`` hands the environment in), does not use the
  console and does not start processes;
* no ``except`` handler binds the exception (an error text could hold a line of the file);
* only ``bootstrap.py`` (and the package that exports it) names ``read_dotenv``.

Each detector has a self-test with synthetic fragments and a mutation test on a copy of the file.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_adapters_boundaries import STDLIB, imported_modules
from tests.architecture.test_bootstrap_boundaries import console_calls, environment_reads

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
DOTENV = PACKAGE_DIR / "adapters" / "system" / "dotenv.py"
FORBIDDEN_STDLIB = frozenset({"os", "subprocess", "sys", "logging", "socket"})
ALLOWED_NAMERS = {"bootstrap.py", "dotenv.py", "__init__.py"}


def non_stdlib_imports(source: str) -> list[str]:
    return [
        f"{module} at line {line}"
        for module, line in imported_modules(source, "harness_agent.adapters.system")
        if module.split(".")[0] not in STDLIB or module.split(".")[0] in FORBIDDEN_STDLIB
    ]


def bound_exceptions(source: str) -> list[str]:
    """``except X as name`` handlers: the name could carry a line of the file into a message."""
    return [
        f"except ... as {node.name} at line {node.lineno}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ExceptHandler) and node.name
    ]


def namers_of(package_dir: Path, name: str) -> set[str]:
    found: set[str] = set()
    for path in package_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if name in text:
            found.add(path.name)
    return found


# --- the real code -----------------------------------------------------------------------------


def test_dotenv_imports_only_the_standard_library_without_io_modules() -> None:
    assert non_stdlib_imports(DOTENV.read_text(encoding="utf-8")) == []


def test_dotenv_does_not_read_the_environment_nor_use_the_console() -> None:
    source = DOTENV.read_text(encoding="utf-8")

    assert environment_reads(source) == []
    assert console_calls(source) == []


def test_dotenv_never_binds_an_exception() -> None:
    assert bound_exceptions(DOTENV.read_text(encoding="utf-8")) == []


def test_only_the_composition_root_reads_a_dotenv() -> None:
    assert namers_of(PACKAGE_DIR, "read_dotenv") <= ALLOWED_NAMERS


# --- self-tests of the detectors ---------------------------------------------------------------


@pytest.mark.parametrize(
    "fragment",
    [
        "import os\n",
        "import subprocess\n",
        "import requests\n",
        "from harness_agent.core import Message\n",
        "import logging\n",
    ],
)
def test_non_stdlib_imports_detects_a_violation(fragment: str) -> None:
    assert non_stdlib_imports(fragment) != []


def test_non_stdlib_imports_accepts_the_standard_library() -> None:
    assert non_stdlib_imports("import re\nfrom pathlib import Path\n") == []


def test_bound_exceptions_detects_a_bound_handler_only() -> None:
    assert bound_exceptions("try:\n    x()\nexcept OSError as e:\n    pass\n") != []
    assert bound_exceptions("try:\n    x()\nexcept OSError:\n    pass\n") == []


# --- mutation tests on a copy of the file ------------------------------------------------------


def test_a_leaky_handler_in_a_copy_is_detected(tmp_path: Path) -> None:
    copy = tmp_path / "dotenv.py"
    copy.write_text(
        DOTENV.read_text(encoding="utf-8")
        + "\ntry:\n    pass\nexcept OSError as problem:\n    raise ValueError(problem)\n",
        encoding="utf-8",
    )

    assert bound_exceptions(copy.read_text(encoding="utf-8")) != []


def test_an_environment_read_in_a_copy_is_detected(tmp_path: Path) -> None:
    copy = tmp_path / "dotenv.py"
    copy.write_text(
        DOTENV.read_text(encoding="utf-8") + "\nimport os\nSNEAKY = os.environ.get('X')\n",
        encoding="utf-8",
    )
    source = copy.read_text(encoding="utf-8")

    assert environment_reads(source) != [] and non_stdlib_imports(source) != []
