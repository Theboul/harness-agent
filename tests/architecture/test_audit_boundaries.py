"""Architecture guard of the audit of decisions (HU-05-05).

* ``core/audit.py`` is pure: standard library and the core only, no I/O, no clock, no environment,
  no terminal, nothing from the loop, the verification, the startup, the adapters or the CLI;
* **the tap never decides**: ``ArgumentsTap.evaluate`` returns only what the policy inside returned,
  never names a ``PermissionDecision`` member and catches nothing (an exception of the policy
  rises as it is);
* **the audit fails closed**: the recorder has no ``except`` at all, so a failure of the log reaches
  the bus and the tool does not run;
* the arguments come only from the tap: the recorder never reads them from an event payload;
* the composition root wraps the policy once, last (every user of the policy goes through the
  tap) and subscribes the recorder to both events with no switch;
* the SQLite store uses the connection of the session store, never one of its own, and the DDL of
  the audit and trace tables (version 7) has no foreign key and no ``CHECK`` (the audit must survive
  anything);

Each rule is proved on the real files and on a mutated copy that breaks it. The detectors of the
other guards are reused, not copied.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_approvals_boundaries import catches_cancellation, imported_modules
from tests.architecture.test_compaction_boundaries import mutate, own_connections
from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
AUDIT = SRC / "core" / "audit.py"
BOOTSTRAP = SRC / "bootstrap.py"
STORE = SRC / "adapters" / "storage" / "audit_store.py"
SCHEMA = SRC / "adapters" / "storage" / "_schema.py"
PACKAGE = "harness_agent.core"
INNER_LAYERS = (
    "harness_agent.core.loop",
    "harness_agent.core.verification",
    "harness_agent.core.startup",
    "harness_agent.core.permissions",
    "harness_agent.core.tasks",
    "harness_agent.adapters",
    "harness_agent.cli",
    "harness_agent.config",
    "harness_agent.bootstrap",
)
CLOCKS_AND_FILES = {"time", "os", "sqlite3", "pathlib", "subprocess", "socket", "datetime.timezone"}
DECISION_MEMBERS = {"ALLOW", "ASK", "DENY"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- detectors --------------------------------------------------------------------------------


def stdlib_clocks_and_files(source: str) -> list[str]:
    """Imports that would let the module read a clock or touch the disk."""
    return [m for m in imported_modules(source) if m.split(".")[0] in CLOCKS_AND_FILES]


def inner_layer_imports(source: str) -> list[str]:
    return [m for m in imported_modules(source) if m.startswith(INNER_LAYERS)]


def purity_problems(source: str, name: str) -> list[str]:
    problems = [f"{m}" for m in forbidden_imports(source)]
    problems += io_stdlib_imports(source)
    problems += stdlib_clocks_and_files(source)
    problems += inner_layer_imports(source)
    problems += find_config_reads(source, name, PACKAGE)
    problems += terminal_uses(source)
    return problems


def find_class(source: str, name: str) -> ast.ClassDef:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"no class called {name}")


def find_method(source: str, class_name: str, method: str) -> ast.FunctionDef:
    for node in find_class(source, class_name).body:
        if isinstance(node, ast.FunctionDef) and node.name == method:
            return node
    raise AssertionError(f"no method {class_name}.{method}")


def decision_members_named(source: str) -> list[int]:
    """Lines that write ``PermissionDecision.ALLOW`` (or ASK or DENY)."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "PermissionDecision"
        and node.attr in DECISION_MEMBERS
    ]


def returns_of(function: ast.FunctionDef) -> list[str]:
    return [
        ast.unparse(node.value)
        for node in ast.walk(function)
        if isinstance(node, ast.Return) and node.value is not None
    ]


def handlers_in(node: ast.AST) -> list[int]:
    return [child.lineno for child in ast.walk(node) if isinstance(child, ast.ExceptHandler)]


def argument_reads(source: str) -> list[int]:
    """Lines where something reads ``"arguments"`` out of a mapping (``.get`` or ``[...]``)."""
    found: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "arguments"
        ):
            found.append(node.lineno)
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and node.slice.value == "arguments"
        ):
            found.append(node.lineno)
    return found


def ddl_problems(source: str, name: str) -> list[str]:
    """Foreign keys and ``CHECK`` constraints in the string constant ``name`` (a DDL)."""
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            upper = node.value.value.upper()
            return [word for word in ("REFERENCES", "CHECK", "FOREIGN KEY") if word in upper]
    raise AssertionError(f"no constant called {name}")


