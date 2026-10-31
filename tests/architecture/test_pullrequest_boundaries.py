"""Architecture guards of the Pull Request step (HU-11-06).

* ``core/pullrequest/`` imports only the standard library and ``harness_agent.core``, does no I/O
  (git, ``gh`` and the terminal are ``Protocol`` ports), reads no configuration or environment,
  does not use the terminal and does not import the agent loop.
* The flow never catches cancellation, and **nothing goes out without a confirmation**: in
  ``on_committed`` the push comes after ``confirm_push`` and the creation after ``confirm_create``;
  no other module of the package calls ``.push(`` or ``.create(``.
* The adapter runs no shell and its strings name no dangerous git option (no force, reset...).
* **Only ``bootstrap.py`` builds the pieces**: no other module of ``src/`` names
  ``GitHubPullRequests``, ``PullRequestFlow`` or ``ConsolePullRequestPrompter`` apart from their
  own packages and the public exports.

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
from tests.architecture.test_review_boundaries import names_any, uses_shell
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
PACKAGE_DIR = SRC / "core" / "pullrequest"
FLOW_FILE = PACKAGE_DIR / "flow.py"
ADAPTER_FILE = SRC / "adapters" / "system" / "github_pull_requests.py"
PACKAGE = "harness_agent.core.pullrequest"
OWN = {Path("core") / "pullrequest", Path("adapters") / "system", Path("cli")}
EXPORTS = {
    Path("core") / "__init__.py",
    Path("adapters") / "system" / "__init__.py",
    Path("cli") / "__init__.py",
}
NAMES = {"GitHubPullRequests", "PullRequestFlow", "ConsolePullRequestPrompter"}
OUTGOING = {"push": "confirm_push", "create": "confirm_create"}
FORBIDDEN_WORDS = frozenset(
    {"--force", "-f", "--force-with-lease", "--mirror", "--delete", "reset", "clean", "checkout"}
    | {"restore", "stash", "rebase", "merge", "pull", "fetch", "tag", "config", "remote"}
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


def outgoing_calls(source: str) -> dict[str, list[int]]:
    """Lines of the calls to ``.push(`` and ``.create(`` (the outgoing actions)."""
    found: dict[str, list[int]] = {name: [] for name in OUTGOING}
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in OUTGOING
        ):
            found[node.func.attr].append(node.lineno)
    return found


def unconfirmed_outgoing(source: str) -> list[str]:
    """Problems: an outgoing call that does not come after its confirmation in ``on_committed``."""
    tree = ast.parse(source)
    problems: list[str] = []
    entry = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "on_committed"
        ),
        None,
    )
    if entry is None:
        return ["no on_committed"]
    asked = {
        attr: [
            call.lineno
            for call in ast.walk(entry)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == confirmation
        ]
        for attr, confirmation in OUTGOING.items()
    }
    inside = outgoing_calls(source)
    for attr, lines in inside.items():
        if len(lines) != 1:
            problems.append(f"{attr} called {len(lines)} times")
            continue
        if not asked[attr] or min(asked[attr]) > lines[0]:
            problems.append(f"{attr} not preceded by {OUTGOING[attr]}")
    return problems


def forbidden_strings(source: str) -> list[str]:
    return sorted(
        {
            node.value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in FORBIDDEN_WORDS
        }
    )


# --- the real code ---------------------------------------------------------------------------


def test_the_pullrequest_package_is_pure() -> None:
    assert scan_package(PACKAGE_DIR) == []


def test_the_flow_never_catches_cancellation() -> None:
    assert catches_cancellation(FLOW_FILE.read_text(encoding="utf-8")) == []


def test_nothing_goes_out_without_its_confirmation() -> None:
    assert unconfirmed_outgoing(FLOW_FILE.read_text(encoding="utf-8")) == []


def test_only_the_flow_calls_the_outgoing_actions() -> None:
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        if path == FLOW_FILE:
            continue
        calls = outgoing_calls(path.read_text(encoding="utf-8"))
        assert not any(calls.values()), path.name


def test_the_package_never_names_the_marking_of_passes() -> None:
    for path in sorted(PACKAGE_DIR.rglob("*.py")):
        assert "mark_passes" not in path.read_text(encoding="utf-8"), path.name


def test_only_bootstrap_builds_the_pull_request_pieces() -> None:
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


def test_the_adapter_uses_no_shell_and_no_dangerous_option() -> None:
    source = ADAPTER_FILE.read_text(encoding="utf-8")
    assert not uses_shell(source)
    assert forbidden_strings(source) == []


# --- self-tests of the detectors ---------------------------------------------------------------

CONFIRMED = (
    "class F:\n"
    "    async def on_committed(self, approved):\n"
    "        if not await self._ask(self._prompter.confirm_push(b)):\n"
    "            return\n"
    "        await self._host.push(b)\n"
    "        if not await self._ask(self._prompter.confirm_create(d)):\n"
    "            return\n"
    "        await self._host.create(d)\n"
)


def test_confirmed_outgoing_calls_are_accepted() -> None:
    assert unconfirmed_outgoing(CONFIRMED) == []


@pytest.mark.parametrize(
    "source",
    [
        CONFIRMED.replace("self._prompter.confirm_push(b)", "True"),
        CONFIRMED.replace("self._prompter.confirm_create(d)", "True"),
        CONFIRMED + "        await self._host.push(b)\n",
        CONFIRMED.replace("on_committed", "other"),
        "class F:\n    async def on_committed(self):\n        await self._host.push(b)\n",
    ],
    ids=["no-push-question", "no-create-question", "second-push", "no-entry", "bare-push"],
)
def test_unconfirmed_outgoing_calls_are_flagged(source: str) -> None:
    assert unconfirmed_outgoing(source) != []


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


def test_the_detectors_see_names_and_words() -> None:
    assert names_any("from x import PullRequestFlow\n", NAMES)
    assert names_any("y = GitHubPullRequests(a)\n", NAMES)
    assert not names_any("y = Other(a)\n", NAMES)
    assert forbidden_strings("x = ['push', '--force']\n") == ["--force"]
    assert forbidden_strings("x = ['push', '-u', 'origin']\n") == []
    assert outgoing_calls("a.push(1)\nb.create(2)\nc.other(3)\n") == {"push": [1], "create": [2]}
