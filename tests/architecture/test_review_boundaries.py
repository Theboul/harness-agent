"""Architecture guards of the review of the diff (HU-11-05).

* ``core/review/`` imports only the standard library and ``harness_agent.core``, does no I/O
  (git and the terminal are ``Protocol`` ports), reads no configuration or environment, does not
  use the terminal and does not import the agent loop.
* The runner never catches cancellation, has no counter of rounds (the session limits are the
  only bound) and **commits only on approval**: the only call to ``.commit(`` is inside
  ``_commit``, and the only call to ``_commit`` is inside an ``if`` on ``can_approve``.
* **Only ``bootstrap.py`` builds the pieces**: no other module of ``src/`` names ``GitChanges`` or
  ``ReviewingRunner`` apart from their own packages and the public exports.
* The git adapter never uses a shell and its strings name no git subcommand other than the ones
  of the review (no push, reset, clean, checkout, restore, stash, rebase, merge, pull, fetch,
  branch, tag, config or remote).
* Marking passes stays in one place (``test_verification_boundaries.py``): the review package
  never names ``mark_passes``.

The rules have a self-test with synthetic fragments.
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
REVIEW_DIR = SRC / "core" / "review"
RUNNER_FILE = REVIEW_DIR / "runner.py"
GIT_FILE = SRC / "adapters" / "system" / "git_changes.py"
PACKAGE = "harness_agent.core.review"
OWN = {Path("core") / "review", Path("adapters") / "system"}
EXPORTS = {Path("core") / "__init__.py", Path("adapters") / "system" / "__init__.py"}
NAMES = {"GitChanges", "ReviewingRunner"}
FORBIDDEN_GIT_WORDS = frozenset(
    {"push", "reset", "clean", "checkout", "restore", "stash", "rebase"}
    | {"merge", "pull", "fetch", "branch", "tag", "config", "remote", "--force", "-f"}
)


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


def calls_of(source: str, attribute: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
    ]


def commit_outside_approval(source: str) -> list[str]:
    """Problems with how the commit is reached: where ``.commit(`` and ``_commit`` are called."""
    tree = ast.parse(source)
    problems: list[str] = []
    for function in ast.walk(tree):
        if isinstance(function, ast.AsyncFunctionDef | ast.FunctionDef):
            inner = [c for c in calls_of(ast.unparse(function), "commit")]
            if inner and function.name != "_commit":
                problems.append(f"commit called in {function.name}")
    guarded = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and "can_approve" in ast.unparse(node.test):
            guarded += len(calls_of(ast.unparse(ast.Module(node.body, [])), "_commit"))
    total = len(calls_of(source, "_commit"))
    if total != 1 or guarded != 1:
        problems.append(f"_commit called {total} times, {guarded} under can_approve")
    return problems


def has_augmented_assignment(source: str) -> bool:
    return any(isinstance(node, ast.AugAssign) for node in ast.walk(ast.parse(source)))


def uses_shell(source: str) -> bool:
    """A ``shell=`` keyword anywhere, or ``os.system``."""
    tree = ast.parse(source)
    return any(isinstance(n, ast.keyword) and n.arg == "shell" for n in ast.walk(tree)) or any(
        isinstance(n, ast.Attribute) and n.attr == "system" for n in ast.walk(tree)
    )


def forbidden_git_strings(source: str) -> list[str]:
    return sorted(
        {
            node.value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in FORBIDDEN_GIT_WORDS
        }
    )


# --- the real code ---------------------------------------------------------------------------


def test_the_review_package_is_pure() -> None:
    assert scan_package(REVIEW_DIR) == []


def test_the_runner_never_catches_cancellation() -> None:
    assert catches_cancellation(RUNNER_FILE.read_text(encoding="utf-8")) == []


def test_the_runner_has_no_counter_of_rounds() -> None:
    assert not has_augmented_assignment(RUNNER_FILE.read_text(encoding="utf-8"))


def test_the_commit_is_only_reached_on_approval() -> None:
    assert commit_outside_approval(RUNNER_FILE.read_text(encoding="utf-8")) == []


def test_the_review_package_never_names_the_marking_of_passes() -> None:
    for path in sorted(REVIEW_DIR.rglob("*.py")):
        assert "mark_passes" not in path.read_text(encoding="utf-8"), path.name


def test_only_bootstrap_builds_the_git_source_and_the_reviewing_runner() -> None:
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        relative = path.relative_to(SRC)
        if relative == Path("bootstrap.py") or relative in EXPORTS:
            continue
        if any(part in relative.parents for part in OWN):
            continue
        if names_any(path.read_text(encoding="utf-8"), NAMES):
            offenders.append(relative.as_posix())
    assert offenders == []


def test_the_git_adapter_uses_no_shell_and_no_dangerous_subcommand() -> None:
    source = GIT_FILE.read_text(encoding="utf-8")
    assert not uses_shell(source)
    assert forbidden_git_strings(source) == []


# --- self-tests of the detectors ---------------------------------------------------------------

APPROVED = (
    "class R:\n"
    "    async def _commit(self):\n"
    "        await self._source.commit('m')\n"
    "    async def _review(self, view):\n"
    "        if view.can_approve:\n"
    "            await self._commit()\n"
)


def test_a_commit_only_under_approval_is_accepted() -> None:
    assert commit_outside_approval(APPROVED) == []


@pytest.mark.parametrize(
    "source",
    [
        APPROVED.replace("if view.can_approve:", "if True:"),
        APPROVED + "    async def other(self):\n        await self._source.commit('x')\n",
        APPROVED + "    async def other(self):\n        await self._commit()\n",
        APPROVED.replace("            await self._commit()\n", "            pass\n"),
    ],
    ids=["unguarded", "direct-commit", "second-caller", "never-called"],
)
def test_a_commit_outside_approval_is_flagged(source: str) -> None:
    assert commit_outside_approval(source) != []


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


def test_the_detectors_see_names_shell_counters_and_words() -> None:
    assert names_any("from x import GitChanges\n", NAMES)
    assert names_any("y = ReviewingRunner(a)\n", NAMES)
    assert not names_any("y = Other(a)\n", NAMES)
    assert has_augmented_assignment("n += 1\n") and not has_augmented_assignment("n = 1\n")
    assert uses_shell("subprocess.run(a, shell=True)\n") and uses_shell("os.system('x')\n")
    assert not uses_shell("subprocess.run(a, check=False)\n")
    assert forbidden_git_strings("x = ['push', 'add']\n") == ["push"]
    assert forbidden_git_strings("x = ['add', 'commit']\n") == []
