"""Architecture guard of the traces of the calls (HU-10-01).

* ``core/tracing.py`` is pure: standard library and the core only, no I/O, no clock of its own, no
  environment, no terminal, nothing from the loop, the verification, the startup, the adapters or
  the CLI;
* **a trace never changes a call**: the only handler that swallows an error is the one of the sink
  and it catches ``Exception`` only (never ``BaseException``, a bare ``except`` or
  ``CancelledError``); the handlers of the wrappers re-raise and use the error only to name its
  class (``result_category``), never its text;
* **a trace holds metadata only**: the content of a response or of a result is read in two places
  (to count its characters and to read a ``[label]``), never an argument, a message or a tool call;
  no field of a trace is built from content, and the kind is always a constant;
* the composition root builds the wrappers only when the configuration leaves the traces on,
  and every loop (the child one with a provider and a registry of its own session) goes through
  them;
* the SQLite store uses the connection of the session store, never one of its own, and the DDL of
  the trace table has no foreign key and no ``CHECK``.

Each rule is proved on the real files and on a mutated copy that breaks it. The detectors of the
other guards are reused, not copied.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_approvals_boundaries import catches_cancellation, imported_modules
from tests.architecture.test_audit_boundaries import (
    constructions,
    ddl_problems,
    find_class,
    inner_layer_imports,
    purity_problems,
    with_parents,
)
from tests.architecture.test_compaction_boundaries import mutate, own_connections

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
TRACING = SRC / "core" / "tracing.py"
BOOTSTRAP = SRC / "bootstrap.py"
STORE = SRC / "adapters" / "storage" / "trace_store.py"
SCHEMA = SRC / "adapters" / "storage" / "_schema.py"
CONTENT_READERS = {"_tool_outcome", "_trace"}
FORBIDDEN_ATTRIBUTES = {"arguments", "tool_calls", "messages"}
METADATA_FIELDS = (
    "session_id",
    "kind",
    "name",
    "started_at",
    "duration_ms",
    "input_tokens",
    "output_tokens",
    "result",
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --- detectors --------------------------------------------------------------------------------


def handlers(source: str) -> list[ast.ExceptHandler]:
    return [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ExceptHandler)]


def swallowing_handlers(source: str) -> list[int]:
    """Lines of handlers that do not re-raise: they swallow the error."""
    return [
        handler.lineno
        for handler in handlers(source)
        if not any(isinstance(child, ast.Raise) for child in ast.walk(handler))
    ]


def error_uses_beyond_the_class_name(source: str) -> list[int]:
    """Lines where a bound error is used other than as the argument of ``result_category``."""
    found: list[int] = []
    for handler in handlers(source):
        if handler.name is None:
            continue
        allowed: set[int] = set()
        for node in ast.walk(handler):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "result_category"
            ):
                allowed |= {id(argument) for argument in node.args}
        found += [
            node.lineno
            for node in ast.walk(handler)
            if isinstance(node, ast.Name) and node.id == handler.name and id(node) not in allowed
        ]
    return found


def attribute_readers(source: str, attribute: str) -> set[str]:
    """The names of the functions that read ``.<attribute>`` (``<module>`` outside any)."""
    found: set[str] = set()

    def visit(node: ast.AST, owner: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = (
                child.name if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) else owner
            )
            if isinstance(child, ast.Attribute) and child.attr == attribute:
                found.add(owner)
            visit(child, name)

    visit(ast.parse(source), "<module>")
    return found


def trace_record_calls(source: str) -> list[dict[str, str]]:
    return [
        {keyword.arg: ast.unparse(keyword.value) for keyword in node.keywords if keyword.arg}
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "TraceRecord"
    ]


def fields_built_from_content(source: str) -> list[str]:
    """Metadata fields whose expression mentions content, arguments or messages."""
    found: list[str] = []
    for fields in trace_record_calls(source):
        for name in METADATA_FIELDS:
            text = fields.get(name, "")
            if any(word in text for word in ("content", "arguments", "messages", "tool_calls")):
                found.append(name)
        size = fields.get("size", "")
        if not (size == "size" or size.startswith("len(")):
            found.append("size")
    return found


def kinds_that_are_not_constants(source: str) -> list[str]:
    return [
        fields["kind"]
        for fields in trace_record_calls(source)
        if not (fields["kind"].startswith("'") or fields["kind"].startswith('"'))
    ]


def names_that_skip_the_redactor(source: str) -> list[str]:
    return [
        fields["name"] for fields in trace_record_calls(source) if "_redact" not in fields["name"]
    ]


def calls_outside_a_traces_switch(source: str, names: tuple[str, ...]) -> list[int]:
    """Lines where one of ``names`` is built outside an ``if`` on ``config.traces.enabled``."""
    found: list[int] = []
    for node, chain in with_parents(source):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in names
            and not any(
                isinstance(parent, ast.If) and "config.traces.enabled" in ast.unparse(parent.test)
                for parent in chain
            )
        ):
            found.append(node.lineno)
    return found


def loops_with_a_bare_provider_or_registry(source: str) -> list[str]:
    """``AgentLoop(...)`` calls whose provider is neither the traced one nor built per session, or
    whose registry is not built per session. The child loop must use ``provider_for``."""
    problems: list[str] = []
    for node, chain in with_parents(source):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "AgentLoop"
        ):
            provider, registry = (ast.unparse(argument) for argument in node.args[:2])
            inside_child = any(
                isinstance(parent, ast.AsyncFunctionDef) and parent.name == "run_child"
                for parent in chain
            )
            if not registry.startswith("registry_for("):
                problems.append(f"registry {registry}")
            if inside_child and not provider.startswith("provider_for("):
                problems.append(f"child provider {provider}")
            if not inside_child and provider != "provider":
                problems.append(f"loop provider {provider}")
    return problems


# --- the real files ---------------------------------------------------------------------------


def test_the_tracing_module_only_uses_the_standard_library_and_the_core() -> None:
    assert purity_problems(read(TRACING), TRACING.name) == []


def test_only_the_sink_swallows_an_error_and_it_catches_exception_only() -> None:
    source = read(TRACING)

    sink = find_class(source, "TraceSink")
    swallowing = swallowing_handlers(source)
    assert len(swallowing) == 1 and sink.lineno < swallowing[0] <= (sink.end_lineno or 0)
    assert catches_cancellation(source) == []
    assert "except Exception:" in ast.get_source_segment(source, sink)  # type: ignore[operator]


def test_the_wrappers_use_a_caught_error_only_to_name_its_class() -> None:
    assert error_uses_beyond_the_class_name(read(TRACING)) == []


def test_content_is_read_in_two_places_and_never_an_argument_a_message_or_a_tool_call() -> None:
    source = read(TRACING)

    assert attribute_readers(source, "content") == CONTENT_READERS
    for attribute in FORBIDDEN_ATTRIBUTES:
        assert attribute_readers(source, attribute) == set()


def test_no_field_of_a_trace_is_built_from_content_and_its_text_fields_are_cleaned() -> None:
    source = read(TRACING)

    assert len(trace_record_calls(source)) == 2
    assert fields_built_from_content(source) == []
    assert kinds_that_are_not_constants(source) == []
    assert names_that_skip_the_redactor(source) == []


def test_the_trace_table_has_no_foreign_key_and_no_check() -> None:
    assert ddl_problems(read(SCHEMA), "_V7") == []


def test_the_trace_store_uses_the_connection_of_the_session_store() -> None:
    source = read(STORE)

    assert own_connections(source) == []
    assert ".connection()" in source
    for module in imported_modules(source):
        assert not module.startswith(("harness_agent.core.loop", "harness_agent.cli"))


def test_the_wrappers_are_built_only_under_the_traces_switch() -> None:
    source = read(BOOTSTRAP)

    assert constructions(source, "TracingProvider") != []
    assert constructions(source, "TracingRegistry") != []
    assert calls_outside_a_traces_switch(source, ("TracingProvider", "TracingRegistry")) == []


def test_every_loop_gets_a_registry_built_per_session_and_the_child_a_provider_of_its_own() -> None:
    assert loops_with_a_bare_provider_or_registry(read(BOOTSTRAP)) == []


# --- the mutations: each rule fails on a copy that breaks it ----------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "from harness_agent.core.loop import AgentLoop\n",
        "from harness_agent.core.verification import CriteriaVerifier\n",
        "from harness_agent.core.startup import StartupRoutine\n",
        "from harness_agent.adapters.storage import SqliteTraceStore\n",
        "from harness_agent.cli import run_cli\n",
        "from harness_agent.config import load_config\n",
        "import sqlite3\n",
        "import time\n",
        "import os\n",
        "import pathlib\n",
    ],
)
def test_a_tracing_module_that_imports_what_it_must_not_is_flagged(line: str) -> None:
    mutated = mutate(read(TRACING), "from __future__ import annotations\n", f"{line}\n")

    assert purity_problems(mutated, TRACING.name) != []


def test_the_inner_layer_detector_sees_the_loop() -> None:
    assert inner_layer_imports("from harness_agent.core.loop import AgentLoop\n") != []
    assert "harness_agent.core.audit" in imported_modules(read(TRACING))


def test_a_tracing_module_that_reads_the_environment_or_prints_is_flagged() -> None:
    source = read(TRACING)

    assert purity_problems(source + '\nHOME_DIR = os.environ["X"]\n', TRACING.name) != []
    assert purity_problems(source + '\nprint("x")\n', TRACING.name) != []


@pytest.mark.parametrize("broken", ["except BaseException:", "except:", "except CancelledError:"])
def test_a_sink_that_catches_cancellation_is_flagged(broken: str) -> None:
    mutated = mutate(
        read(TRACING),
        "        except Exception:\n            if not self._warned:",
        f"        {broken}\n            if not self._warned:",
    )

    assert catches_cancellation(mutated) != []


def test_a_wrapper_that_swallows_the_error_of_the_call_is_flagged() -> None:
    mutated = mutate(
        read(TRACING),
        '        except Exception:\n            result = "error"\n            raise\n',
        '        except Exception:\n            result = "error"\n',
    )

    assert len(swallowing_handlers(mutated)) == 2


def test_a_wrapper_that_keeps_the_text_of_the_error_is_flagged() -> None:
    mutated = mutate(read(TRACING), "result = result_category(error)", "result = str(error)")

    assert error_uses_beyond_the_class_name(mutated) != []


def test_a_wrapper_that_reads_the_arguments_a_message_or_the_tool_calls_is_flagged() -> None:
    for attribute, anchor in (
        (
            "arguments",
            "        started = self._clock()\n"
            "        begin = self._monotonic()\n"
            "        result, size",
        ),
        (
            "messages",
            "        started = self._clock()\n        begin = self._monotonic()\n        result = ",
        ),
    ):
        mutated = mutate(read(TRACING), anchor, f"        leak = args.{attribute}\n" + anchor)
        assert attribute_readers(mutated, attribute) != set()


def test_a_response_whose_content_is_read_outside_the_two_places_is_flagged() -> None:
    mutated = mutate(
        read(TRACING),
        "            response = await self._inner.complete(messages, tools)\n",
        "            response = await self._inner.complete(messages, tools)\n"
        "            leak = response.content\n",
    )

    assert attribute_readers(mutated, "content") != CONTENT_READERS


@pytest.mark.parametrize(
    "broken",
    [
        (
            "result=result,\n            size=len(content) if isinstance(content, str) else 0,",
            "result=content,\n            size=len(content) if isinstance(content, str) else 0,",
        ),
        ("size=len(content) if isinstance(content, str) else 0,", "size=content,"),
        (
            'session_id=self._session(),\n            kind="modelo",',
            'session_id=str(content),\n            kind="modelo",',
        ),
    ],
)
def test_a_trace_field_built_from_content_is_flagged(broken: tuple[str, str]) -> None:
    mutated = mutate(read(TRACING), *broken)

    assert fields_built_from_content(mutated) != []


def test_a_trace_whose_kind_or_name_is_not_a_constant_or_cleaned_is_flagged() -> None:
    kind = mutate(read(TRACING), 'kind="modelo",', "kind=str(content),")
    name = mutate(
        read(TRACING),
        "name=_bounded(str(self._redact(self._model()))),",
        "name=_bounded(str(self._model())),",
    )

    assert kinds_that_are_not_constants(kind) != []
    assert names_that_skip_the_redactor(name) != []


@pytest.mark.parametrize(
    "broken",
    [
        "nombre          TEXT NOT NULL REFERENCES sessions(id),",
        "nombre          TEXT NOT NULL CHECK (length(nombre) > 0),",
    ],
)
def test_a_trace_table_with_a_foreign_key_or_a_check_is_flagged(broken: str) -> None:
    mutated = mutate(read(SCHEMA), "nombre          TEXT NOT NULL,", broken)

    assert ddl_problems(mutated, "_V7") != []


def test_a_trace_store_that_opens_its_own_connection_or_imports_the_loop_is_flagged() -> None:
    source = read(STORE)

    assert own_connections(source + "\nimport sqlite3\nconn = sqlite3.connect('x')\n") != []
    mutated = mutate(
        source,
        "from __future__ import annotations",
        "from harness_agent.core.loop import AgentLoop",
    )
    assert "harness_agent.core.loop" in imported_modules(mutated)


def test_a_wrapper_built_without_the_switch_is_flagged() -> None:
    mutated = mutate(
        read(BOOTSTRAP),
        "if config.traces.enabled and trace_sink is not None:",
        "if trace_sink is not None:",
    )

    assert calls_outside_a_traces_switch(mutated, ("TracingProvider", "TracingRegistry")) != []


def test_a_child_loop_without_its_own_traced_provider_or_registry_is_flagged() -> None:
    child_provider = "                    provider_for(lambda: session),\n"
    child_registry = (
        "                    registry_for(\n"
        "                        RegistryView(registry, {DELEGATE_TOOL_NAME, MEMORY_TOOL_NAME}),\n"
        "                        lambda: session,\n"
        "                    ),\n"
    )
    main_registry = "            registry_for(registry, lambda: cursor.value),\n"
    parent_provider = mutate(read(BOOTSTRAP), child_provider, "                    provider,\n")
    bare_registry = mutate(
        read(BOOTSTRAP),
        child_registry,
        "                    RegistryView(registry, {DELEGATE_TOOL_NAME, MEMORY_TOOL_NAME}),\n",
    )
    shared_registry = mutate(read(BOOTSTRAP), main_registry, "            registry,\n")

    assert loops_with_a_bare_provider_or_registry(parent_provider) != []
    assert loops_with_a_bare_provider_or_registry(bare_registry) != []
    assert loops_with_a_bare_provider_or_registry(shared_registry) != []
