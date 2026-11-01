"""Architecture guard of the models by alias and the planning mode (HU-06-06).

``core/permissions/mode_switch.py``:

* imports only the standard library and ``harness_agent.core``, does no I/O, reads no configuration
  or environment and does not use the terminal; it names no tool (``"shell"``…) and never names
  ``PermissionDecision.ALLOW`` (it forwards the answer of a policy, it cannot open a door);
* every ``except`` returns ``DENY``;
* only ``ReadOnlySwitch`` changes its own state outside ``__init__`` (``SwitchablePolicy``
  keeps none).

``adapters/providers/model_switch.py``:

* imports only the standard library, the public API of the core and its own package; knows no
  events and never blocks the loop; no provider name in a literal (they come from the build
  function the composition root injects);
* never copies the text of a failure: no ``except … as name``; handlers catch only
  ``ModelUnavailable`` and ``Exception``, never a cancellation;
* the build function is called nowhere but in ``select``.

**Only ``bootstrap.py`` connects them**, and the active model comes from the switch: ``_compactor``
does not read ``config.model``.

Each rule has a self-test on synthetic fragments and a mutation test on a copy of the real module.
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
from tests.architecture.test_protected_policy_boundaries import handlers_not_denying
from tests.architecture.test_retry_boundaries import (
    blocking_imports,
    event_imports,
    foreign_imports,
)
from tests.architecture.test_review_boundaries import names_any
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
SWITCH = SRC / "core" / "permissions" / "mode_switch.py"
PROVIDER = SRC / "adapters" / "providers" / "model_switch.py"
BOOTSTRAP = SRC / "bootstrap.py"
PACKAGE = "harness_agent.core.permissions"
TOOL_NAMES = {"shell", "command", "git", "leer_archivo", "escribir_archivo", "preguntar_usuario"}
PROVIDER_NAMES = {"openai", "anthropic", "gemini", "groq", "ollama", "openrouter", "fake"}
ALLOWED_HANDLERS = {"ModelUnavailable", "Exception"}
STATEFUL_CLASS = "ReadOnlySwitch"
OWN = {SWITCH, PROVIDER}
EXPORTS = {
    SRC / "core" / "permissions" / "__init__.py",
    SRC / "core" / "__init__.py",
}
NAMES = {"ModelSwitch", "SwitchablePolicy", "ReadOnlySwitch"}


def literal_matches(source: str, words: set[str]) -> list[str]:
    return [
        f"'{node.value}' at line {node.lineno}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in words
    ]


def foreign_state_changes(source: str) -> list[str]:
    """Assignments to ``self.<name>`` outside ``__init__`` in a class other than the switch."""
    found: list[str] = []
    for cls in (n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ClassDef)):
        if cls.name == STATEFUL_CLASS:
            continue
        for method in (n for n in cls.body if isinstance(n, ast.FunctionDef)):
            if method.name == "__init__":
                continue
            for node in (n for n in ast.walk(method) if isinstance(n, ast.stmt)):
                targets = (
                    node.targets
                    if isinstance(node, ast.Assign)
                    else [node.target]
                    if isinstance(node, (ast.AugAssign, ast.AnnAssign))
                    else []
                )
                found.extend(
                    f"self.{target.attr} at line {node.lineno}"
                    for target in targets
                    if isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                )
    return found


def scan_switch(source: str, name: str = "mode_switch.py") -> list[str]:
    violations = forbidden_imports(source)
    violations.extend(io_stdlib_imports(source))
    violations.extend(find_config_reads(source, name, PACKAGE))
    violations.extend(terminal_uses(source))
    violations.extend(allow_outside_comparisons(source))
    violations.extend(literal_matches(source, TOOL_NAMES))
    violations.extend(handlers_not_denying(source))
    violations.extend(foreign_state_changes(source))
    return violations


def risky_handlers(source: str) -> list[str]:
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.name is not None:
            found.append(f"except … as {node.name} at line {node.lineno}")
        if node.type is None:
            found.append(f"bare except at line {node.lineno}")
        elif not (isinstance(node.type, ast.Name) and node.type.id in ALLOWED_HANDLERS):
            found.append(f"except {ast.dump(node.type)} at line {node.lineno}")
    return found


def build_calls_outside_select(source: str) -> list[str]:
    found: list[str] = []
    for func in (n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)):
        if func.name == "select":
            continue
        found.extend(
            f"self._build() in {func.name} at line {node.lineno}"
            for node in ast.walk(func)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_build"
        )
    return found


def scan_provider(source: str) -> list[str]:
    violations = foreign_imports_for_provider(source)
    violations.extend(event_imports(source))
    violations.extend(blocking_imports(source))
    violations.extend(terminal_uses(source))
    violations.extend(
        find_config_reads(source, "model_switch.py", "harness_agent.adapters.providers")
    )
    violations.extend(literal_matches(source, PROVIDER_NAMES))
    violations.extend(risky_handlers(source))
    violations.extend(build_calls_outside_select(source))
    return violations


def foreign_imports_for_provider(source: str) -> list[str]:
    return foreign_imports(source)


def compactor_reads_config_model(source: str) -> list[str]:
    """Reads of ``config.model`` inside ``_compactor``: the active model comes from the switch."""
    found: list[str] = []
    for func in (n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)):
        if func.name != "_compactor":
            continue
        found.extend(
            f"config.model at line {node.lineno}"
            for node in ast.walk(func)
            if isinstance(node, ast.Attribute)
            and node.attr == "model"
            and isinstance(node.value, ast.Name)
            and node.value.id == "config"
        )
    return found


# --- the real code --------------------------------------------------------------------------


def test_the_switch_of_the_mode_follows_the_rules() -> None:
    assert scan_switch(SWITCH.read_text(encoding="utf-8")) == []


def test_the_switchable_provider_follows_the_rules() -> None:
    assert scan_provider(PROVIDER.read_text(encoding="utf-8")) == []


def test_only_bootstrap_connects_the_pieces() -> None:
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path.name == "bootstrap.py" or path in EXPORTS or path in OWN:
            continue
        if names_any(path.read_text(encoding="utf-8"), NAMES):
            offenders.append(path.relative_to(SRC).as_posix())
    assert offenders == []


def test_the_compactor_takes_the_active_model_from_the_switch() -> None:
    assert compactor_reads_config_model(BOOTSTRAP.read_text(encoding="utf-8")) == []


# --- the detectors detect -------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3\n",
        "from harness_agent.adapters import x\n",
        "print('hola')\n",
        "x = PermissionDecision.ALLOW\n",
        "x = 'shell'\n",
        "try:\n    pass\nexcept Exception:\n    return PermissionDecision.ASK\n",
        "class SwitchablePolicy:\n    def evaluate(self):\n        self._x = 1\n",
    ],
    ids=["sqlite", "adapters", "terminal", "allow", "tool-name", "ask-in-except", "state"],
)
def test_the_switch_rules_flag_violations(source: str) -> None:
    assert scan_switch(source) != []


def test_the_switch_class_may_change_its_state() -> None:
    source = "class ReadOnlySwitch:\n    def enable(self):\n        self._x = 1\n"
    assert foreign_state_changes(source) == []


@pytest.mark.parametrize(
    "source",
    [
        "from harness_agent.config import Secret\n",
        "import time\n",
        "from harness_agent.core import EventType\n",
        "x = 'groq'\n",
        "try:\n    pass\nexcept Exception as error:\n    pass\n",
        "try:\n    pass\nexcept BaseException:\n    pass\n",
        "try:\n    pass\nexcept:\n    pass\n",
        "class S:\n    def other(self):\n        self._build('x')\n",
    ],
    ids=["config", "time", "events", "provider-name", "binding", "base", "bare", "build-outside"],
)
def test_the_provider_rules_flag_violations(source: str) -> None:
    assert scan_provider(source) != []


def test_the_compactor_detector_flags_a_config_model_read() -> None:
    assert compactor_reads_config_model("def _compactor(config):\n    return config.model\n")
    assert not compactor_reads_config_model("def _compactor(config):\n    return config.context\n")
    assert not compactor_reads_config_model("def other(config):\n    return config.model\n")


@pytest.mark.parametrize(
    ("path", "scan", "addition"),
    [
        (SWITCH, scan_switch, "\nOPEN = PermissionDecision.ALLOW\n"),
        (PROVIDER, scan_provider, "\nimport time\n"),
    ],
    ids=["switch", "provider"],
)
def test_the_rules_fail_on_a_mutation_of_the_real_module(
    tmp_path: Path, path: Path, scan: object, addition: str
) -> None:
    copy = tmp_path / path.name
    shutil.copyfile(path, copy)
    copy.write_text(copy.read_text(encoding="utf-8") + addition, encoding="utf-8")

    assert scan(copy.read_text(encoding="utf-8")) != []  # type: ignore[operator]
