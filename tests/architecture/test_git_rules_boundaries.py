"""Architecture test of the git rules and the hiding of credentials (HU-11-02 / T004, T005).

``core/permissions/git_table.py``, ``core/permissions/git_rules.py`` and ``core/redaction.py``:

* import only the standard library and ``harness_agent.core``; no adapters, configuration or CLI,
  no third parties and none of the standard modules that do I/O or touch the system (``os``,
  ``subprocess``, ``socket``, ``pathlib``, ``shutil``, ``sys``…) nor ``shlex``;
* read no file, environment or configuration and do not use the terminal;
* do not name the shell tool or its arguments (``"shell"``, ``"command"``, ``"timeout_seconds"``):
  the composition root gives them;
* store no state outside ``__init__``;
* ``git_table.py`` is data only: no function, class, lambda, loop, condition or comprehension;
* ``git_rules.py`` allows in one place only: ``PermissionDecision.ALLOW`` appears once, inside
  ``if self._only_reads(…) is True:``, and every ``except`` returns ``ASK`` or ``DENY``.

The detectors are reused from the other guards; the new ones have a self-test with synthetic
fragments and a mutation test on a copy in ``tmp_path`` (the real code is never edited).
"""

from __future__ import annotations

import ast
import hashlib
import shutil
from pathlib import Path

import pytest

from tests.architecture.test_command_policy_boundaries import extra_forbidden_imports, shell_names
from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_permissions_boundaries import stateful_methods
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core"
PERMISSIONS_DIR = CORE_DIR / "permissions"
TABLE = "git_table.py"
RULES = "git_rules.py"
REDACTION = "redaction.py"
MODULES = {
    TABLE: PERMISSIONS_DIR / TABLE,
    RULES: PERMISSIONS_DIR / RULES,
    REDACTION: CORE_DIR / REDACTION,
}
PACKAGES = {
    TABLE: "harness_agent.core.permissions",
    RULES: "harness_agent.core.permissions",
    REDACTION: "harness_agent.core",
}
LOGIC = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
    ast.If,
    ast.For,
    ast.While,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


def logic_in(source: str) -> list[str]:
    return [
        f"{type(node).__name__} at line {getattr(node, 'lineno', 0)}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, LOGIC)
    ]


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _is_allow(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "ALLOW"
        and isinstance(node.value, ast.Name)
        and node.value.id == "PermissionDecision"
    ) or (isinstance(node, ast.Constant) and node.value in ("allow", "ALLOW"))


def _is_only_reads_true(test: ast.expr) -> bool:
    """``self._only_reads(<one argument>) is True``."""
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
        and call.func.attr == "_only_reads"
        and len(call.args) == 1
        and not call.keywords
    )


def allow_problems(source: str) -> list[str]:
    """``ALLOW`` must appear exactly once, inside ``if self._only_reads(…) is True:``."""
    tree = ast.parse(source)
    parents = _parents(tree)
    allows = [node for node in ast.walk(tree) if _is_allow(node)]
    found: list[str] = []
    if len(allows) != 1:
        found.append(f"ALLOW appears {len(allows)} times, not once")
    for node in allows:
        child, ancestor, guarded = node, parents.get(node), False
        while ancestor is not None:
            if isinstance(ancestor, ast.If) and child in ancestor.body:
                if _is_only_reads_true(ancestor.test):
                    guarded = True
                    break
            child, ancestor = ancestor, parents.get(ancestor)
        if not guarded:
            line = getattr(node, "lineno", 0)
            found.append(f"ALLOW at line {line} is not inside if self._only_reads(...) is True")
    return found


def _is_hardening_return(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Return)
        and isinstance(statement.value, ast.Attribute)
        and statement.value.attr in ("ASK", "DENY")
        and isinstance(statement.value.value, ast.Name)
        and statement.value.value.id == "PermissionDecision"
    )


def soft_handlers(source: str) -> list[str]:
    return [
        f"except at line {node.lineno} does not return ASK or DENY"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ExceptHandler)
        and not (node.body and _is_hardening_return(node.body[-1]))
    ]


