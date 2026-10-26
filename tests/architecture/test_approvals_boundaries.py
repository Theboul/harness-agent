"""Architecture guards of the approval gate (HU-05-03).

* ``core/permissions/approvals.py`` imports only the standard library and ``harness_agent.core``,
  does no I/O, reads no configuration or environment and does not use the terminal (the detectors
  of the other guards are reused, not copied).
* The gate never catches cancellation (``BaseException``, a bare ``except`` or ``CancelledError``):
  a cancelled wait must never become an approval.
* An approval can never override a denial: in ``core/loop.py`` the gate is reachable only through
  ``_ask_approval``, which ``_process_call`` calls only for a verdict marked ``pending_approval``,
  and that mark is set in a single place, the ``ASK`` branch of ``_decide``.

The rules have a self-test with synthetic fragments.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_permissions_boundaries import PACKAGE

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core"
APPROVALS_FILE = CORE_DIR / "permissions" / "approvals.py"
LOOP_FILE = CORE_DIR / "loop.py"
IO_STDLIB = {"sqlite3", "subprocess", "socket", "http", "urllib", "shutil", "tempfile", "os"}


def imported_modules(source: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append(node.module)
    return found


def io_stdlib_imports(source: str) -> list[str]:
    return [m for m in imported_modules(source) if m.split(".")[0] in IO_STDLIB]


def catches_cancellation(source: str) -> list[int]:
    """Lines of handlers that would also catch ``CancelledError`` (a ``BaseException``)."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ExceptHandler):
            continue
        caught = [] if node.type is None else list(ast.walk(node.type))
        names = {n.id for n in caught if isinstance(n, ast.Name)} | {
            n.attr for n in caught if isinstance(n, ast.Attribute)
        }
        if node.type is None or names & {"BaseException", "CancelledError"}:
            lines.append(node.lineno)
    return lines


def _function_of(tree: ast.AST) -> dict[ast.AST, str]:
    owner: dict[ast.AST, str] = {}
    for function in ast.walk(tree):
        if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.walk(function):
                owner.setdefault(child, function.name)
    return owner


def gate_users(source: str) -> set[str]:
    """Names of the functions that touch ``self._approvals``."""
    tree = ast.parse(source)
    owner = _function_of(tree)
    return {
        owner.get(node, "<module>")
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "_approvals"
    }


def callers_of(source: str, method: str) -> set[str]:
    tree = ast.parse(source)
    owner = _function_of(tree)
    return {
        owner.get(node, "<module>")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
    }


def pending_marks(source: str) -> list[str]:
    """Functions that build a verdict with ``pending_approval=True``."""
    tree = ast.parse(source)
    owner = _function_of(tree)
    return [
        owner.get(node, "<module>")
        for node in ast.walk(tree)
        if isinstance(node, ast.keyword)
        and node.arg == "pending_approval"
        and isinstance(node.value, ast.Constant)
        and node.value.value is True
    ]


def guarded_by_pending(source: str, method: str) -> bool:
    """Every call of ``self.<method>`` sits inside ``if verdict.pending_approval:``."""
    tree = ast.parse(source)
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == method
    ]
    for call in calls:
        node: ast.AST | None = call
        while node is not None and not (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Attribute)
            and node.test.attr == "pending_approval"
        ):
            node = parents.get(node)
        if node is None:
            return False
    return bool(calls)


class TestApprovalsModule:
    def test_only_stdlib_and_core_without_io_config_or_terminal(self) -> None:
        source = APPROVALS_FILE.read_text(encoding="utf-8")
        name = APPROVALS_FILE.name

        assert forbidden_imports(source) == []
        assert io_stdlib_imports(source) == []
        assert find_config_reads(source, name, PACKAGE) == []
        assert terminal_uses(source) == []

    def test_it_does_not_depend_on_the_loop_or_the_cli(self) -> None:
        modules = imported_modules(APPROVALS_FILE.read_text(encoding="utf-8"))

        assert not [m for m in modules if m.endswith(".loop") or ".cli" in m]

    def test_it_never_catches_cancellation(self) -> None:
        assert catches_cancellation(APPROVALS_FILE.read_text(encoding="utf-8")) == []

    def test_it_never_decides_allow_on_its_own(self) -> None:
        assert "PermissionDecision" not in APPROVALS_FILE.read_text(encoding="utf-8")


class TestLoopUsesTheGateOnlyForAsk:
    def test_only_the_constructor_the_decision_and_the_approval_step_touch_the_gate(self) -> None:
        users = gate_users(LOOP_FILE.read_text(encoding="utf-8"))

        assert users == {"__init__", "_decide", "_ask_approval"}

    def test_the_approval_step_is_called_only_for_a_pending_verdict(self) -> None:
        source = LOOP_FILE.read_text(encoding="utf-8")

        assert callers_of(source, "_ask_approval") == {"_process_call"}
        assert guarded_by_pending(source, "_ask_approval")

    def test_the_pending_mark_is_set_only_in_the_decision(self) -> None:
        assert pending_marks(LOOP_FILE.read_text(encoding="utf-8")) == ["_decide"]

    def test_the_loop_does_not_catch_cancellation_around_the_wait(self) -> None:
        source = LOOP_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        owner = _function_of(tree)
        lines = [
            n.lineno
            for n in ast.walk(tree)
            if isinstance(n, ast.ExceptHandler) and owner.get(n) in {"_ask_approval", "_decide"}
        ]
        # ``_decide`` catches ``Exception`` from the policy only; ``_ask_approval`` catches nothing.
        assert not [n for n in catches_cancellation(source) if n in lines]


class TestSelfTests:
    @pytest.mark.parametrize(
        "source",
        [
            "try:\n    pass\nexcept BaseException:\n    pass\n",
            "try:\n    pass\nexcept:\n    pass\n",
            "import asyncio\ntry:\n    pass\nexcept asyncio.CancelledError:\n    pass\n",
            "try:\n    pass\nexcept (ValueError, BaseException):\n    pass\n",
        ],
        ids=["base", "bare", "cancelled", "tuple"],
    )
    def test_the_cancellation_detector_flags_each_form(self, source: str) -> None:
        assert catches_cancellation(source)

    def test_the_cancellation_detector_accepts_ordinary_exceptions(self) -> None:
        assert catches_cancellation("try:\n    pass\nexcept Exception:\n    pass\n") == []

    def test_the_detectors_see_a_second_user_of_the_gate_or_an_unguarded_call(self) -> None:
        extra = "class A:\n    def other(self):\n        return self._approvals\n"
        loose = "class A:\n    def go(self):\n        self._ask_approval()\n"
        guarded = (
            "class A:\n    def go(self, v):\n        if v.pending_approval:\n"
            "            self._ask_approval()\n"
        )

        assert gate_users(extra) == {"other"}
        assert not guarded_by_pending(loose, "_ask_approval")
        assert guarded_by_pending(guarded, "_ask_approval")
        assert pending_marks("f(pending_approval=True)\n") == ["<module>"]

    def test_the_io_detector_flags_stdlib_io(self) -> None:
        assert io_stdlib_imports("import subprocess\n")
        assert io_stdlib_imports("import json\n") == []
