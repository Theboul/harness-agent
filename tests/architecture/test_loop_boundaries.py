"""AST guards for the agentic loop module (HU-01-01, T028).

``core/loop.py`` must stay a pure core module: stdlib plus ``harness_agent.core`` only, no
console output, ``LIMIT_REACHED`` only from one method (HU-01-06), only the agreed limit
parameters and no cycles with the rest of the core. The guards are exercised against
in-memory samples too, so we know they would fail if the rule were broken.
"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path

from harness_agent.core.loop import AgentLoop
from tests.architecture.test_core_boundaries import FORBIDDEN_PACKAGES

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core"
LOOP_FILE = CORE_DIR / "loop.py"
FORBIDDEN_LAYERS = {"adapters", "cli", "observability"}
# HU-05-03 lets the loop publish the two approval events; HU-01-06 lets it publish LIMIT_REACHED,
# but only from the method that checks the limits before a call to the model.
LIMIT_EVENT = "LIMIT_REACHED"
LIMIT_METHOD = "_stop_at_limit"
LIMIT_PARAMETERS = {"limits", "clock"}
APPROVAL_EVENTS = {"APPROVAL_REQUESTED", "APPROVAL_RESOLVED"}
LIMIT_WORDS = ("limit", "max_", "turns", "iterations", "budget")


def console_uses(source: str) -> list[str]:
    """Return console-writing constructs found in ``source``."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"print", "input"}:
                found.append(f"{node.func.id}() at line {node.lineno}")
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "sys"
            and node.attr in {"stdout", "stderr", "stdin"}
        ):
            found.append(f"sys.{node.attr} at line {node.lineno}")
    return found