def scan(modules: dict[str, Path]) -> list[str]:
    violations: list[str] = []
    for name, path in modules.items():
        source = path.read_text(encoding="utf-8")
        violations.extend(f"{name}: {m}" for m in forbidden_imports(source))
        violations.extend(f"{name}: {m}" for m in io_stdlib_imports(source))
        violations.extend(f"{name}: {m}" for m in extra_forbidden_imports(source))
        package = PACKAGES[name]
        violations.extend(f"{name}: {m}" for m in find_config_reads(source, name, package))
        violations.extend(f"{name}: {m}" for m in terminal_uses(source))
        violations.extend(f"{name}: names the shell: {m}" for m in shell_names(source))
        violations.extend(f"{name}: {m}" for m in stateful_methods(source))
        if name == TABLE:
            violations.extend(f"{name}: logic: {m}" for m in logic_in(source))
        if name == RULES:
            violations.extend(f"{name}: {m}" for m in allow_problems(source))
            violations.extend(f"{name}: {m}" for m in soft_handlers(source))
    return violations


GUARDED = """\
def evaluate(self, call, verdict):
    if self._only_reads(verdict) is True:
        return PermissionDecision.ALLOW
    return PermissionDecision.ASK
"""


class TestAutopruebaDeLosDetectores:
    def test_the_guarded_allow_is_accepted(self) -> None:
        assert allow_problems(GUARDED) == []

    @pytest.mark.parametrize(
        "source",
        [
            "def f():\n    return PermissionDecision.ALLOW\n",
            GUARDED + "def g():\n    return PermissionDecision.ALLOW\n",
            (
                "def f(self, v):\n    if self._only_reads(v):\n"
                "        return PermissionDecision.ALLOW\n"
            ),
            "def f(self, v):\n    if v is True:\n        return PermissionDecision.ALLOW\n",
            "def f(self):\n    return PermissionDecision('allow')\n",
            "def f(self):\n    return 1\n",
        ],
    )
    def test_a_misplaced_or_missing_allow_is_detected(self, source: str) -> None:
        assert allow_problems(source)

    def test_hardening_handlers_are_accepted(self) -> None:
        source = (
            "def f():\n    try:\n        pass\n    except Exception:\n"
            "        return PermissionDecision.ASK\n"
            "def g():\n    try:\n        pass\n    except Exception:\n"
            "        return PermissionDecision.DENY\n"
        )

        assert soft_handlers(source) == []

    @pytest.mark.parametrize("handler", ["return PermissionDecision.ALLOW", "pass", "return False"])
    def test_a_soft_handler_is_detected(self, handler: str) -> None:
        source = f"def f():\n    try:\n        pass\n    except Exception:\n        {handler}\n"

        assert soft_handlers(source)

    @pytest.mark.parametrize("fragment", ["def f():\n    pass\n", "X = [a for a in 'b']\n"])
    def test_logic_in_the_table_is_detected(self, fragment: str) -> None:
        assert logic_in(fragment)


class TestLosModulosReales:
    def test_they_respect_every_rule(self) -> None:
        violations = scan(MODULES)

        assert violations == [], "las reglas de git rompen una regla:\n" + "\n".join(violations)


def _fingerprint(modules: dict[str, Path]) -> dict[str, str]:
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in modules.items()}


class TestMutacionSobreUnaCopia:
    def test_the_detectors_fail_on_copies_that_allow_more_or_do_io(self, tmp_path: Path) -> None:
        before = _fingerprint(MODULES)
        copies = {name: tmp_path / name for name in MODULES}
        for name, path in MODULES.items():
            shutil.copyfile(path, copies[name])
        assert scan(copies) == []
        with copies[RULES].open("a", encoding="utf-8") as handle:
            handle.write(
                "\n\nimport subprocess\n\n\ndef extra(call: ToolCall) -> PermissionDecision:\n"
                "    try:\n"
                "        subprocess.run(['shell'])\n"
                "    except Exception:\n"
                "        return PermissionDecision.ALLOW\n"
                "    return PermissionDecision.ALLOW\n"
            )
        with copies[TABLE].open("a", encoding="utf-8") as handle:
            handle.write("\n\ndef helper() -> int:\n    return 1\n")
        with copies[REDACTION].open("a", encoding="utf-8") as handle:
            handle.write("\n\nimport os\n\nVALUE = os.environ.get('X')\n")

        violations = scan(copies)

        assert any("subprocess" in message for message in violations)
        assert any("names the shell" in message for message in violations)
        assert any("ALLOW appears" in message for message in violations)
        assert any("does not return ASK or DENY" in message for message in violations)
        assert any("git_table.py: logic" in message for message in violations)
        assert any(m.startswith("redaction.py") and "os" in m for m in violations)
        assert _fingerprint(MODULES) == before
