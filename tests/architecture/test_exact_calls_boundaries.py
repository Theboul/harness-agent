"""Architecture test of the exact-call rule (HU-11-03 / T003).

``core/permissions/exact_calls.py`` adds a second way to ``ALLOW`` that does not go through
``AuthorizedArea.contains`` (the guard of ``policy.py`` does not cover it), so it gets its own:

* the module imports only the standard library and ``harness_agent.core``, does no I/O, reads no
  file nor environment and does not use the terminal (detectors reused, not copied);
* every ``PermissionDecision.ALLOW`` is in the body of ``if self._matches(<call>) is True`` and,
  in the same function, after ``if <decision> is not PermissionDecision.ASK: return <decision>``:
  it can only turn an ``ASK`` into an ``ALLOW`` (a ``DENY`` of the wrapped policy is kept);
* the module does not name the shell (``"shell"``, ``"command"``, ``"timeout_seconds"``): the
  composition root gives it the names of the tool;
* no method other than ``__init__`` stores state.

The detectors have a self-test with synthetic fragments and a mutation test on a copy of the
module in ``tmp_path``: the real code is never edited.
"""

from __future__ import annotations

import ast
import hashlib
import shutil
from pathlib import Path

import pytest

from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_permissions_boundaries import stateful_methods
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

MODULE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "harness_agent"
    / "core"
    / "permissions"
    / "exact_calls.py"
)
PACKAGE = "harness_agent.core.permissions"
SHELL_NAMES = {"shell", "command", "timeout_seconds"}


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _is_matches_true(test: ast.expr) -> bool:
    """``self._matches(<name>) is True``."""
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Is)
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is True
    ):
        return False
    call = test.left
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "self"
        and call.func.attr == "_matches"
        and len(call.args) == 1
        and isinstance(call.args[0], ast.Name)
        and not call.keywords
    )


def _is_keep_unless_ask(statement: ast.stmt) -> bool:
    """``if <x> is not PermissionDecision.ASK: return <x>``."""
    if not isinstance(statement, ast.If) or statement.orelse:
        return False
    test = statement.test
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and isinstance(test.left, ast.Name)
        and isinstance(test.comparators[0], ast.Attribute)
        and test.comparators[0].attr == "ASK"
        and isinstance(test.comparators[0].value, ast.Name)
        and test.comparators[0].value.id == "PermissionDecision"
    ):
        return False
    body = statement.body
    return (
        len(body) == 1
        and isinstance(body[0], ast.Return)
        and isinstance(body[0].value, ast.Name)
        and body[0].value.id == test.left.id
    )


def _is_allow(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "ALLOW"
        and isinstance(node.value, ast.Name)
        and node.value.id == "PermissionDecision"
    ) or (isinstance(node, ast.Constant) and node.value in ("allow", "ALLOW"))


