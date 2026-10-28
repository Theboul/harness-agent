"""Architecture guard of the resumable conversation (HU-03-04 / T011).

* ``core/context/conversation.py`` and ``resume.py`` are pure: standard library and the core only,
  no I/O, no environment, no terminal, nothing from the loop, the adapters, the CLI, the
  permissions, the tasks or the verification;
* nothing in them is asynchronous and they never catch ``BaseException`` or ``CancelledError``;
* the SQLite store uses the connection of the session store, never one of its own, does not import
  the loop and does not define the ``SessionStore`` port;
* **only the composition root** builds the capture of messages and resumes a session;
* in ``bootstrap.py`` the capture is subscribed **before** the event recorder (a message is saved
  before its event) and nothing inside ``run_session`` reads ``composition.session_id`` except to
  start (a session that was left is never written again);
* the CLI gained nothing but ``argument_commands``.

Each rule is proved on the real files and on a mutated copy that breaks it. The detectors of the
other guards are reused, not copied.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from harness_agent.cli import run_cli
from tests.architecture.test_approvals_boundaries import catches_cancellation, imported_modules
from tests.architecture.test_compaction_boundaries import (
    defines_the_port,
    mutate,
    own_connections,
)
from tests.architecture.test_essential_boundaries import asynchronous, purity_problems

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
CONVERSATION = SRC / "core" / "context" / "conversation.py"
RESUME = SRC / "core" / "context" / "resume.py"
STORE = SRC / "adapters" / "storage" / "message_store.py"
BOOTSTRAP = SRC / "bootstrap.py"
PURE = (CONVERSATION, RESUME)
NAMES = ("ConversationCapture", "resume_session")
MAY_NAME_THEM = {
    BOOTSTRAP,
    CONVERSATION,
    RESUME,
    SRC / "core" / "context" / "__init__.py",
    SRC / "core" / "__init__.py",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- detectors --------------------------------------------------------------------------------


def uses_of(source: str, names: tuple[str, ...]) -> list[int]:
    """Lines that name one of ``names`` (as a name, an attribute or an import)."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id in names:
            lines.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr in names:
            lines.append(node.lineno)
        elif isinstance(node, ast.alias) and node.name in names:
            lines.append(node.lineno)
    return lines


def subscription_order(source: str) -> tuple[int, int] | None:
    """Lines of the first subscription of a capture and of the event recorder, if both exist."""
    capture: list[int] = []
    recorder: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "attach_event_recorder":
            recorder.append(node.lineno)
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "subscribe":
            if any(isinstance(a, ast.Attribute) and a.attr == "on_event" for a in node.args):
                capture.append(node.lineno)
    if not capture or not recorder:
        return None
    return min(capture), min(recorder)


