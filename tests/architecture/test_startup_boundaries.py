"""Architecture guards of the startup routine of a resumed ticket (HU-11-08.2).

* ``core/startup/`` imports only the standard library and ``harness_agent.core``, does no I/O (the
  reads and the commands are injected), reads no configuration or environment and does not use the
  terminal. It does not import the agent loop.
* The gated runner and the routine never catch cancellation (``Exception`` only).
* The text of the briefing (``briefing.py``) is pure: no ``async`` and it never reads a ``command``
  attribute, so the command that ran can never reach the agent.
* The gated runner turns an unknown answer of the policy into a denial: ``PermissionDecision.ALLOW``
  appears once, in the only comparison that lets a command run.
* **Only ``bootstrap.py`` builds the routine**: no other module of ``src/`` names
  ``StartupRoutine`` or ``GatedCommandRunner`` apart from the package itself and the exports.

The rules have a self-test with synthetic fragments and a mutation test on a copy.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_approvals_boundaries import catches_cancellation, imported_modules
from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_progress_boundaries import attributes_read
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
STARTUP_DIR = SRC / "core" / "startup"
BRIEFING_FILE = STARTUP_DIR / "briefing.py"
GATED_FILE = STARTUP_DIR / "gated.py"
ROUTINE_FILE = STARTUP_DIR / "routine.py"
PACKAGE = "harness_agent.core.startup"
BUILT_ONLY_BY_BOOTSTRAP = {"StartupRoutine", "GatedCommandRunner"}
ALLOWED_FILES = (Path("bootstrap.py"), Path("core") / "__init__.py")


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
        violations.extend(
            f"{name}: imports the loop ({m})"
            for m in imported_modules(source)
            if m == "harness_agent.core.loop" or m.startswith("harness_agent.core.loop.")
        )
    return violations


def names_any(source: str, names: set[str]) -> bool:
    """Whether the source uses one of ``names`` (an import, a call or an annotation)."""
    return any(
        (isinstance(node, ast.Name) and node.id in names)
        or (isinstance(node, ast.alias) and node.name in names)
        for node in ast.walk(ast.parse(source))
    )


def has_async(source: str) -> bool:
    return any(isinstance(node, ast.AsyncFunctionDef) for node in ast.walk(ast.parse(source)))


def allow_mentions(source: str) -> int:
    """How many times ``PermissionDecision.ALLOW`` is named."""
    return sum(
        1
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute)
        and node.attr == "ALLOW"
        and isinstance(node.value, ast.Name)
        and node.value.id == "PermissionDecision"
    )


# --- the real code ---------------------------------------------------------------------------


def test_the_startup_package_is_pure() -> None:
    assert scan_package(STARTUP_DIR) == []


@pytest.mark.parametrize("path", [GATED_FILE, ROUTINE_FILE], ids=["gated", "routine"])
def test_cancellation_is_never_caught(path: Path) -> None:
    assert catches_cancellation(path.read_text(encoding="utf-8")) == []


def test_the_briefing_is_pure_and_never_reads_the_command() -> None:
    source = BRIEFING_FILE.read_text(encoding="utf-8")
    assert not has_async(source)
    assert attributes_read(source, {"command"}) == []


def test_the_gated_runner_allows_only_on_an_exact_allow() -> None:
    assert allow_mentions(GATED_FILE.read_text(encoding="utf-8")) == 1


def test_only_bootstrap_builds_the_routine() -> None:
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC)
        if relative in ALLOWED_FILES or Path("core") / "startup" in relative.parents:
            continue
        if names_any(path.read_text(encoding="utf-8"), BUILT_ONLY_BY_BOOTSTRAP):
            offenders.append(relative.as_posix())
    assert offenders == []


# --- self-tests of the detectors ---------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "import pathlib\n",
        "import subprocess\n",
        "from harness_agent.adapters import x\n",
        "from harness_agent.core.loop import AgentLoop\n",
        "import os\nos.environ['X']\n",
        "print('hola')\n",
    ],
    ids=["pathlib", "subprocess", "adapters", "loop", "entorno", "terminal"],
)
def test_the_scan_flags_violations(source: str, tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    assert scan_package(tmp_path) != []


def test_the_scan_lets_pure_code_through(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(
        "import re\nfrom dataclasses import dataclass\nfrom typing import Protocol\n",
        encoding="utf-8",
    )
    assert scan_package(tmp_path) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from x import StartupRoutine\n", True),
        ("x = GatedCommandRunner(p)\n", True),
        ("x = Other(p)\n", False),
    ],
)
def test_the_builder_detector(source: str, expected: bool) -> None:
    assert names_any(source, BUILT_ONLY_BY_BOOTSTRAP) is expected


def test_the_cancellation_guard_catches_a_mutation_of_the_gated_runner() -> None:
    source = GATED_FILE.read_text(encoding="utf-8")
    mutated = source.replace("except Exception:", "except BaseException:")
    assert mutated != source
    assert catches_cancellation(mutated) != []


def test_the_command_guard_catches_a_mutation_of_the_briefing() -> None:
    source = BRIEFING_FILE.read_text(encoding="utf-8")
    mutated = source.replace("check.output", "check.command")
    assert mutated != source
    assert attributes_read(mutated, {"command"}) != []


def test_the_allow_guard_counts_a_second_allow() -> None:
    source = GATED_FILE.read_text(encoding="utf-8")
    mutated = source + "\nx = PermissionDecision.ALLOW\n"
    assert allow_mentions(mutated) == 2
