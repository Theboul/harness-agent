"""Architecture guard of the subagents (HU-09-01, HU-09-03, HU-09-04 / T007).

``core/subagents/`` is pure: it imports only the standard library and ``harness_agent.core``, does
no I/O, reads no file nor environment and does not use the terminal. Beyond that:

* nothing in it imports the loop, the permissions, the context, the verification, the adapters or
  the CLI (the loop and the session of the child come in by constructor from ``bootstrap.py``);
* no handler catches ``BaseException`` or ``CancelledError`` (a cancellation reaches the caller);
* the view of the registry never registers a tool;
* the runner publishes only the two events of the catalog that are about subagents.

Each rule is proved on the real files and on a mutated copy that breaks it. The detectors of the
other guards are reused, not copied.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_approvals_boundaries import catches_cancellation, imported_modules
from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

PACKAGE = "harness_agent.core.subagents"
MODULE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core" / "subagents"
REGISTRY = MODULE_DIR / "registry.py"
RUNNER = MODULE_DIR / "runner.py"
FORBIDDEN = (
    "harness_agent.core.loop",
    "harness_agent.core.permissions",
    "harness_agent.core.context",
    "harness_agent.core.verification",
    "harness_agent.adapters",
    "harness_agent.cli",
    "harness_agent.config",
    "harness_agent.bootstrap",
)
ALLOWED_EVENTS = {"SUBAGENT_STARTED", "SUBAGENT_FINISHED"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- detectors ---------------------------------------------------------------------------------


def scan_package(directory: Path) -> list[str]:
    files = sorted(directory.rglob("*.py"))
    assert files, f"No Python files found under {directory}"
    violations: list[str] = []
    for file_path in files:
        source = read(file_path)
        name = file_path.name
        violations.extend(f"{name}: {m}" for m in forbidden_imports(source))
        violations.extend(f"{name}: {m}" for m in io_stdlib_imports(source))
        violations.extend(f"{name}: {m}" for m in find_config_reads(source, name, PACKAGE))
        violations.extend(f"{name}: {m}" for m in terminal_uses(source))
        violations.extend(f"{name}: {m}" for m in reaches_forbidden(source))
        violations.extend(f"{name}: handler at line {n}" for n in catches_cancellation(source))
    return violations


def reaches_forbidden(source: str) -> list[str]:
    return [
        f"imports {module}"
        for module in imported_modules(source)
        if any(module == p or module.startswith(p + ".") for p in FORBIDDEN)
    ]


def registrations(source: str) -> list[int]:
    """Lines that call ``.register(...)`` on anything."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "register"
    ]


def foreign_events(source: str) -> list[str]:
    """``EventType.<name>`` uses other than the two events about subagents."""
    return [
        node.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "EventType"
        and node.attr not in ALLOWED_EVENTS
    ]


def mutate(source: str, anchor: str, replacement: str) -> str:
    assert anchor in source, anchor
    return source.replace(anchor, replacement, 1)


# --- the rules on the real files ---------------------------------------------------------------


def test_the_package_is_pure_and_reaches_nothing_it_should_not() -> None:
    assert scan_package(MODULE_DIR) == []


def test_the_view_of_the_registry_never_registers_a_tool() -> None:
    assert registrations(read(REGISTRY)) == []


def test_the_runner_publishes_only_the_two_events_about_subagents() -> None:
    assert foreign_events(read(RUNNER)) == []
    assert ALLOWED_EVENTS <= {
        node.attr for node in ast.walk(ast.parse(read(RUNNER))) if isinstance(node, ast.Attribute)
    }


# --- the mutations: each rule fails on a copy that breaks it -----------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3\n",
        "import subprocess\n",
        "from pathlib import Path\n",
        "from harness_agent.core.loop import AgentLoop\n",
        "from harness_agent.core.permissions import ExactCallPolicy\n",
        "from harness_agent.core.context import ContextCompactor\n",
        "from harness_agent.core.verification import CriteriaVerifier\n",
        "from harness_agent.adapters.storage import SqliteSessionStore\n",
        "from harness_agent.cli import run_cli\n",
        "from harness_agent.config import load_config\n",
        "from harness_agent.bootstrap import compose\n",
        "import os\nos.environ['X']\n",
        "print('hola')\n",
    ],
    ids=[
        "sqlite",
        "subprocess",
        "pathlib",
        "loop",
        "permissions",
        "context",
        "verification",
        "adapters",
        "cli",
        "config",
        "bootstrap",
        "environment",
        "terminal",
    ],
)
def test_detectors_flag_violations(source: str, tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(source, encoding="utf-8")
    assert scan_package(tmp_path) != []


def test_detectors_let_pure_code_through(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text(
        "import json\nfrom dataclasses import dataclass\n"
        "from harness_agent.core.entities import Message\n"
        "from harness_agent.core.tools.schema_validator import validate_arguments\n",
        encoding="utf-8",
    )
    assert scan_package(tmp_path) == []


CATCH = "        except Exception:" + chr(10)
CATCHING = {
    "except BaseException": "        except BaseException:" + chr(10),
    "bare except": "        except:" + chr(10),
    "except CancelledError": "        except asyncio.CancelledError:" + chr(10),
}


@pytest.mark.parametrize("name", list(CATCHING))
def test_a_runner_that_catches_cancellation_is_flagged(name: str) -> None:
    mutated = mutate(read(RUNNER), CATCH, CATCHING[name])

    assert catches_cancellation(mutated) != []


def test_a_view_that_registers_is_flagged() -> None:
    mutated = mutate(
        read(REGISTRY),
        '        raise TypeError("La vista',
        "        self._inner.register(tool)\n" + '        raise TypeError("La vista',
    )

    assert registrations(mutated) != []


def test_a_runner_that_publishes_another_event_is_flagged() -> None:
    mutated = mutate(read(RUNNER), "EventType.SUBAGENT_STARTED", "EventType.USER_MESSAGE")

    assert foreign_events(mutated) == ["USER_MESSAGE"]
