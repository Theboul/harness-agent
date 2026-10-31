"""Architecture guards of the progress file of a ticket (HU-11-08.1).

* ``core/progress/`` imports only the standard library and ``harness_agent.core``, does no I/O
  (not even the standard modules that do it: the destination is injected), reads no configuration
  or environment and does not use the terminal. It does not import the agent loop.
* The recorder never catches cancellation: it catches ``Exception`` only, so ``CancelledError``
  and ``KeyboardInterrupt`` go through.
* **Only ``bootstrap.py`` builds the file destination**: no other module of ``src/`` names
  ``ProgressFile`` apart from its own package.
* The progress files never carry a verification command: ``core/progress/`` does not read the
  ``command`` or ``evidence`` of a criterion except to decide the state.

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
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
PROGRESS_DIR = SRC / "core" / "progress"
RECORDER_FILE = PROGRESS_DIR / "recorder.py"
RENDER_FILE = PROGRESS_DIR / "render.py"
PACKAGE = "harness_agent.core.progress"
OWN_PACKAGES = (Path("core") / "progress", Path("adapters") / "storage")


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


def names_progress_file(source: str) -> bool:
    """Whether the source uses the name ``ProgressFile`` (an import, a call or an annotation)."""
    return any(
        (isinstance(node, ast.Name) and node.id == "ProgressFile")
        or (isinstance(node, ast.alias) and node.name == "ProgressFile")
        for node in ast.walk(ast.parse(source))
    )


def attributes_read(source: str, names: set[str]) -> list[int]:
    """Lines where one of ``names`` is read as an attribute (``item.command``)."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute) and node.attr in names
    ]


# --- the real code ---------------------------------------------------------------------------


def test_the_progress_package_is_pure() -> None:
    assert scan_package(PROGRESS_DIR) == []


def test_the_recorder_never_catches_cancellation() -> None:
    assert catches_cancellation(RECORDER_FILE.read_text(encoding="utf-8")) == []


def test_only_bootstrap_and_the_storage_package_name_the_file_destination() -> None:
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC)
        if relative == Path("bootstrap.py") or any(
            part in relative.parents for part in OWN_PACKAGES
        ):
            continue
        if names_progress_file(path.read_text(encoding="utf-8")):
            offenders.append(relative.as_posix())
    assert offenders == []


def test_the_progress_text_never_reads_the_command_or_the_evidence() -> None:
    for path in (RECORDER_FILE, RENDER_FILE):
        reads = attributes_read(path.read_text(encoding="utf-8"), {"evidence", "expectation"})
        assert reads == [], path.name
    # the only use of ``command`` is to tell a semantic criterion from an objective one
    uses = attributes_read(RECORDER_FILE.read_text(encoding="utf-8"), {"command"})
    assert len(uses) == 1


# --- self-tests of the detectors ---------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "import pathlib\n",
        "import sqlite3\n",
        "from harness_agent.adapters import x\n",
        "from harness_agent.core.loop import AgentLoop\n",
        "import os\nos.environ['X']\n",
        "print('hola')\n",
    ],
    ids=["pathlib", "sqlite", "adapters", "loop", "entorno", "terminal"],
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
        ("from x import ProgressFile\n", True),
        ("x = ProgressFile(p)\n", True),
        ("x = Other(p)\n", False),
    ],
)
def test_the_destination_detector(source: str, expected: bool) -> None:
    assert names_progress_file(source) is expected


def test_the_cancellation_guard_catches_a_mutation_of_the_recorder() -> None:
    source = RECORDER_FILE.read_text(encoding="utf-8")
    mutated = source.replace("except Exception:", "except BaseException:")
    assert mutated != source
    assert catches_cancellation(mutated) != []


def test_the_evidence_guard_catches_a_mutation_of_the_recorder() -> None:
    source = RECORDER_FILE.read_text(encoding="utf-8")
    mutated = source.replace("item.description", "item.evidence")
    assert mutated != source
    assert attributes_read(mutated, {"evidence"}) != []