def forbidden_imports(source: str) -> list[str]:
    """Return imports that are neither stdlib nor ``harness_agent.core`` (or are forbidden)."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules = [node.module]
        for module in modules:
            top = module.split(".")[0]
            if top in FORBIDDEN_PACKAGES:
                found.append(f"{module} (vendor SDK)")
            elif top == "harness_agent":
                parts = module.split(".")
                if len(parts) < 2 or parts[1] != "core" or parts[1] in FORBIDDEN_LAYERS:
                    found.append(f"{module} (outside harness_agent.core)")
            elif top not in sys.stdlib_module_names and top != "__future__":
                found.append(f"{module} (third party)")
    return found


def forbidden_event_uses(source: str) -> list[str]:
    """Return uses of ``LIMIT_REACHED`` outside the one method allowed to publish it."""
    found: list[str] = []

    def visit(node: ast.AST, function: str | None) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node.name
        if (
            isinstance(node, ast.Attribute)
            and node.attr == LIMIT_EVENT
            and function != LIMIT_METHOD
        ):
            found.append(f"EventType.{node.attr} at line {node.lineno}")
        for child in ast.iter_child_nodes(node):
            visit(child, function)

    visit(ast.parse(source), None)
    return found


def test_loop_module_never_writes_to_the_console() -> None:
    assert console_uses(LOOP_FILE.read_text(encoding="utf-8")) == []


def test_loop_module_only_imports_stdlib_and_core() -> None:
    assert forbidden_imports(LOOP_FILE.read_text(encoding="utf-8")) == []


def test_loop_module_publishes_the_limit_event_only_from_the_limit_check() -> None:
    assert forbidden_event_uses(LOOP_FILE.read_text(encoding="utf-8")) == []


def test_loop_module_publishes_both_approval_events() -> None:
    source = LOOP_FILE.read_text(encoding="utf-8")
    used = {
        node.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
        if node.value.id == "EventType"
    }
    assert APPROVAL_EVENTS <= used


def test_loop_publishes_the_limit_event_from_the_limit_check() -> None:
    source = LOOP_FILE.read_text(encoding="utf-8")
    assert LIMIT_METHOD in source
    assert f"EventType.{LIMIT_EVENT}" in source


def test_the_only_limit_parameters_are_the_agreed_ones() -> None:
    init = inspect.signature(AgentLoop.__init__).parameters
    names = [*init, *inspect.signature(AgentLoop.run_turn).parameters]
    limit_like = {n for n in names if any(word in n.lower() for word in LIMIT_WORDS)}
    assert limit_like == {"limits"}
    # Keyword-only and optional: code written before HU-01-06 keeps working unchanged.
    for name in LIMIT_PARAMETERS:
        assert init[name].kind is inspect.Parameter.KEYWORD_ONLY
        assert init[name].default is None


def test_no_other_core_module_imports_the_loop_so_there_is_no_cycle() -> None:
    importers = []
    for path in CORE_DIR.rglob("*.py"):
        if path == LOOP_FILE:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "harness_agent.core.loop":
                importers.append(path.name)
            if isinstance(node, ast.Import):
                importers += [path.name for a in node.names if a.name == "harness_agent.core.loop"]
    assert importers == []


# ----------------------------------------- the guards fail when the rule is broken


def test_guards_detect_console_output_in_samples() -> None:
    assert console_uses("print('x')")
    assert console_uses("import sys\nsys.stdout.write('x')")
    assert console_uses("value = input()")
    assert console_uses("def ok() -> int:\n    return 1") == []


def test_guards_detect_forbidden_imports_in_samples() -> None:
    assert forbidden_imports("import openai")
    assert forbidden_imports("from litellm import completion")
    assert forbidden_imports("from harness_agent.adapters.converters import x")
    assert forbidden_imports("import requests")
    assert (
        forbidden_imports("import asyncio\nfrom harness_agent.core.entities import Message") == []
    )


def test_guards_detect_forbidden_events_in_samples() -> None:
    assert forbidden_event_uses("EventType.LIMIT_REACHED")
    assert forbidden_event_uses("def other():\n    x = EventType.LIMIT_REACHED")
    assert forbidden_event_uses("def _stop_at_limit():\n    x = EventType.LIMIT_REACHED") == []
    assert forbidden_event_uses("EventType.APPROVAL_REQUESTED") == []
    assert forbidden_event_uses("EventType.TOOL_FINISHED") == []


# ----------------------------------------- Q4: no except swallows a bus failure (T019 / T035)


def emits_guarded_by_try(source: str) -> list[tuple[str, int]]:
    """Return (function, line) of ``emit`` calls placed in the body of a ``try`` statement.

    An ``emit`` call inside an ``except`` handler is fine (it is not guarded by that handler);
    one inside the ``try`` body would let a bus failure be caught by it.
    """
    found: list[tuple[str, int]] = []
    for function in ast.walk(ast.parse(source)):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(function):
            if not isinstance(node, ast.Try):
                continue
            for statement in node.body:
                for inner in ast.walk(statement):
                    if (
                        isinstance(inner, ast.Call)
                        and isinstance(inner.func, ast.Attribute)
                        and inner.func.attr in {"emit", "_emit"}
                    ):
                        found.append((function.name, inner.lineno))
    return found


def test_only_the_r08_interruption_publisher_guards_a_bus_emit_with_a_try() -> None:
    """Q4 stays intact: an ordinary ``emit`` failure is never caught; R-08 is the one exception."""
    guarded = emits_guarded_by_try(LOOP_FILE.read_text(encoding="utf-8"))

    assert {function for function, _ in guarded} == {"_publish_interruption"}


def test_the_try_guard_detects_a_swallowed_emit_in_samples() -> None:
    swallowed = "def f(bus):\n    try:\n        bus.emit(1)\n    except Exception:\n        pass\n"
    in_handler = "def f(bus):\n    try:\n        pass\n    except Exception:\n        bus.emit(1)\n"

    assert emits_guarded_by_try(swallowed) == [("f", 3)]
    assert emits_guarded_by_try(in_handler) == []
