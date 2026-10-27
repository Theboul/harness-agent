"""Architecture guards of the automatic verification of criteria (HU-11-04.1).

* ``core/verification/`` imports only the standard library and ``harness_agent.core``, does no I/O,
  reads no configuration or environment and does not use the terminal. No module of it imports the
  agent loop (the existing guard of the loop forbids it), and the runner has no number of rounds:
  the only bound is the one of the session limits.
* **One writer of passes**: in the whole of ``src/`` the only call to ``mark_passes`` is the one of
  ``core/verification/verifier.py`` (there are only definitions elsewhere), and no tool module
  names it, so no registered tool can expose it.
* The verifier never catches cancellation, and a permission is only granted by comparing the
  decision with ``is``.

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
VERIFICATION_DIR = SRC / "core" / "verification"
VERIFIER_FILE = VERIFICATION_DIR / "verifier.py"
RUNNER_FILE = VERIFICATION_DIR / "runner.py"
PACKAGE = "harness_agent.core.verification"
TOOL_DIRS = (SRC / "adapters" / "tools", SRC / "core" / "tools")


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


def mark_passes_calls(source: str) -> int:
    """Calls to ``<something>.mark_passes(...)`` (a definition is not a call)."""
    return sum(
        1
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "mark_passes"
    )


def writers(root: Path) -> dict[str, int]:
    """Relative path -> number of calls to ``mark_passes``, for every file that has any."""
    found: dict[str, int] = {}
    for path in sorted(root.rglob("*.py")):
        count = mark_passes_calls(path.read_text(encoding="utf-8"))
        if count:
            found[path.relative_to(root).as_posix()] = count
    return found


def integer_constants(source: str) -> list[int]:
    """Integer literals (not booleans) of the source."""
    return [
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, int)
        and not isinstance(node.value, bool)
    ]


def has_counter(source: str) -> bool:
    """An augmented assignment, or any integer literal: a count of rounds would need one."""
    tree = ast.parse(source)
    return any(isinstance(node, ast.AugAssign) for node in ast.walk(tree)) or bool(
        integer_constants(source)
    )


def allow_without_is(source: str) -> list[int]:
    """Lines where ``PermissionDecision.ALLOW`` is used other than as one side of an ``is``."""
    tree = ast.parse(source)
    in_is: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and all(isinstance(op, ast.Is) for op in node.ops):
            in_is.update(id(part) for part in [node.left, *node.comparators])
    lines: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "ALLOW"
            and isinstance(node.value, ast.Name)
            and node.value.id == "PermissionDecision"
            and id(node) not in in_is
        ):
            lines.append(node.lineno)
    return lines


# --- the real code ---------------------------------------------------------------------------


def test_the_verification_package_is_pure() -> None:
    assert scan_package(VERIFICATION_DIR) == []


def test_the_runner_has_no_counter_of_rounds() -> None:
    assert not has_counter(RUNNER_FILE.read_text(encoding="utf-8"))


def test_only_the_verifier_marks_passes_in_all_of_src() -> None:
    assert writers(SRC) == {"core/verification/verifier.py": 1}


def test_no_tool_module_names_the_marking_of_passes() -> None:
    for directory in TOOL_DIRS:
        for path in sorted(directory.rglob("*.py")):
            assert "mark_passes" not in path.read_text(encoding="utf-8"), path.name


def test_the_verifier_never_catches_cancellation() -> None:
    assert catches_cancellation(VERIFIER_FILE.read_text(encoding="utf-8")) == []


def test_a_permission_is_only_granted_by_comparing_with_is() -> None:
    assert allow_without_is(VERIFIER_FILE.read_text(encoding="utf-8")) == []


# --- self-test of the rules with synthetic fragments ----------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3\n",
        "import subprocess\n",
        "from harness_agent.adapters.tools import make_command_runner\n",
        "from harness_agent.cli import criterion_line\n",
        "from harness_agent.core.loop import TurnResult\n",
        "import os\nos.environ['X']\n",
        "print('hola')\n",
    ],
    ids=["sqlite", "subprocess", "adapters", "cli", "loop", "entorno", "terminal"],
)
def test_the_package_scan_flags_violations(source: str, tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    assert scan_package(tmp_path) != []


def test_the_package_scan_lets_pure_code_through(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(
        "from dataclasses import dataclass\nfrom harness_agent.core.entities import ToolCall\n",
        encoding="utf-8",
    )
    assert scan_package(tmp_path) == []


def test_a_definition_is_not_a_call_of_the_writer() -> None:
    assert mark_passes_calls("class S:\n    def mark_passes(self, a, b):\n        pass\n") == 0
    assert mark_passes_calls("def f(store):\n    store.mark_passes('1', 'e')\n") == 1


def test_a_counter_is_detected() -> None:
    assert has_counter("rounds = 0\nrounds += 1\n")
    assert has_counter("LIMIT = 5\n")
    assert not has_counter("while True:\n    break\n")


def test_an_allow_without_is_is_detected() -> None:
    assert allow_without_is("if d is PermissionDecision.ALLOW:\n    pass\n") == []
    assert allow_without_is("return PermissionDecision.ALLOW\n") == [1]
    assert allow_without_is("if d == PermissionDecision.ALLOW:\n    pass\n") == [1]


# --- mutation: a second writer on a copy makes the guard fail -------------------------------------


def test_a_second_writer_on_a_copy_is_caught(tmp_path: Path) -> None:
    folder = tmp_path / "core" / "verification"
    folder.mkdir(parents=True)
    (folder / "verifier.py").write_text(VERIFIER_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    assert writers(tmp_path) == {"core/verification/verifier.py": 1}

    (tmp_path / "cli.py").write_text(
        "def sneaky(store):\n    store.mark_passes('1', 'dicho por el modelo')\n", encoding="utf-8"
    )

    assert writers(tmp_path) == {"core/verification/verifier.py": 1, "cli.py": 1}


def test_a_swallowed_cancellation_on_a_copy_is_caught() -> None:
    mutated = VERIFIER_FILE.read_text(encoding="utf-8").replace(
        "        except Exception:\n            return None\n        return outcome",
        "        except BaseException:\n            return None\n        return outcome",
        1,
    )

    assert mutated != VERIFIER_FILE.read_text(encoding="utf-8")
    assert catches_cancellation(mutated) != []
