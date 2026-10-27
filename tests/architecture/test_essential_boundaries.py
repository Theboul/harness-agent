"""Architecture guard of the essential context (HU-02-06.1 / T010).

* ``core/context/essential.py`` and ``renewer.py`` are pure: standard library and the core only,
  no I/O, no environment, no terminal, nothing from the loop, the adapters, the CLI, the
  permissions, the tasks or the verification;
* the renewer never catches ``BaseException`` or ``CancelledError`` and nothing in the two
  modules is asynchronous;
* the SQLite store uses the connection of the session store, never one of its own, does not import
  the loop and does not define the ``SessionStore`` port;
* **only the composition root renews the block**: the renewer is named and called nowhere else in
  ``src/`` (not by the loop, the verification, the CLI nor the compactor).

Each rule is proved on the real files and on a mutated copy that breaks it. The detectors of the
other guards are reused, not copied.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_approvals_boundaries import catches_cancellation, imported_modules
from tests.architecture.test_compaction_boundaries import (
    defines_the_port,
    forbidden_context_imports,
    mutate,
    own_connections,
)
from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
ESSENTIAL = SRC / "core" / "context" / "essential.py"
RENEWER = SRC / "core" / "context" / "renewer.py"
STORE = SRC / "adapters" / "storage" / "essential_store.py"
PURE = (ESSENTIAL, RENEWER)
PACKAGE = "harness_agent.core.context"
MAY_NAME_THE_RENEWER = {
    SRC / "bootstrap.py",
    RENEWER,
    SRC / "core" / "context" / "__init__.py",
    SRC / "core" / "__init__.py",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- detectors --------------------------------------------------------------------------------


def purity_problems(source: str, name: str) -> list[str]:
    problems = [f"{m}" for m in forbidden_imports(source)]
    problems += io_stdlib_imports(source)
    problems += find_config_reads(source, name, PACKAGE)
    problems += terminal_uses(source)
    problems += forbidden_context_imports(source)
    return problems


def asynchronous(source: str) -> list[int]:
    """Lines of ``async def`` and ``await``: the two modules are plain synchronous code."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.AsyncFunctionDef | ast.Await)
    ]


def renewer_uses(source: str) -> list[int]:
    """Lines that name ``EssentialRenewer`` or call a method called ``renew``."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id == "EssentialRenewer":
            lines.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr in ("EssentialRenewer", "renew"):
            lines.append(node.lineno)
        elif isinstance(node, ast.alias) and node.name == "EssentialRenewer":
            lines.append(node.lineno)
    return lines


# --- the real files ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", PURE, ids=lambda p: p.name)
def test_the_pure_modules_only_use_the_standard_library_and_the_core(path: Path) -> None:
    assert purity_problems(read(path), path.name) == []


def test_the_renewer_never_catches_cancellation() -> None:
    assert catches_cancellation(read(RENEWER)) == []


@pytest.mark.parametrize("path", PURE, ids=lambda p: p.name)
def test_nothing_in_the_pure_modules_is_asynchronous(path: Path) -> None:
    assert asynchronous(read(path)) == []


def test_the_store_uses_the_connection_of_the_session_store() -> None:
    source = read(STORE)

    assert own_connections(source) == []
    assert "harness_agent.core.loop" not in imported_modules(source)
    assert defines_the_port(source) == []
    assert ".connection()" in source


def test_only_the_composition_root_names_or_calls_the_renewer() -> None:
    offenders = {
        str(path.relative_to(SRC)): renewer_uses(read(path))
        for path in sorted(SRC.rglob("*.py"))
        if path not in MAY_NAME_THE_RENEWER and renewer_uses(read(path))
    }

    assert offenders == {}


def test_the_composition_root_does_call_it() -> None:
    assert renewer_uses(read(SRC / "bootstrap.py"))


# --- the mutations: each rule fails on a copy that breaks it ----------------------------------


def test_a_renewer_that_catches_cancellation_is_flagged() -> None:
    source = read(RENEWER)

    for broken in ("except BaseException:", "except:", "except asyncio.CancelledError:"):
        mutated = mutate(source, "        except Exception:\n", f"        {broken}\n")
        assert catches_cancellation(mutated) != [], broken


def test_an_asynchronous_renewer_is_flagged() -> None:
    source = read(RENEWER)

    assert asynchronous(mutate(source, "    def renew(", "    async def renew(")) != []
    assert asynchronous(source + "\n\nasync def x() -> None:\n    await y()\n") != []


@pytest.mark.parametrize(
    "line",
    [
        "from harness_agent.core.loop import AgentLoop\n",
        "from harness_agent.adapters.storage import SqliteSessionStore\n",
        "from harness_agent.cli import run_cli\n",
        "from harness_agent.core.permissions import PermissionRules\n",
        "from harness_agent.core.tasks import TaskDefinition\n",
        "from harness_agent.core.verification import CriteriaVerifier\n",
        "from harness_agent.core.interfaces import TaskCriteria\n",
        "import sqlite3\n",
        "import os\nos.environ['X']\n",
        "print('hola')\n",
        "import litellm\n",
    ],
    ids=[
        "loop",
        "adapters",
        "cli",
        "permissions",
        "tasks",
        "verification",
        "TaskCriteria",
        "sqlite",
        "environment",
        "terminal",
        "sdk",
    ],
)
def test_the_forbidden_imports_and_uses_of_the_pure_modules_are_flagged(line: str) -> None:
    assert purity_problems(line + read(RENEWER), "renewer.py") != []


def test_a_store_that_opens_its_own_connection_or_defines_the_port_is_flagged() -> None:
    source = read(STORE)

    assert own_connections(source + "\n\ndef x() -> None:\n    sqlite3.connect('x')\n") != []
    assert own_connections("from sqlite3 import connect\n" + source) != []
    assert defines_the_port(source + "\n\nclass SessionStore:\n    pass\n") != []
    assert "harness_agent.core.loop" in imported_modules(
        "from harness_agent.core.loop import AgentLoop\n" + source
    )


def test_a_module_other_than_the_composition_root_that_renews_is_flagged() -> None:
    from_the_loop = (
        "from harness_agent.core import EssentialRenewer\n"
        "def run(renewer: EssentialRenewer, history: list) -> None:\n"
        "    renewer.renew(history)\n"
    )

    assert renewer_uses(from_the_loop) != []
    assert renewer_uses("def run(x) -> None:\n    x.renew([])\n") != []
    assert renewer_uses("import harness_agent.core as core\ncore.EssentialRenewer\n") != []
    assert renewer_uses("x = 1\n") == []