def with_parents(source: str) -> list[tuple[ast.AST, list[ast.AST]]]:
    """Every node with the chain of nodes that contain it, outermost first."""
    found: list[tuple[ast.AST, list[ast.AST]]] = []

    def visit(node: ast.AST, chain: list[ast.AST]) -> None:
        found.append((node, chain))
        for child in ast.iter_child_nodes(node):
            visit(child, [*chain, node])

    visit(ast.parse(source), [])
    return found


def policy_assignments(source: str) -> list[tuple[int, str]]:
    """Assignments to ``policy`` inside ``compose``: the line and the source of the value."""
    compose = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef) and node.name == "compose"
    )
    found: list[tuple[int, str]] = []
    for node in ast.walk(compose):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "policy" for target in node.targets
        ):
            found.append((node.lineno, ast.unparse(node.value)))
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "policy"
            and node.value is not None
        ):
            found.append((node.lineno, ast.unparse(node.value)))
    return sorted(found)


def constructions(source: str, name: str) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
    ]


def audit_subscriptions_under_a_condition(source: str) -> list[int]:
    """Lines where the audit recorder is subscribed inside an ``if`` (it must have no switch)."""
    found: list[int] = []
    for node, chain in with_parents(source):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "subscribe"
            and node.args
            and ast.unparse(node.args[0])
            in ("EventType.PERMISSION_DECIDED", "EventType.APPROVAL_RESOLVED")
            and any(isinstance(parent, ast.If) for parent in chain)
        ):
            found.append(node.lineno)
    return found


def audit_subscriptions(source: str) -> list[str]:
    return [
        ast.unparse(node.args[0])
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "subscribe"
        and node.args
        and ast.unparse(node.args[0])
        in ("EventType.PERMISSION_DECIDED", "EventType.APPROVAL_RESOLVED")
    ]


# --- the real files ---------------------------------------------------------------------------


def test_the_audit_module_only_uses_the_standard_library_and_the_core() -> None:
    assert purity_problems(read(AUDIT), AUDIT.name) == []


def test_the_tap_returns_only_what_the_policy_inside_returned() -> None:
    source = read(AUDIT)

    assert returns_of(find_method(source, "ArgumentsTap", "evaluate")) == [
        "self._inner.evaluate(call)"
    ]
    assert decision_members_named(source) == []


def test_the_tap_catches_nothing_and_the_recorder_has_no_handler_at_all() -> None:
    source = read(AUDIT)

    assert handlers_in(find_method(source, "ArgumentsTap", "evaluate")) == []
    assert handlers_in(find_class(source, "AuditRecorder")) == []
    assert catches_cancellation(source) == []


def test_the_recorder_never_reads_the_arguments_from_an_event() -> None:
    assert argument_reads(read(AUDIT)) == []


def test_the_audit_and_trace_tables_have_no_foreign_key_and_no_check() -> None:
    assert ddl_problems(read(SCHEMA), "_V7") == []


def test_the_other_tables_still_have_theirs_so_the_detector_can_see_one() -> None:
    assert ddl_problems(read(SCHEMA), "_V5") != []


def test_the_audit_store_uses_the_connection_of_the_session_store() -> None:
    source = read(STORE)

    assert own_connections(source) == []
    assert ".connection()" in source
    for module in imported_modules(source):
        assert not module.startswith(("harness_agent.core.loop", "harness_agent.cli"))


def test_the_policy_of_every_user_is_the_tap_and_it_is_built_once() -> None:
    source = read(BOOTSTRAP)

    assert len(constructions(source, "ArgumentsTap")) == 1
    assert policy_assignments(source)[-1][1] == "tap"


def test_the_audit_recorder_has_no_switch_and_listens_to_both_events() -> None:
    source = read(BOOTSTRAP)

    assert sorted(audit_subscriptions(source)) == [
        "EventType.APPROVAL_RESOLVED",
        "EventType.PERMISSION_DECIDED",
    ]
    assert audit_subscriptions_under_a_condition(source) == []


# --- the mutations: each rule fails on a copy that breaks it ----------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "from harness_agent.core.loop import AgentLoop\n",
        "from harness_agent.core.verification import CriteriaVerifier\n",
        "from harness_agent.core.startup import StartupRoutine\n",
        "from harness_agent.adapters.storage import SqliteAuditStore\n",
        "from harness_agent.cli import run_cli\n",
        "from harness_agent.config import load_config\n",
        "import sqlite3\n",
        "import time\n",
        "import os\n",
        "import pathlib\n",
    ],
)
def test_an_audit_module_that_imports_what_it_must_not_is_flagged(line: str) -> None:
    mutated = mutate(read(AUDIT), "from __future__ import annotations\n", f"{line}\n")

    assert purity_problems(mutated, AUDIT.name) != []


