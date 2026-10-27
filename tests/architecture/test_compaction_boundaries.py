"""Architecture guard of the automatic compaction (HU-02-03 / T010).

Beyond the purity that ``test_context_boundaries.py`` already checks for ``core/context/``:

* the compactor never catches ``BaseException`` or ``CancelledError`` (a cancellation reaches the
  loop untouched);
* the one summary call goes out without tools;
* between saving the summary and replacing the view in memory there is no ``await``, so the two
  change together;
* ``cut.py`` is total: it has no ``raise``;
* nothing in ``core/context/`` imports the loop, the adapters, the CLI, the permissions or the
  criteria (the compaction touches neither, FR-014);
* the SQLite archive uses the connection of the session store, never one of its own, does not
  import the loop and does not define the ``SessionStore`` port.

Each rule is proved on the real files and on a mutated copy that breaks it. The detectors of the
other guards are reused, not copied.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_approvals_boundaries import catches_cancellation, imported_modules

ROOT = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
CONTEXT_DIR = ROOT / "core" / "context"
COMPACTOR = CONTEXT_DIR / "compactor.py"
CUT = CONTEXT_DIR / "cut.py"
ARCHIVE = ROOT / "adapters" / "storage" / "compaction_archive.py"

FORBIDDEN_FOR_CONTEXT = (
    "harness_agent.core.loop",
    "harness_agent.core.permissions",
    "harness_agent.core.tasks",
    "harness_agent.core.verification",
    "harness_agent.adapters",
    "harness_agent.cli",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- detectors ---------------------------------------------------------------------------------


def complete_calls(source: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "complete"
    ]


def calls_with_tools(source: str) -> list[int]:
    """Lines of ``complete`` calls that pass anything but the messages."""
    return [c.lineno for c in complete_calls(source) if len(c.args) != 1 or c.keywords]


def awaits_between_commit_and_replacement(source: str) -> list[int]:
    """Lines of an ``await`` from the call of ``commit_compaction`` up to the view replacement."""
    tree = ast.parse(source)
    commit_start = commit_end = replacement = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign | ast.Expr):
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "commit_compaction"
                ):
                    commit_start, commit_end = node.lineno, node.end_lineno
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "history"
                    and isinstance(target.slice, ast.Slice)
                ):
                    replacement = node.lineno
    assert commit_start is not None and commit_end is not None, "no commit_compaction call found"
    assert replacement is not None, "no replacement of the view found"
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Await) and commit_start <= node.lineno < replacement
    ]


def raises(source: str) -> list[int]:
    return [n.lineno for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Raise)]


def forbidden_context_imports(source: str) -> list[str]:
    found = [
        module
        for module in imported_modules(source)
        if any(module == p or module.startswith(p + ".") for p in FORBIDDEN_FOR_CONTEXT)
    ]
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and any(a.name == "TaskCriteria" for a in node.names):
            found.append("TaskCriteria")
    return found


def own_connections(source: str) -> list[int]:
    """Lines that open a SQLite connection (``sqlite3.connect`` or ``connect`` imported from it)."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "connect"
        ):
            lines.append(node.lineno)
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "sqlite3"
            and any(a.name == "connect" for a in node.names)
        ):
            lines.append(node.lineno)
    return lines


def defines_the_port(source: str) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef):
            bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
            if node.name == "SessionStore" or "SessionStore" in bases:
                lines.append(node.lineno)
    return lines


def mutate(source: str, anchor: str, replacement: str) -> str:
    assert source.count(anchor) >= 1, f"anchor not found: {anchor!r}"
    return source.replace(anchor, replacement, 1)


# --- the real files ----------------------------------------------------------------------------


def test_the_compactor_never_catches_cancellation() -> None:
    assert catches_cancellation(read(COMPACTOR)) == []


def test_the_summary_call_has_no_tools_and_is_the_only_one() -> None:
    calls = []
    for path in sorted(CONTEXT_DIR.glob("*.py")):
        source = read(path)
        assert calls_with_tools(source) == [], path.name
        calls.extend(complete_calls(source))
    assert len(calls) == 1


