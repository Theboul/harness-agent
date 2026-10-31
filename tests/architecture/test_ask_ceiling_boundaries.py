"""Architecture test of the ask ceiling (HU-08-03).

``core/permissions/ask_ceiling.py`` can only make a decision stricter:

* it imports only the standard library and ``harness_agent.core``, does no I/O, reads no file nor
  environment and does not use the terminal (detectors reused, not copied);
* it never returns or assigns ``PermissionDecision.ALLOW``: the name may only appear in a
  comparison (``decision is PermissionDecision.ALLOW``), so it cannot open a door;
* it does not know any tool (``"shell"``, ``"command"``, ``"mcp"``): the composition root gives it
  the names;
* every ``except`` handler returns ``PermissionDecision.DENY`` (it fails closed);
* no method other than ``__init__`` stores state.

The rules have a self-test on synthetic fragments and a mutation test on a copy of the module.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_permissions_boundaries import stateful_methods
from tests.architecture.test_protected_policy_boundaries import handlers_not_denying
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

MODULE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "harness_agent"
    / "core"
    / "permissions"
    / "ask_ceiling.py"
)
PACKAGE = "harness_agent.core.permissions"
TOOL_NAMES = {"shell", "command", "mcp", "timeout_seconds"}


def allow_outside_comparisons(source: str) -> list[str]:
    """Mentions of ``ALLOW`` that are not an operand of a comparison."""
    tree = ast.parse(source)
    inside = {
        id(operand)
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        for operand in [node.left, *node.comparators]
    }
    return [
        f"ALLOW at line {node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "ALLOW" and id(node) not in inside
    ]


def tool_names_mentioned(source: str) -> list[str]:
    return [
        f"'{node.value}' at line {node.lineno}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in TOOL_NAMES
    ]


def scan(source: str, name: str = "ask_ceiling.py") -> list[str]:
    violations: list[str] = []
    violations.extend(forbidden_imports(source))
    violations.extend(io_stdlib_imports(source))
    violations.extend(find_config_reads(source, name, PACKAGE))
    violations.extend(terminal_uses(source))
    violations.extend(allow_outside_comparisons(source))
    violations.extend(tool_names_mentioned(source))
    violations.extend(handlers_not_denying(source))
    violations.extend(stateful_methods(source))
    return violations


def test_the_ceiling_only_makes_decisions_stricter() -> None:
    assert scan(MODULE.read_text(encoding="utf-8")) == []


def test_the_module_compares_with_allow_and_has_a_denying_handler() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    assert [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    assert any(isinstance(n, ast.Attribute) and n.attr == "ALLOW" for n in ast.walk(tree))


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3\n",
        "from harness_agent.adapters import x\n",
        "print('hola')\n",
        "def f():\n    return PermissionDecision.ALLOW\n",
        "x = PermissionDecision.ALLOW\n",
        "x = 'shell'\n",
        "try:\n    pass\nexcept Exception:\n    return PermissionDecision.ASK\n",
    ],
    ids=[
        "sqlite",
        "adapters",
        "terminal",
        "return-allow",
        "assign-allow",
        "tool-name",
        "ask-in-except",
    ],
)
def test_the_rules_flag_violations(source: str) -> None:
    assert scan(source) != []


def test_a_comparison_with_allow_is_fine() -> None:
    assert allow_outside_comparisons("ok = decision is PermissionDecision.ALLOW\n") == []


def test_the_rules_fail_on_a_mutation_of_the_real_module(tmp_path: Path) -> None:
    copy = tmp_path / "ask_ceiling.py"
    shutil.copyfile(MODULE, copy)
    copy.write_text(
        copy.read_text(encoding="utf-8") + "\nOPEN = PermissionDecision.ALLOW\n", encoding="utf-8"
    )

    assert scan(copy.read_text(encoding="utf-8")) != []
