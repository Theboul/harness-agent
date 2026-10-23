"""Architecture test of the permission policy (HU-05-01 / T006).

* ``core/permissions/`` only imports the standard library and ``harness_agent.core`` (never
  ``config``, ``cli``, ``adapters``, ``observability``), reads no file nor environment and does
  not use the terminal. The detectors of ``test_core_reads_no_config`` and
  ``test_core_no_terminal`` and the import check of ``test_loop_boundaries`` are reused, not copied.
* Every path of ``policy.py`` that returns ``PermissionDecision.ALLOW`` goes through
  ``AuthorizedArea.contains`` with the path of the call, only when it answers exactly ``True``:
  there are two rules to allow (write and read, both bounded to the area) and no allow without
  that condition. The count of rules is not asserted; what is asserted is that none escapes it.
* The policy is stateless and only receives the call; ``PermissionRules`` has no field to allow.

The detectors have a self-test with synthetic fragments and a mutation test on a copy of the
package in ``tmp_path``: the real code is never edited.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import shutil
from pathlib import Path

import pytest

from harness_agent.core.permissions import DefaultPermissionPolicy, PermissionRules
from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core" / "permissions"
POLICY_FILE = PACKAGE_DIR / "policy.py"
PACKAGE = "harness_agent.core.permissions"


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _is_exact_true_check(test: ast.expr) -> bool:
    """``<something>.contains(<one name>) is True``."""
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
        and call.func.attr == "contains"
        and len(call.args) == 1
        and isinstance(call.args[0], ast.Name)
        and not call.keywords
    )


def unguarded_allows(source: str) -> list[str]:
    """Every ALLOW that is not in the body of an ``if area.contains(path) is True``."""
    tree = ast.parse(source)
    parents = _parents(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        is_allow = (
            isinstance(node, ast.Attribute)
            and node.attr == "ALLOW"
            and isinstance(node.value, ast.Name)
            and node.value.id == "PermissionDecision"
        ) or (isinstance(node, ast.Constant) and node.value in ("allow", "ALLOW"))
        if not is_allow:
            continue
        child, ancestor, guarded = node, parents.get(node), False
        while ancestor is not None:
            if isinstance(ancestor, ast.If) and child in ancestor.body:
                if _is_exact_true_check(ancestor.test):
                    guarded = True
                    break
            child, ancestor = ancestor, parents.get(ancestor)
        if not guarded:
            found.append(f"ALLOW at line {getattr(node, 'lineno', 0)} is not guarded by contains")
    return found


def stateful_methods(source: str) -> list[str]:
    """Methods other than ``__init__`` that assign an attribute of ``self``."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef) or node.name == "__init__":
            continue
        for inner in ast.walk(node):
            targets: list[ast.expr] = []
            if isinstance(inner, ast.Assign):
                targets = list(inner.targets)
            elif isinstance(inner, ast.AugAssign | ast.AnnAssign):
                targets = [inner.target]
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    found.append(f"{node.name} assigns self.{target.attr}")
    return found


def scan_package(directory: Path) -> list[str]:
    files = sorted(directory.rglob("*.py"))
    assert files, f"No Python files found under {directory}"
    violations: list[str] = []
    for file_path in files:
        source = file_path.read_text(encoding="utf-8")
        name = file_path.name
        violations.extend(f"{name}: {m}" for m in forbidden_imports(source))
        violations.extend(f"{name}: {m}" for m in find_config_reads(source, name, PACKAGE))
        violations.extend(f"{name}: {m}" for m in terminal_uses(source))
        if name == "policy.py":
            violations.extend(f"{name}: {m}" for m in unguarded_allows(source))
            violations.extend(f"{name}: {m}" for m in stateful_methods(source))
    return violations


def fingerprint(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*.py"))
    }