def test_there_is_no_await_between_the_commit_and_the_replacement_of_the_view() -> None:
    assert awaits_between_commit_and_replacement(read(COMPACTOR)) == []


def test_the_cut_never_raises() -> None:
    assert raises(read(CUT)) == []


def test_the_context_package_does_not_reach_the_loop_adapters_cli_permissions_or_criteria() -> None:
    violations = {
        path.name: forbidden_context_imports(read(path))
        for path in sorted(CONTEXT_DIR.glob("*.py"))
    }
    assert {name: found for name, found in violations.items() if found} == {}


def test_the_archive_uses_the_connection_of_the_store() -> None:
    source = read(ARCHIVE)
    assert own_connections(source) == []
    assert "harness_agent.core.loop" not in imported_modules(source)
    assert defines_the_port(source) == []
    assert ".connection()" in source


# --- the mutations: each rule fails on a copy that breaks it -----------------------------------


CATCH = "        except Exception:" + chr(10)
CATCHING = {
    "except BaseException": "        except BaseException:" + chr(10),
    "bare except": "        except:" + chr(10),
    "except CancelledError": "        except asyncio.CancelledError:" + chr(10),
}


@pytest.mark.parametrize("name", list(CATCHING))
def test_a_compactor_that_catches_cancellation_is_flagged(name: str) -> None:
    mutated = mutate(read(COMPACTOR), CATCH, CATCHING[name])

    assert catches_cancellation(mutated) != []


def test_a_summary_call_with_tools_is_flagged() -> None:
    source = read(COMPACTOR)

    assert (
        calls_with_tools(
            mutate(
                source,
                "self._provider.complete(request)",
                "self._provider.complete(request, tools)",
            )
        )
        != []
    )
    assert (
        calls_with_tools(
            mutate(
                source,
                "self._provider.complete(request)",
                "self._provider.complete(request, tools=None)",
            )
        )
        != []
    )


def test_an_await_between_the_commit_and_the_replacement_is_flagged() -> None:
    source = read(COMPACTOR)
    anchor = "        # No await from here on"

    inserted = mutate(source, anchor, "        await self._provider.complete(request)\n" + anchor)
    inside = mutate(
        source,
        "        if receipt is None:\n",
        "        await asyncio.sleep(0)\n        if receipt is None:\n",
    )

    assert awaits_between_commit_and_replacement(inserted) != []
    assert awaits_between_commit_and_replacement(inside) != []
    # An await before the commit (the summary call itself) is where it belongs.
    assert awaits_between_commit_and_replacement(source) == []


def test_a_cut_that_raises_is_flagged() -> None:
    source = read(CUT)

    assert raises(source + "\n\ndef broken() -> None:\n    raise ValueError\n") != []


@pytest.mark.parametrize(
    "line",
    [
        "from harness_agent.core.loop import AgentLoop\n",
        "from harness_agent.core.permissions import PermissionRules\n",
        "from harness_agent.core.tasks import TaskDefinition\n",
        "from harness_agent.core.verification import CriteriaVerifier\n",
        "from harness_agent.adapters.storage import SqliteSessionStore\n",
        "from harness_agent.cli import run_cli\n",
        "from harness_agent.core.interfaces import TaskCriteria\n",
    ],
    ids=["loop", "permissions", "tasks", "verification", "adapters", "cli", "TaskCriteria"],
)
def test_the_forbidden_imports_of_the_context_are_flagged(line: str) -> None:
    assert forbidden_context_imports(line + read(COMPACTOR)) != []


def test_an_archive_that_opens_its_own_connection_is_flagged() -> None:
    source = read(ARCHIVE)

    assert own_connections(source + "\n\ndef x() -> None:\n    sqlite3.connect('x')\n") != []
    assert own_connections("from sqlite3 import connect\n" + source) != []


def test_an_archive_that_defines_the_port_or_imports_the_loop_is_flagged() -> None:
    source = read(ARCHIVE)

    assert defines_the_port(source + "\n\nclass SessionStore:\n    pass\n") != []
    assert defines_the_port(source + "\n\nclass Mine(SessionStore):\n    pass\n") != []
    assert "harness_agent.core.loop" in imported_modules(
        "from harness_agent.core.loop import AgentLoop\n" + source
    )