def unguarded_allows(source: str) -> list[str]:
    """Every ALLOW that is not guarded by the exact match after keeping a non-ASK decision."""
    tree = ast.parse(source)
    parents = _parents(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if not _is_allow(node):
            continue
        guard: ast.If | None = None
        child, ancestor = node, parents.get(node)
        while ancestor is not None:
            if isinstance(ancestor, ast.If) and child in ancestor.body:
                if _is_matches_true(ancestor.test):
                    guard = ancestor
                    break
            child, ancestor = ancestor, parents.get(ancestor)
        line = getattr(node, "lineno", 0)
        if guard is None:
            found.append(f"ALLOW at line {line} is not guarded by self._matches(call) is True")
            continue
        block = parents.get(guard)
        siblings: list[ast.stmt] = []
        for field in ("body", "orelse", "finalbody"):
            statements = getattr(block, field, None)
            if isinstance(statements, list) and guard in statements:
                siblings = statements[: statements.index(guard)]
        if not any(_is_keep_unless_ask(statement) for statement in siblings):
            found.append(f"ALLOW at line {line} does not come after keeping a non-ASK decision")
    return found


def shell_names(source: str) -> list[str]:
    """String constants that name the shell tool or its arguments."""
    return [
        f"{node.value!r} at line {node.lineno}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and node.value in SHELL_NAMES
    ]


def scan(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    name = path.name
    violations: list[str] = []
    violations.extend(f"{name}: {m}" for m in forbidden_imports(source))
    violations.extend(f"{name}: {m}" for m in io_stdlib_imports(source))
    violations.extend(f"{name}: {m}" for m in find_config_reads(source, name, PACKAGE))
    violations.extend(f"{name}: {m}" for m in terminal_uses(source))
    violations.extend(f"{name}: {m}" for m in unguarded_allows(source))
    violations.extend(f"{name}: names the shell: {m}" for m in shell_names(source))
    violations.extend(f"{name}: {m}" for m in stateful_methods(source))
    return violations


GUARDED = """\
def evaluate(self, call):
    decision = self._inner.evaluate(call)
    if decision is not PermissionDecision.ASK:
        return decision
    if self._matches(call) is True:
        return PermissionDecision.ALLOW
    return PermissionDecision.ASK
"""
UNGUARDED = {
    "a bare allow": "def f(self):\n    return PermissionDecision.ALLOW\n",
    "an allow by value": "def f(self):\n    return PermissionDecision('allow')\n",
    "an allow without keeping the decision first": (
        "def f(self, call):\n"
        "    if self._matches(call) is True:\n"
        "        return PermissionDecision.ALLOW\n"
    ),
    "an allow when the decision is kept after the match": (
        "def f(self, call, d):\n"
        "    if self._matches(call) is True:\n"
        "        return PermissionDecision.ALLOW\n"
        "    if d is not PermissionDecision.ASK:\n"
        "        return d\n"
    ),
    "an allow that keeps only a deny": (
        "def f(self, call, d):\n"
        "    if d is not PermissionDecision.DENY:\n"
        "        return d\n"
        "    if self._matches(call) is True:\n"
        "        return PermissionDecision.ALLOW\n"
    ),
    "an allow that returns another value when not asked": (
        "def f(self, call, d):\n"
        "    if d is not PermissionDecision.ASK:\n"
        "        return PermissionDecision.ALLOW\n"
        "    if self._matches(call) is True:\n"
        "        return PermissionDecision.ALLOW\n"
    ),
    "an allow with a match that is not compared with True": (
        "def f(self, call, d):\n"
        "    if d is not PermissionDecision.ASK:\n"
        "        return d\n"
        "    if self._matches(call):\n"
        "        return PermissionDecision.ALLOW\n"
    ),
    "an allow in the else branch": (
        "def f(self, call, d):\n"
        "    if d is not PermissionDecision.ASK:\n"
        "        return d\n"
        "    if self._matches(call) is True:\n"
        "        return PermissionDecision.ASK\n"
        "    else:\n"
        "        return PermissionDecision.ALLOW\n"
    ),
    "an allow after another check": (
        "def f(self, call, d):\n"
        "    if d is not PermissionDecision.ASK:\n"
        "        return d\n"
        "    if call.name:\n"
        "        return PermissionDecision.ALLOW\n"
    ),
}


class TestAutopruebaDeLosDetectores:
    def test_the_guarded_form_is_accepted(self) -> None:
        assert unguarded_allows(GUARDED) == []

    @pytest.mark.parametrize("label", sorted(UNGUARDED))
    def test_an_unguarded_allow_is_detected(self, label: str) -> None:
        assert unguarded_allows(UNGUARDED[label]), label

    @pytest.mark.parametrize("name", sorted(SHELL_NAMES))
    def test_a_name_of_the_shell_is_detected(self, name: str) -> None:
        assert shell_names(f"TOOL = {name!r}\n")

    def test_other_strings_are_not_names_of_the_shell(self) -> None:
        assert shell_names("TEXT = 'commands'\nOTHER = 'Shell'\n") == []


class TestElModuloReal:
    def test_it_respects_every_rule(self) -> None:
        violations = scan(MODULE)

        assert violations == [], "exact_calls.py rompe una regla:\n" + "\n".join(violations)

    def test_it_has_exactly_one_allow_of_its_own(self) -> None:
        source = MODULE.read_text(encoding="utf-8")

        assert sum(1 for node in ast.walk(ast.parse(source)) if _is_allow(node)) == 1


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestMutacionSobreUnaCopia:
    def test_the_detectors_fail_on_a_copy_that_allows_more(self, tmp_path: Path) -> None:
        before = _fingerprint(MODULE)
        copy = tmp_path / "exact_calls.py"
        shutil.copyfile(MODULE, copy)
        assert scan(copy) == []
        with copy.open("a", encoding="utf-8") as handle:
            handle.write(
                "\n\ndef extra(call: ToolCall) -> PermissionDecision:\n"
                "    if call.name == 'shell':\n"
                "        return PermissionDecision.ALLOW\n"
                "    return PermissionDecision.ASK\n"
            )

        violations = scan(copy)

        assert any("is not guarded" in message for message in violations)
        assert any("names the shell" in message for message in violations)
        assert _fingerprint(MODULE) == before
