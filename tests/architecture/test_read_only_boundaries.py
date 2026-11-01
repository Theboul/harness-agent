"""Architecture guard of the read-only mode (HU-05-07).

``core/permissions/read_only.py`` and ``git_reads.py``:

* import only the standard library and ``harness_agent.core``, do no I/O, read no configuration
  or environment and do not use the terminal;
* ``read_only.py`` knows no tool (``"shell"``, ``"command"``, ``"escribir_archivo"``…) and only
  compares with ``PermissionDecision.ALLOW`` (it can restrict, never open a door); every ``except``
  returns ``DENY``; no method other than ``__init__`` keeps state;
* ``git_reads.py`` adds no table of its own: it is a few lines over ``GitPolicy``.

**Only ``bootstrap.py`` connects the mode**: no other module of ``src/`` names ``ReadOnlyPolicy``
or ``only_git_reads`` apart from their own modules and the public exports.

The rules have a self-test on synthetic fragments and a mutation test on a copy of the module.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

from tests.architecture.test_ask_ceiling_boundaries import allow_outside_comparisons
from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_permissions_boundaries import stateful_methods
from tests.architecture.test_protected_policy_boundaries import handlers_not_denying
from tests.architecture.test_review_boundaries import names_any
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
PERMISSIONS = SRC / "core" / "permissions"
POLICY = PERMISSIONS / "read_only.py"
CLASSIFIER = PERMISSIONS / "git_reads.py"
PACKAGE = "harness_agent.core.permissions"
TOOL_NAMES = {
    "shell",
    "command",
    "git",
    "leer_archivo",
    "escribir_archivo",
    "listar_archivos",
    "buscar_texto",
    "preguntar_usuario",
}
OWN = {POLICY, CLASSIFIER}
EXPORTS = {PERMISSIONS / "__init__.py", SRC / "core" / "__init__.py"}
NAMES = {"ReadOnlyPolicy", "only_git_reads"}


def tool_names_mentioned(source: str) -> list[str]:
    return [
        f"'{node.value}' at line {node.lineno}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in TOOL_NAMES
    ]


def common(source: str, name: str) -> list[str]:
    violations: list[str] = []
    violations.extend(forbidden_imports(source))
    violations.extend(io_stdlib_imports(source))
    violations.extend(find_config_reads(source, name, PACKAGE))
    violations.extend(terminal_uses(source))
    return violations


def scan_policy(source: str, name: str = "read_only.py") -> list[str]:
    violations = common(source, name)
    violations.extend(allow_outside_comparisons(source))
    violations.extend(tool_names_mentioned(source))
    violations.extend(handlers_not_denying(source))
    violations.extend(stateful_methods(source))
    return violations


def scan_classifier(source: str, name: str = "git_reads.py") -> list[str]:
    violations = common(source, name)
    return violations


def test_the_policy_can_only_restrict() -> None:
    assert scan_policy(POLICY.read_text(encoding="utf-8")) == []


def test_the_classifier_is_pure() -> None:
    assert scan_classifier(CLASSIFIER.read_text(encoding="utf-8")) == []


def test_the_classifier_has_no_table_of_its_own() -> None:
    tree = ast.parse(CLASSIFIER.read_text(encoding="utf-8"))
    tables: list[ast.AST] = [n for n in ast.walk(tree) if isinstance(n, ast.Set)]
    tables += [n for n in ast.walk(tree) if isinstance(n, ast.Dict) and len(n.keys) > 1]
    assert not tables
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]


def test_the_policy_compares_with_allow_and_has_a_denying_handler() -> None:
    tree = ast.parse(POLICY.read_text(encoding="utf-8"))
    assert [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]


def test_only_bootstrap_connects_the_mode() -> None:
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "bootstrap.py" or path in EXPORTS or path in OWN:
            continue
        if names_any(path.read_text(encoding="utf-8"), NAMES):
            offenders.append(path.relative_to(SRC).as_posix())
    assert offenders == []


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3\n",
        "from harness_agent.adapters import x\n",
        "print('hola')\n",
        "def f():\n    return PermissionDecision.ALLOW\n",
        "x = PermissionDecision.ALLOW\n",
        "x = 'shell'\n",
        "x = 'escribir_archivo'\n",
        "try:\n    pass\nexcept Exception:\n    return PermissionDecision.ASK\n",
    ],
    ids=[
        "sqlite",
        "adapters",
        "terminal",
        "return-allow",
        "assign-allow",
        "shell-name",
        "tool-name",
        "ask-in-except",
    ],
)
def test_the_policy_rules_flag_violations(source: str) -> None:
    assert scan_policy(source) != []


@pytest.mark.parametrize("source", ["import subprocess\n", "import os\nos.environ\n", "print(1)\n"])
def test_the_classifier_rules_flag_violations(source: str) -> None:
    assert scan_classifier(source) != []


def test_the_rules_fail_on_a_mutation_of_the_real_module(tmp_path: Path) -> None:
    copy = tmp_path / "read_only.py"
    shutil.copyfile(POLICY, copy)
    copy.write_text(
        copy.read_text(encoding="utf-8") + "\nOPEN = PermissionDecision.ALLOW\n", encoding="utf-8"
    )

    assert scan_policy(copy.read_text(encoding="utf-8")) != []