def reads_composition_session(source: str, functions: tuple[str, ...]) -> list[int]:
    """Lines where a function nested in ``functions`` reads ``composition.session_id``."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in functions:
            for inner in ast.walk(node):
                if inner is node or not isinstance(inner, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                for leaf in ast.walk(inner):
                    if (
                        isinstance(leaf, ast.Attribute)
                        and leaf.attr == "session_id"
                        and isinstance(leaf.value, ast.Name)
                        and leaf.value.id == "composition"
                    ):
                        lines.append(leaf.lineno)
    return lines


# --- the real files ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", PURE, ids=lambda p: p.name)
def test_the_pure_modules_only_use_the_standard_library_and_the_core(path: Path) -> None:
    assert purity_problems(read(path), path.name) == []


@pytest.mark.parametrize("path", PURE, ids=lambda p: p.name)
def test_nothing_in_the_pure_modules_is_asynchronous_or_catches_the_cancellation(
    path: Path,
) -> None:
    assert asynchronous(read(path)) == []
    assert catches_cancellation(read(path)) == []


def test_the_store_uses_the_connection_of_the_session_store() -> None:
    source = read(STORE)

    assert own_connections(source) == []
    assert "harness_agent.core.loop" not in imported_modules(source)
    assert defines_the_port(source) == []
    assert ".connection()" in source


def test_only_the_composition_root_builds_the_capture_and_resumes() -> None:
    offenders = {
        str(path.relative_to(SRC)): uses_of(read(path), NAMES)
        for path in sorted(SRC.rglob("*.py"))
        if path not in MAY_NAME_THEM and uses_of(read(path), NAMES)
    }

    assert offenders == {}
    assert uses_of(read(BOOTSTRAP), NAMES)


def test_the_capture_is_subscribed_before_the_event_recorder() -> None:
    order = subscription_order(read(BOOTSTRAP))

    assert order is not None and order[0] < order[1]


def test_nothing_inside_run_session_reads_the_session_of_the_composition() -> None:
    source = read(BOOTSTRAP)

    assert reads_composition_session(source, ("run_session", "_resume_command")) == []


def test_the_cli_gained_only_the_argument_commands() -> None:
    parameters = list(inspect.signature(run_cli).parameters)

    assert parameters == [
        "bus",
        "run_turn",
        "input_stream",
        "output",
        "commands",
        "argument_commands",
    ]


# --- the mutations: each rule fails on a copy that breaks it ----------------------------------


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
@pytest.mark.parametrize("path", PURE, ids=lambda p: p.name)
def test_the_forbidden_imports_and_uses_of_the_pure_modules_are_flagged(
    path: Path, line: str
) -> None:
    assert purity_problems(line + read(path), path.name) != []


def test_a_capture_that_catches_cancellation_or_is_asynchronous_is_flagged() -> None:
    source = read(CONVERSATION)

    for broken in ("except BaseException:", "except:", "except asyncio.CancelledError:"):
        assert (
            catches_cancellation(
                mutate(source, "        except Exception:\n", f"        {broken}\n")
            )
            != []
        )
    assert asynchronous(mutate(source, "    def flush(", "    async def flush(")) != []


def test_a_store_that_opens_its_own_connection_or_defines_the_port_is_flagged() -> None:
    source = read(STORE)

    assert own_connections(source + "\n\ndef x() -> None:\n    sqlite3.connect('x')\n") != []
    assert own_connections("from sqlite3 import connect\n" + source) != []
    assert defines_the_port(source + "\n\nclass SessionStore:\n    pass\n") != []
    assert "harness_agent.core.loop" in imported_modules(
        "from harness_agent.core.loop import AgentLoop\n" + source
    )


def test_a_module_other_than_the_composition_root_that_builds_or_resumes_is_flagged() -> None:
    assert uses_of("from harness_agent.core import ConversationCapture\n", NAMES) != []
    assert uses_of("def f(x) -> None:\n    resume_session(x)\n", NAMES) != []
    assert uses_of("import harness_agent.core as core\ncore.ConversationCapture\n", NAMES) != []
    assert uses_of("x = 1\n", NAMES) == []


def test_a_subscription_after_the_recorder_is_flagged() -> None:
    right = "attach_event_recorder(bus, store)\n"
    wrong = "attach_event_recorder(bus, store)\nbus.subscribe(kind, capture.on_event)\n"
    ok = "bus.subscribe(kind, capture.on_event)\nattach_event_recorder(bus, store)\n"

    assert subscription_order(ok) == (1, 2)
    order = subscription_order(wrong)
    assert order is not None and order[0] > order[1]
    assert subscription_order(right) is None
    mutated = mutate(
        read(BOOTSTRAP),
        "bus.subscribe(kind, capture.on_event)",
        "pass",
    )
    assert subscription_order(mutated) is None


def test_reading_the_session_of_the_composition_inside_run_session_is_flagged() -> None:
    mutated = mutate(
        read(BOOTSTRAP),
        "session_id=active.session_id, task=task",
        "session_id=composition.session_id, task=task",
    )
    synthetic = (
        "def run_session(composition):\n"
        "    async def run_turn(task):\n"
        "        return composition.session_id\n"
    )

    assert reads_composition_session(mutated, ("run_session",)) != []
    assert reads_composition_session(synthetic, ("run_session",)) != []
    assert (
        reads_composition_session(
            "def run_session(composition):\n    return composition.session_id\n", ("run_session",)
        )
        == []
    )
