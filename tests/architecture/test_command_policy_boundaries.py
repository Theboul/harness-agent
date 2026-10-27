"""Architecture test of the command analysis and its policy (HU-05-02 / T006).

``core/permissions/command_parser.py``, ``command_rules.py`` and ``command_policy.py``:

* import only the standard library and ``harness_agent.core``; no adapters, configuration or CLI,
  no third parties and none of the standard modules that do I/O or touch the system (``os``,
  ``subprocess``, ``socket``, ``pathlib``, ``shutil``…) nor ``shlex``;
* read no file, environment or configuration and do not use the terminal;
* do not name the shell tool or its arguments: the composition root gives them. The rules and
  the policy never contain ``"shell"``, ``"command"`` or ``"timeout_seconds"``; the parser never
  contains ``"shell"`` or ``"timeout_seconds"`` (it must know the word ``command``, which is the
  ``command`` builtin of bash and the ``-Command`` parameter of PowerShell, not the tool);
* the rules and the policy store no state outside ``__init__`` (the parser uses a scanner object
  created for each call to ``parse_command`` and never shared);
* ``command_policy.py`` only hardens: ``PermissionDecision.ALLOW`` appears only inside a
  comparison (never returned or assigned), and every ``except`` returns ``DENY`` or "not
  understood" (``False``).

The detectors are reused from the other guards; the new ones have a self-test with synthetic
fragments and a mutation test on a copy in ``tmp_path`` (the real code is never edited).
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

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core" / "permissions"
MODULES = ("command_parser.py", "command_rules.py", "command_policy.py")
POLICY = "command_policy.py"
PACKAGE = "harness_agent.core.permissions"
EXTRA_FORBIDDEN = {"os", "shlex", "subprocess", "socket", "pathlib", "shutil", "sys", "io"}
SHELL_NAMES = {"shell", "command", "timeout_seconds"}
# The parser has to recognize the word ``command`` (bash builtin, ``-Command`` of PowerShell).
PARSER_SHELL_NAMES = SHELL_NAMES - {"command"}
PARSER = "command_parser.py"


def extra_forbidden_imports(source: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules = [node.module]
        else:
            continue
        found.extend(
            f"{module} at line {node.lineno}"
            for module in modules
            if module.split(".")[0] in EXTRA_FORBIDDEN
        )
    return found


def shell_names(source: str, names: frozenset[str] | set[str] = SHELL_NAMES) -> list[str]:
    return [
        f"{node.value!r} at line {node.lineno}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and node.value in names
    ]


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def allows_outside_comparisons(source: str) -> list[str]:
    """Every ``PermissionDecision.ALLOW`` (or ``"allow"``) that is not part of a comparison."""
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
        if is_allow and not isinstance(parents.get(node), ast.Compare):
            found.append(f"ALLOW at line {getattr(node, 'lineno', 0)} is not only compared")
    return found


def _is_hardening_return(statement: ast.stmt) -> bool:
    if not isinstance(statement, ast.Return) or statement.value is None:
        return False
    value = statement.value
    return (
        isinstance(value, ast.Attribute)
        and value.attr == "DENY"
        and isinstance(value.value, ast.Name)
        and value.value.id == "PermissionDecision"
    ) or (isinstance(value, ast.Constant) and value.value is False)


def soft_handlers(source: str) -> list[str]:
    """Every ``except`` whose body does not end returning ``DENY`` or ``False``."""
    return [
        f"except at line {node.lineno} does not return DENY or False"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ExceptHandler)
        and not (node.body and _is_hardening_return(node.body[-1]))
    ]


def scan(directory: Path) -> list[str]:
    violations: list[str] = []
    for name in MODULES:
        source = (directory / name).read_text(encoding="utf-8")
        violations.extend(f"{name}: {m}" for m in forbidden_imports(source))
        violations.extend(f"{name}: {m}" for m in io_stdlib_imports(source))
        violations.extend(f"{name}: {m}" for m in extra_forbidden_imports(source))
        violations.extend(f"{name}: {m}" for m in find_config_reads(source, name, PACKAGE))
        violations.extend(f"{name}: {m}" for m in terminal_uses(source))
        names = PARSER_SHELL_NAMES if name == PARSER else SHELL_NAMES
        violations.extend(f"{name}: names the shell: {m}" for m in shell_names(source, names))
        if name != PARSER:
            violations.extend(f"{name}: {m}" for m in stateful_methods(source))
        if name == POLICY:
            violations.extend(f"{name}: {m}" for m in allows_outside_comparisons(source))
            violations.extend(f"{name}: {m}" for m in soft_handlers(source))
    return violations


class TestAutopruebaDeLosDetectores:
    @pytest.mark.parametrize(
        "fragment",
        ["import os\n", "import shlex\n", "from subprocess import run\n", "import sys\n"],
    )
    def test_a_forbidden_standard_module_is_detected(self, fragment: str) -> None:
        assert extra_forbidden_imports(fragment)

    def test_allowed_imports_are_not_detected(self) -> None:
        assert extra_forbidden_imports("import re\nfrom dataclasses import dataclass\n") == []

    @pytest.mark.parametrize("name", sorted(SHELL_NAMES))
    def test_a_name_of_the_shell_is_detected(self, name: str) -> None:
        assert shell_names(f"X = {name!r}\n")

    def test_the_parser_may_name_the_command_builtin_but_not_the_tool(self) -> None:
        assert shell_names("X = 'command'\n", PARSER_SHELL_NAMES) == []
        assert shell_names("X = 'shell'\n", PARSER_SHELL_NAMES)
        assert shell_names("X = 'timeout_seconds'\n", PARSER_SHELL_NAMES)

    def test_the_rules_and_the_policy_keep_no_state(self) -> None:
        source = "class C:\n    def f(self):\n        self.a = 1\n"

        assert stateful_methods(source)

    def test_comparing_with_allow_is_accepted(self) -> None:
        source = "def f(d):\n    if d is PermissionDecision.ALLOW:\n        return d\n"

        assert allows_outside_comparisons(source) == []

    @pytest.mark.parametrize(
        "source",
        [
            "def f():\n    return PermissionDecision.ALLOW\n",
            "def f():\n    x = PermissionDecision.ALLOW\n    return x\n",
            "def f(d):\n    return PermissionDecision.ALLOW if d else PermissionDecision.ASK\n",
            "def f():\n    return PermissionDecision('allow')\n",
        ],
    )
    def test_an_allow_that_is_returned_or_assigned_is_detected(self, source: str) -> None:
        assert allows_outside_comparisons(source)

    def test_hardening_handlers_are_accepted(self) -> None:
        source = (
            "def f():\n    try:\n        pass\n    except Exception:\n"
            "        return PermissionDecision.DENY\n"
            "def g():\n    try:\n        pass\n    except Exception:\n        return False\n"
        )

        assert soft_handlers(source) == []

    @pytest.mark.parametrize(
        "handler",
        [
            "return PermissionDecision.ASK",
            "return True",
            "pass",
            "return",
            "raise",
        ],
    )
    def test_a_soft_handler_is_detected(self, handler: str) -> None:
        source = f"def f():\n    try:\n        pass\n    except Exception:\n        {handler}\n"

        assert soft_handlers(source)


class TestLosModulosReales:
    def test_they_respect_every_rule(self) -> None:
        violations = scan(PACKAGE_DIR)

        assert violations == [], "el análisis de comandos rompe una regla:\n" + "\n".join(
            violations
        )

    def test_the_policy_compares_with_allow_at_least_once(self) -> None:
        source = (PACKAGE_DIR / POLICY).read_text(encoding="utf-8")

        assert "PermissionDecision.ALLOW" in source


def _fingerprint(directory: Path) -> dict[str, str]:
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in MODULES}


class TestMutacionSobreUnaCopia:
    def test_the_detectors_fail_on_a_copy_that_allows_or_runs_commands(
        self, tmp_path: Path
    ) -> None:
        before = _fingerprint(PACKAGE_DIR)
        for name in MODULES:
            shutil.copyfile(PACKAGE_DIR / name, tmp_path / name)
        assert scan(tmp_path) == []
        with (tmp_path / POLICY).open("a", encoding="utf-8") as handle:
            handle.write(
                "\n\nimport subprocess\n\n\ndef extra(call: ToolCall) -> PermissionDecision:\n"
                "    try:\n"
                "        subprocess.run(['shell'])\n"
                "    except Exception:\n"
                "        return PermissionDecision.ASK\n"
                "    return PermissionDecision.ALLOW\n"
            )

        violations = scan(tmp_path)

        assert any("subprocess" in message for message in violations)
        assert any("names the shell" in message for message in violations)
        assert any("is not only compared" in message for message in violations)
        assert any("does not return DENY or False" in message for message in violations)
        assert _fingerprint(PACKAGE_DIR) == before
