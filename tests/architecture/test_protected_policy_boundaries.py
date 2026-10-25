"""Architecture test of the protecting policy (HU-11-01 / T012).

``core/permissions/protected.py`` can only make a policy stricter:

* it imports only the standard library and ``harness_agent.core`` and does no I/O;
* it never names ``PermissionDecision.ALLOW`` (the decorator denies or delegates, it never opens
  a door the inner policy kept shut);
* every ``except`` handler returns ``PermissionDecision.DENY`` (it fails closed).

The rules have a self-test on synthetic fragments.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

PACKAGE = "harness_agent.core.permissions"
PROTECTED_FILE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "harness_agent"
    / "core"
    / "permissions"
    / "protected.py"
)


def allow_mentions(source: str) -> list[str]:
    """Every reference to ``ALLOW`` as an attribute or a name."""
    return [
        f"ALLOW at line {node.lineno}"
        for node in ast.walk(ast.parse(source))
        if (isinstance(node, ast.Attribute) and node.attr == "ALLOW")
        or (isinstance(node, ast.Name) and node.id == "ALLOW")
    ]


def _is_deny(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "DENY"


def handlers_not_denying(source: str) -> list[str]:
    """``except`` handlers whose body does not end in ``return ...DENY``."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ExceptHandler):
            last = node.body[-1]
            if not (isinstance(last, ast.Return) and _is_deny(last.value)):
                found.append(f"except at line {node.lineno} does not return DENY")
    return found


def scan(source: str, name: str = "protected.py") -> list[str]:
    violations: list[str] = []
    violations.extend(forbidden_imports(source))
    violations.extend(io_stdlib_imports(source))
    violations.extend(find_config_reads(source, name, PACKAGE))
    violations.extend(terminal_uses(source))
    violations.extend(allow_mentions(source))
    violations.extend(handlers_not_denying(source))
    return violations


def test_the_protecting_policy_only_makes_decisions_stricter() -> None:
    assert scan(PROTECTED_FILE.read_text(encoding="utf-8")) == []


def test_the_policy_really_has_a_handler_that_denies() -> None:
    tree = ast.parse(PROTECTED_FILE.read_text(encoding="utf-8"))
    assert [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3\n",
        "from harness_agent.adapters import x\n",
        "print('hola')\n",
        "x = PermissionDecision.ALLOW\n",
        "try:\n    pass\nexcept Exception:\n    return PermissionDecision.ASK\n",
        "try:\n    pass\nexcept Exception:\n    pass\n",
    ],
    ids=["sqlite", "adapters", "terminal", "allow", "ask-en-excepcion", "excepcion-silenciosa"],
)
def test_the_rules_flag_violations(source: str) -> None:
    assert scan(source) != []


def test_the_rules_let_a_denying_handler_through() -> None:
    source = "try:\n    pass\nexcept Exception:\n    return PermissionDecision.DENY\n"
    assert scan(source) == []
