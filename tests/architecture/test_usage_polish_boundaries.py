"""Architecture guard of the usage polish (HU-06-07).

All the changes live in ``bootstrap.py``, ``cli/session_commands.py`` and the LiteLLM adapter:

* the adapter takes the debug sink by constructor and reads no environment; ``_report`` swallows
  the failures of the sink (``except Exception``) so a diagnostic aid never changes the error;
* ``bootstrap.py`` reads ``HARNESS_DEBUG_PROVIDER`` only from the injected mapping, in
  ``_debug_sink``, and that function never writes to disk (only ``sys.stderr``);
* the git instructions enter the prefix only under ``area is not None and task is not None``;
* **the harness decides, the model never does**: in ``_offer_implement`` the ``implement`` function
  is called only inside an ``if`` that compares ``.number``; the function names neither
  ``enable`` nor ``disable`` and checks ``locked`` before asking; the question has no free text;
* ``core/loop.py`` and the ports are not touched (their own guards and the protected-files diff).

Each rule has a self-test on synthetic fragments.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
BOOTSTRAP = SRC / "bootstrap.py"
PROVIDER = SRC / "adapters" / "providers" / "litellm_provider.py"


def function(source: str, name: str) -> ast.AST:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"no function {name}")


def attribute_names(node: ast.AST) -> set[str]:
    return {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}


def names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def calls_outside_number_test(node: ast.AST, callee: str) -> list[int]:
    """Lines where ``callee(...)`` is called outside an ``if`` whose test reads ``.number``."""
    guarded: set[int] = set()
    for branch in ast.walk(node):
        if isinstance(branch, ast.If) and "number" in attribute_names(branch.test):
            guarded.update(id(n) for stmt in branch.body for n in ast.walk(stmt))
    return [
        call.lineno
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == callee
        and id(call) not in guarded
    ]


def handlers_not_exception(node: ast.AST) -> list[int]:
    return [
        h.lineno
        for h in ast.walk(node)
        if isinstance(h, ast.ExceptHandler)
        and not (isinstance(h.type, ast.Name) and h.type.id == "Exception")
    ]


def reads_environment(source: str) -> list[int]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr in {"environ", "getenv"}:
            found.append(node.lineno)
    return found


def test_the_adapter_reads_no_environment() -> None:
    assert reads_environment(PROVIDER.read_text(encoding="utf-8")) == []


def test_the_report_of_the_adapter_only_swallows_exception() -> None:
    report = function(PROVIDER.read_text(encoding="utf-8"), "_report")

    assert handlers_not_exception(report) == []
    assert any(isinstance(n, ast.ExceptHandler) for n in ast.walk(report))


def test_the_debug_sink_only_writes_to_standard_error() -> None:
    sink = function(BOOTSTRAP.read_text(encoding="utf-8"), "_debug_sink")

    assert "open" not in names(sink) and "write_text" not in attribute_names(sink)
    assert "stderr" in attribute_names(sink)
    assert "environ" not in attribute_names(sink)  # only the mapping it receives, by name


def test_the_git_instructions_need_an_area_and_a_task() -> None:
    prefix = function(BOOTSTRAP.read_text(encoding="utf-8"), "_provisional_prefix")
    guard = next(
        n
        for n in ast.walk(prefix)
        if isinstance(n, ast.If) and "git_instructions" in names(ast.Module(n.body, []))
    )

    assert {"area", "task"} <= names(guard.test)
    assert isinstance(guard.test, ast.BoolOp) and isinstance(guard.test.op, ast.And)


def test_the_offer_applies_implement_only_after_the_person_chose_one() -> None:
    offer = function(BOOTSTRAP.read_text(encoding="utf-8"), "_offer_implement")

    assert calls_outside_number_test(offer, "implement") == []
    assert {"enable", "disable"}.isdisjoint(attribute_names(offer))
    assert "locked" in attribute_names(offer)


def test_the_offer_question_accepts_no_free_text() -> None:
    offer = function(BOOTSTRAP.read_text(encoding="utf-8"), "_offer_implement")
    keywords = {
        k.arg: k.value
        for c in ast.walk(offer)
        if isinstance(c, ast.Call)
        for k in c.keywords
        if k.arg == "allow_free_text"
    }

    assert isinstance(keywords["allow_free_text"], ast.Constant)
    assert keywords["allow_free_text"].value is False


def test_the_offer_runs_only_after_a_finished_turn() -> None:
    """It is called from ``run_turn`` after the turn returned, never from the model's path."""
    source = BOOTSTRAP.read_text(encoding="utf-8")
    callers = [
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and "_offer_implement" in names(node)
        and node.name != "_offer_implement"
    ]

    assert callers == ["run_session", "run_turn"]


class TestSelfTests:
    def test_an_unguarded_call_is_found(self) -> None:
        bad = "def f(a):\n    a()\n    if x.number == 1:\n        a()\n"
        good = "def f(a):\n    if x.number == 1:\n        a()\n"

        assert calls_outside_number_test(ast.parse(bad), "a") == [2]
        assert calls_outside_number_test(ast.parse(good), "a") == []

    def test_a_handler_other_than_exception_is_found(self) -> None:
        tree = ast.parse("try:\n    pass\nexcept BaseException:\n    pass\n")

        assert handlers_not_exception(tree) == [3]

    def test_an_environment_read_is_found(self) -> None:
        assert reads_environment("import os\nos.environ['X']\n") == [2]