GUARDED = """\
def f(self, path):
    if self._area.contains(path) is True:
        return PermissionDecision.ALLOW
    return PermissionDecision.ASK
"""
GUARDED_NESTED = """\
def f(self, path):
    if path:
        if self._area.contains(path) is True:
            if path != "x":
                return PermissionDecision.ALLOW
    return PermissionDecision.ASK
"""
UNGUARDED = {
    "a bare allow": "def f(self):\n    return PermissionDecision.ALLOW\n",
    "an allow after an unrelated condition": (
        "def f(self, path):\n    if path:\n        return PermissionDecision.ALLOW\n"
    ),
    "an allow in the else branch": (
        "def f(self, path):\n"
        "    if self._area.contains(path) is True:\n"
        "        return PermissionDecision.ASK\n"
        "    else:\n"
        "        return PermissionDecision.ALLOW\n"
    ),
    "a contains that is not compared with True": (
        "def f(self, path):\n"
        "    if self._area.contains(path):\n"
        "        return PermissionDecision.ALLOW\n"
    ),
    "a contains with a computed argument": (
        "def f(self, path):\n"
        "    if self._area.contains(path.strip()) is True:\n"
        "        return PermissionDecision.ALLOW\n"
    ),
    "an allow that is not exactly true": (
        "def f(self, path):\n"
        "    if self._area.contains(path) is not False:\n"
        "        return PermissionDecision.ALLOW\n"
    ),
    "an allow by value": 'def f(self):\n    return PermissionDecision("allow")\n',
    "an allow by name": 'def f(self):\n    return PermissionDecision["ALLOW"]\n',
    "an allow in a conditional expression": (
        "def f(self, p):\n    return PermissionDecision.ALLOW if p else PermissionDecision.ASK\n"
    ),
}


class TestAutopruebaDelDetector:
    def test_an_allow_in_the_guarded_branch_is_accepted(self) -> None:
        assert unguarded_allows(GUARDED) == []
        assert unguarded_allows(GUARDED_NESTED) == []

    @pytest.mark.parametrize("label", sorted(UNGUARDED))
    def test_an_allow_outside_the_guarded_branch_is_detected(self, label: str) -> None:
        assert unguarded_allows(UNGUARDED[label]), label

    def test_the_rules_may_be_more_than_one_while_each_one_is_guarded(self) -> None:
        two_rules = GUARDED + GUARDED.replace("def f", "def g")

        assert unguarded_allows(two_rules) == []

    def test_a_method_that_assigns_self_is_detected_except_the_constructor(self) -> None:
        assert stateful_methods("class C:\n    def __init__(self):\n        self.a = 1\n") == []
        assert stateful_methods("class C:\n    def f(self):\n        self.a = 1\n")
        assert stateful_methods("class C:\n    def f(self):\n        self.a += 1\n")
        assert stateful_methods("class C:\n    def f(self):\n        self.a: int = 1\n")
        assert stateful_methods("class C:\n    def f(self):\n        a = 1\n") == []


class TestPaqueteReal:
    def test_the_package_respects_the_frontiers_and_every_allow_is_guarded(self) -> None:
        assert len(list(PACKAGE_DIR.rglob("*.py"))) >= 3

        violations = scan_package(PACKAGE_DIR)

        assert violations == [], "core/permissions rompe una regla:\n" + "\n".join(violations)

    def test_the_policy_has_at_least_one_allow_and_all_of_them_go_through_contains(self) -> None:
        source = POLICY_FILE.read_text(encoding="utf-8")

        assert "PermissionDecision.ALLOW" in source  # the rules to allow exist
        assert unguarded_allows(source) == []

    def test_evaluate_only_receives_the_call(self) -> None:
        parameters = list(inspect.signature(DefaultPermissionPolicy.evaluate).parameters)

        assert parameters == ["self", "call"]

    def test_the_policy_keeps_no_state_between_calls(self) -> None:
        assert stateful_methods(POLICY_FILE.read_text(encoding="utf-8")) == []

    def test_the_rules_have_no_field_to_allow(self) -> None:
        names = {field.name for field in dataclasses.fields(PermissionRules)}

        assert names == {"deny", "ask"}
        assert not any("allow" in name.lower() for name in names)


class TestMutacionSobreUnaCopia:
    def test_the_detectors_fail_on_a_copy_with_an_unguarded_allow_and_an_environment_read(
        self, tmp_path: Path
    ) -> None:
        before = fingerprint(PACKAGE_DIR)
        copy = tmp_path / "permissions"
        shutil.copytree(PACKAGE_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
        assert scan_package(copy) == []
        with (copy / "policy.py").open("a", encoding="utf-8") as handle:
            handle.write(
                "\nimport os\n\n\ndef extra() -> PermissionDecision:\n"
                "    if os.environ.get('X'):\n"
                "        return PermissionDecision.ALLOW\n"
                "    return PermissionDecision.ASK\n"
            )

        violations = scan_package(copy)

        assert any("is not guarded by contains" in message for message in violations)
        assert any("os.environ" in message for message in violations)
        assert fingerprint(PACKAGE_DIR) == before
