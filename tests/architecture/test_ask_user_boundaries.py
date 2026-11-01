"""Architecture guards of the question with options (HU-06-02).

* ``core/permissions/open_tools.py`` imports only the standard library and ``harness_agent.core``,
  does no I/O, reads no configuration, knows no tool name and mentions ``PermissionDecision.ALLOW``
  only in a ``return`` (it can only open what was asked); every ``except`` denies.
* ``adapters/tools/ask_user.py`` does not use the terminal, does not import ``cli``, ``config`` or
  ``bootstrap``, and never catches cancellation (only ``Exception``).
* ``cli/question*.py`` does not import ``adapters``: the console reads the question by protocol.
* **Only ``bootstrap.py`` connects the pieces**: no other module of ``src/`` names ``AskUserTool``
  or ``ConsoleQuestioner`` apart from their own modules and the public exports.

The rules have a self-test on synthetic fragments.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_approvals_boundaries import catches_cancellation, imported_modules
from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_permissions_boundaries import stateful_methods
from tests.architecture.test_protected_policy_boundaries import handlers_not_denying
from tests.architecture.test_review_boundaries import names_any
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
POLICY = SRC / "core" / "permissions" / "open_tools.py"
TOOL = SRC / "adapters" / "tools" / "ask_user.py"
CONSOLE_FILES = [SRC / "cli" / "question.py", SRC / "cli" / "question_view.py"]
PACKAGE = "harness_agent.core.permissions"
TOOL_NAMES = {"preguntar_usuario", "shell", "leer_archivo"}
OWN = {TOOL, SRC / "cli" / "question.py"}
EXPORTS = {SRC / "adapters" / "tools" / "__init__.py", SRC / "cli" / "__init__.py"}
NAMES = {"AskUserTool", "ConsoleQuestioner"}


def allow_outside_return(source: str) -> list[str]:
    """Mentions of ``ALLOW`` that are not the value of a ``return``."""
    tree = ast.parse(source)
    allowed = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Return) and node.value is not None
    }
    return [
        f"ALLOW at line {node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "ALLOW" and id(node) not in allowed
    ]


def tool_names_mentioned(source: str) -> list[str]:
    return [
        f"'{node.value}' at line {node.lineno}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in TOOL_NAMES
    ]


def imports_of(source: str, *prefixes: str) -> list[str]:
    return [
        module
        for module in imported_modules(source)
        if any(module == prefix or module.startswith(prefix + ".") for prefix in prefixes)
    ]


def scan_policy(source: str, name: str = "open_tools.py") -> list[str]:
    violations: list[str] = []
    violations.extend(forbidden_imports(source))
    violations.extend(io_stdlib_imports(source))
    violations.extend(find_config_reads(source, name, PACKAGE))
    violations.extend(terminal_uses(source))
    violations.extend(allow_outside_return(source))
    violations.extend(tool_names_mentioned(source))
    violations.extend(handlers_not_denying(source))
    violations.extend(stateful_methods(source))
    return violations


def scan_tool(source: str) -> list[str]:
    violations: list[str] = []
    violations.extend(terminal_uses(source))
    violations.extend(imports_of(source, "harness_agent.cli", "harness_agent.bootstrap"))
    violations.extend(imports_of(source, "harness_agent.config"))
    violations.extend(str(line) for line in catches_cancellation(source))
    return violations


def test_the_policy_only_opens_what_was_asked() -> None:
    assert scan_policy(POLICY.read_text(encoding="utf-8")) == []


def test_the_tool_is_a_pure_adapter() -> None:
    assert scan_tool(TOOL.read_text(encoding="utf-8")) == []


def test_the_console_does_not_import_the_adapters() -> None:
    for path in CONSOLE_FILES:
        assert imports_of(path.read_text(encoding="utf-8"), "harness_agent.adapters") == []


def test_only_bootstrap_connects_the_pieces() -> None:
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "bootstrap.py" or path in EXPORTS or path in OWN:
            continue
        if names_any(path.read_text(encoding="utf-8"), NAMES):
            offenders.append(path.relative_to(SRC).as_posix())
    assert offenders == []


def test_the_policy_has_a_denying_handler() -> None:
    tree = ast.parse(POLICY.read_text(encoding="utf-8"))
    assert [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3\n",
        "from harness_agent.adapters import x\n",
        "print('hola')\n",
        "x = PermissionDecision.ALLOW\n",
        "x = 'preguntar_usuario'\n",
        "try:\n    pass\nexcept Exception:\n    return PermissionDecision.ASK\n",
    ],
    ids=["sqlite", "adapters", "terminal", "assign-allow", "tool-name", "ask-in-except"],
)
def test_the_policy_rules_flag_violations(source: str) -> None:
    assert scan_policy(source) != []


@pytest.mark.parametrize(
    "source",
    [
        "from harness_agent.cli import x\n",
        "from harness_agent.bootstrap import x\n",
        "print('hola')\n",
        "try:\n    pass\nexcept asyncio.CancelledError:\n    pass\n",
    ],
    ids=["cli", "bootstrap", "terminal", "cancellation"],
)
def test_the_tool_rules_flag_violations(source: str) -> None:
    assert scan_tool(source) != []


def test_a_return_of_allow_is_fine() -> None:
    assert allow_outside_return("def f():\n    return PermissionDecision.ALLOW\n") == []