def test_an_audit_module_that_reads_the_environment_or_prints_is_flagged() -> None:
    source = read(AUDIT)

    assert purity_problems(source + '\nHOME_DIR = os.environ["X"]\n', AUDIT.name) != []
    assert purity_problems(source + '\nprint("x")\n', AUDIT.name) != []


@pytest.mark.parametrize(
    "broken",
    [
        "return PermissionDecision.ALLOW",
        "self._inner.evaluate(call)\n        return PermissionDecision.DENY",
        "decision = self._inner.evaluate(call)\n        return decision",
    ],
)
def test_a_tap_that_decides_by_itself_or_returns_something_else_is_flagged(broken: str) -> None:
    mutated = mutate(read(AUDIT), "return self._inner.evaluate(call)", broken)

    assert (
        returns_of(find_method(mutated, "ArgumentsTap", "evaluate"))
        != ["self._inner.evaluate(call)"]
        or decision_members_named(mutated) != []
    )


def test_a_tap_that_catches_the_exception_of_the_policy_is_flagged() -> None:
    mutated = mutate(
        read(AUDIT),
        "        return self._inner.evaluate(call)\n",
        "        try:\n            return self._inner.evaluate(call)\n"
        "        except Exception:\n            return self._inner.evaluate(call)\n",
    )

    assert handlers_in(find_method(mutated, "ArgumentsTap", "evaluate")) != []


@pytest.mark.parametrize("handler", ["except Exception:", "except BaseException:", "except:"])
def test_a_recorder_that_swallows_the_error_of_the_log_is_flagged(handler: str) -> None:
    mutated = mutate(
        read(AUDIT),
        "        self._log.record_decision(\n",
        "        try:\n            self._log.record_decision(\n",
    )
    mutated = mutate(
        mutated,
        "                decided_at=event.timestamp,\n            )\n        )\n",
        "                decided_at=event.timestamp,\n            )\n            )\n"
        f"        {handler}\n            pass\n",
    )

    assert handlers_in(find_class(mutated, "AuditRecorder")) != []


def test_a_recorder_that_reads_the_arguments_from_the_event_is_flagged() -> None:
    mutated = mutate(
        read(AUDIT),
        "arguments=NO_DATA if raw_id is None else self._tap.take(raw_id),",
        'arguments=str(payload.get("arguments")),',
    )

    assert argument_reads(mutated) != []


@pytest.mark.parametrize(
    "broken",
    [
        "herramienta   TEXT NOT NULL REFERENCES sessions(id),",
        "herramienta   TEXT NOT NULL CHECK (length(herramienta) > 0),",
    ],
)
def test_an_audit_table_with_a_foreign_key_or_a_check_is_flagged(broken: str) -> None:
    mutated = mutate(read(SCHEMA), "herramienta   TEXT NOT NULL,", broken)

    assert ddl_problems(mutated, "_V7") != []


def test_a_store_that_opens_its_own_connection_or_imports_the_loop_is_flagged() -> None:
    source = read(STORE)

    assert own_connections(source + "\nimport sqlite3\nconn = sqlite3.connect('x')\n") != []
    mutated = mutate(
        source,
        "from __future__ import annotations",
        "from harness_agent.core.loop import AgentLoop",
    )
    assert "harness_agent.core.loop" in imported_modules(mutated)


def test_a_policy_assigned_after_the_tap_is_flagged() -> None:
    after = "        policy = tap\n"
    mutated = mutate(
        read(BOOTSTRAP),
        after,
        after + "        policy = SwitchablePolicy(policy, policy, read_switch)\n",
    )

    assert policy_assignments(mutated)[-1][1] != "tap"


def test_a_second_tap_is_flagged() -> None:
    after = "        policy = tap\n"
    mutated = mutate(
        read(BOOTSTRAP), after, after + "        other = ArgumentsTap(policy, redactor.value)\n"
    )

    assert len(constructions(mutated, "ArgumentsTap")) == 2


def test_an_audit_recorder_behind_a_switch_or_for_one_event_only_is_flagged() -> None:
    decided = "        bus.subscribe(EventType.PERMISSION_DECIDED, audit_recorder.on_decided)\n"
    resolved = "        bus.subscribe(EventType.APPROVAL_RESOLVED, audit_recorder.on_resolved)\n"
    switched = mutate(
        read(BOOTSTRAP),
        decided,
        "        if config.traces.enabled:\n    " + decided,
    )
    partial = mutate(read(BOOTSTRAP), resolved, "")

    assert audit_subscriptions_under_a_condition(switched) != []
    assert audit_subscriptions(partial) == ["EventType.PERMISSION_DECIDED"]
