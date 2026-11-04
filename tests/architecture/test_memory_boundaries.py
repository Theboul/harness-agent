"""Architecture guard of the persistent memory (HU-04-01 and HU-04-02).

* ``core/context/memory.py`` and ``memory_loader.py`` are pure: standard library and the core only,
  no I/O (not even ``sqlite3``), no environment, no terminal, nothing from the loop, the adapters,
  the CLI, the permissions, the tasks or the verification;
* **the memory block is data, never an instruction**: ``memory.py`` builds a ``Message`` in one
  place, with the role ``USER`` and ``is_external=True``, and never a ``SYSTEM`` one; it does not
  touch the stable prefix;
* the loader only catches ``Exception`` (never ``BaseException``, a bare ``except`` or
  ``CancelledError``) and no handler binds the error it caught, so nothing of the store survives;
* the SQLite store uses the connection of the session store, never one of its own, and the DDL of
  the ``memorias`` table has no foreign key (deleting or compacting a session cannot touch it);
* the tool only stores what ``make_entry`` returned, and no handler of the tool binds the error;
* the composition root registers the tool only when the configuration turns the memory on, hides it
  from the subagents and does not load the block when a session is resumed.

Each rule is proved on the real files and on a mutated copy that breaks it. The detectors of the
other guards are reused, not copied.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_approvals_boundaries import catches_cancellation, imported_modules
from tests.architecture.test_compaction_boundaries import (
    forbidden_context_imports,
    mutate,
    own_connections,
)
from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_tasks_boundaries import io_stdlib_imports

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
MEMORY = SRC / "core" / "context" / "memory.py"
LOADER = SRC / "core" / "context" / "memory_loader.py"
STORE = SRC / "adapters" / "storage" / "memory_store.py"
SCHEMA = SRC / "adapters" / "storage" / "_schema.py"
TOOL = SRC / "adapters" / "tools" / "memoria.py"
BOOTSTRAP = SRC / "bootstrap.py"
PURE = (MEMORY, LOADER)
PACKAGE = "harness_agent.core.context"
TOOL_FORBIDDEN = (
    "sqlite3",
    "harness_agent.adapters.storage",
    "harness_agent.cli",
    "harness_agent.core.loop",
)


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


def messages_built(source: str) -> list[tuple[int, str, bool]]:
    """Every ``Message(...)`` call: its line, its role (``Role.X`` or ``?``) and ``is_external``."""
    found: list[tuple[int, str, bool]] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Message"
        ):
            role = "?"
            if node.args and isinstance(node.args[0], ast.Attribute):
                role = f"Role.{node.args[0].attr}"
            external = any(
                keyword.arg == "is_external"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in node.keywords
            )
            found.append((node.lineno, role, external))
    return found


def builds_only_external_user_messages(source: str) -> bool:
    built = messages_built(source)
    return bool(built) and all(role == "Role.USER" and external for _, role, external in built)


def handlers_that_bind(source: str) -> list[int]:
    """Lines of ``except ... as name`` handlers: they keep the error they caught."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ExceptHandler) and node.name is not None
    ]


def remember_calls(source: str) -> list[tuple[int, list[str]]]:
    """Every ``.remember(...)`` call: its line and the source text of each argument."""
    return [
        (node.lineno, [ast.unparse(argument) for argument in node.args])
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "remember"
    ]


def ddl_with_references(source: str, name: str) -> list[int]:
    """Lines of the string constant ``name`` (a DDL) that declare a foreign key."""
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return [
                node.lineno + number
                for number, line in enumerate(node.value.value.split("\n"))
                if "REFERENCES" in line.upper()
            ]
    raise AssertionError(f"no constant called {name}")


def memory_tool_calls_outside_the_switch(source: str) -> list[int]:
    """Lines where ``MemoryTool(...)`` is built outside ``if config.memory.enabled:``."""
    tree = ast.parse(source)
    inside: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and ast.unparse(node.test) == "config.memory.enabled":
            inside |= {id(child) for stmt in node.body for child in ast.walk(stmt)}
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "MemoryTool"
        and id(node) not in inside
    ]


def registry_views_that_hide_the_memory_tool(source: str) -> int:
    """How many ``RegistryView(...)`` calls name ``MEMORY_TOOL_NAME`` among the hidden tools."""
    return sum(
        1
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "RegistryView"
        and any(
            isinstance(child, ast.Name) and child.id == "MEMORY_TOOL_NAME"
            for argument in node.args
            for child in ast.walk(argument)
        )
    )


def functions_that_load_the_memory(source: str) -> set[str]:
    """The top-level functions with a ``.load_into(...)`` call anywhere inside them."""
    found: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and any(
            isinstance(child, ast.Attribute) and child.attr == "load_into"
            for child in ast.walk(node)
        ):
            found.add(node.name)
    return found


# --- the real files ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", [p for p in PURE if p.exists()], ids=lambda p: p.name)
def test_the_pure_modules_only_use_the_standard_library_and_the_core(path: Path) -> None:
    assert purity_problems(read(path), path.name) == []


def test_the_memory_block_is_built_only_as_external_user_content() -> None:
    source = read(MEMORY)

    assert builds_only_external_user_messages(source)
    assert len(messages_built(source)) == 1


def test_the_memory_never_touches_the_stable_prefix() -> None:
    assert "harness_agent.core.context.prefix" not in imported_modules(read(MEMORY))


def test_the_loader_never_catches_cancellation_and_keeps_no_error() -> None:
    source = read(LOADER)

    assert catches_cancellation(source) == []
    assert handlers_that_bind(source) == []
    assert "except Exception:" in source


def test_the_store_uses_the_connection_of_the_session_store() -> None:
    source = read(STORE)

    assert own_connections(source) == []
    assert ".connection()" in source
    for module in imported_modules(source):
        assert not module.startswith(("harness_agent.core.loop", "harness_agent.cli"))


def test_the_memory_table_has_no_foreign_key() -> None:
    assert ddl_with_references(read(SCHEMA), "_V6") == []


def test_the_other_tables_still_have_theirs_so_the_detector_can_see_one() -> None:
    assert ddl_with_references(read(SCHEMA), "_V5") != []


def test_the_tool_only_stores_what_the_cleaning_returned() -> None:
    calls = remember_calls(read(TOOL))

    assert [arguments for _, arguments in calls] == [["entry.key", "entry.content"]]


def test_the_tool_never_catches_cancellation_and_does_not_import_a_store_or_the_loop() -> None:
    source = read(TOOL)

    assert catches_cancellation(source) == []
    for module in imported_modules(source):
        assert not module.startswith(TOOL_FORBIDDEN)


def test_the_tool_is_built_only_when_the_configuration_turns_the_memory_on() -> None:
    source = read(BOOTSTRAP)

    assert "MemoryTool(" in source
    assert memory_tool_calls_outside_the_switch(source) == []


def test_the_subagents_get_a_registry_view_without_the_memory_tool() -> None:
    assert registry_views_that_hide_the_memory_tool(read(BOOTSTRAP)) == 1


def test_the_block_is_loaded_when_a_session_starts_and_on_new_never_on_resume() -> None:
    assert functions_that_load_the_memory(read(BOOTSTRAP)) == {"run_session", "_new_command"}


# --- the mutations: each rule fails on a copy that breaks it ----------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "from harness_agent.core.loop import AgentLoop\n",
        "from harness_agent.adapters.storage import SqliteSessionStore\n",
        "from harness_agent.cli import run_cli\n",
        "from harness_agent.config import load_config\n",
        "from harness_agent.core.permissions import DefaultPermissionPolicy\n",
        "from harness_agent.core.verification import CriteriaVerifier\n",
        "import sqlite3\n",
        "import pathlib\n",
        "import subprocess\n",
    ],
)
def test_a_memory_module_that_imports_what_it_must_not_is_flagged(line: str) -> None:
    mutated = mutate(read(MEMORY), "from __future__ import annotations\n", f"{line}\n")

    assert purity_problems(mutated, MEMORY.name) != []


def test_a_memory_module_that_reads_the_environment_or_prints_is_flagged() -> None:
    source = read(MEMORY)

    assert purity_problems(source + '\nHOME_DIR = os.environ["X"]\n', MEMORY.name) != []
    assert purity_problems(source + '\nprint("x")\n', MEMORY.name) != []


@pytest.mark.parametrize(
    "broken",
    [
        "Message(Role.SYSTEM, text, is_external=True)",
        "Message(Role.USER, text)",
        "Message(Role.USER, text, is_external=False)",
        "Message(Role.ASSISTANT, text, is_external=True)",
    ],
)
def test_a_block_that_is_not_external_user_content_is_flagged(broken: str) -> None:
    mutated = mutate(read(MEMORY), "Message(Role.USER, text, is_external=True)", broken)

    assert not builds_only_external_user_messages(mutated)


def test_a_second_message_built_in_the_memory_is_flagged() -> None:
    mutated = read(MEMORY) + "\n\ndef extra(text):\n    return Message(Role.SYSTEM, text)\n"

    assert not builds_only_external_user_messages(mutated)
    assert len(messages_built(mutated)) == 2


def test_a_memory_that_imports_the_prefix_is_flagged() -> None:
    mutated = mutate(
        read(MEMORY),
        "from __future__ import annotations\n",
        "from harness_agent.core.context.prefix import build_prefix\n",
    )

    assert "harness_agent.core.context.prefix" in imported_modules(mutated)


def test_the_detector_of_bound_handlers_and_cancellation_works() -> None:
    source = "try:\n    pass\nexcept Exception as error:\n    pass\n"

    assert handlers_that_bind(source) == [3]
    assert catches_cancellation("try:\n    pass\nexcept BaseException:\n    pass\n") == [3]
    assert own_connections("import sqlite3\nsqlite3.connect('x')\n") == [2]


@pytest.mark.parametrize("broken", ["except BaseException:", "except:", "except CancelledError:"])
def test_a_loader_that_catches_cancellation_is_flagged(broken: str) -> None:
    mutated = mutate(read(LOADER), "        except Exception:\n", f"        {broken}\n")

    assert catches_cancellation(mutated) != []


def test_a_loader_that_keeps_the_error_of_the_store_is_flagged() -> None:
    mutated = mutate(
        read(LOADER), "        except Exception:\n", "        except Exception as error:\n"
    )

    assert handlers_that_bind(mutated) != []


@pytest.mark.parametrize(
    "line",
    [
        "import sqlite3\n",
        "from harness_agent.adapters.storage import SqliteMemoryStore\n",
        "from harness_agent.core.loop import AgentLoop\n",
    ],
)
def test_a_loader_that_imports_what_it_must_not_is_flagged(line: str) -> None:
    mutated = mutate(read(LOADER), "from __future__ import annotations\n", f"{line}\n\n")

    assert purity_problems(mutated, LOADER.name) != []


def test_a_store_that_opens_its_own_connection_or_imports_the_loop_is_flagged() -> None:
    source = read(STORE)

    assert own_connections(source + "\nimport sqlite3\nconn = sqlite3.connect('x')\n") != []
    mutated = mutate(
        source,
        "from __future__ import annotations",
        "from harness_agent.core.loop import AgentLoop",
    )
    assert "harness_agent.core.loop" in imported_modules(mutated)


@pytest.mark.parametrize(
    "broken",
    [
        "creada       TEXT NOT NULL REFERENCES sessions(id),",
        "creada       TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,",
    ],
)
def test_a_memory_table_with_a_foreign_key_is_flagged(broken: str) -> None:
    mutated = mutate(read(SCHEMA), "creada       TEXT NOT NULL,", broken)

    assert ddl_with_references(mutated, "_V6") != []


def test_a_tool_that_stores_what_it_was_given_without_cleaning_is_flagged() -> None:
    mutated = mutate(
        read(TOOL),
        "self._log.remember(entry.key, entry.content)",
        'self._log.remember(args.get("clave"), args.get("texto"))',
    )

    assert remember_calls(mutated)[0][1] != ["entry.key", "entry.content"]


@pytest.mark.parametrize("broken", ["except BaseException:", "except:", "except CancelledError:"])
def test_a_tool_that_catches_cancellation_is_flagged(broken: str) -> None:
    mutated = mutate(read(TOOL), "        except Exception:\n", f"        {broken}\n")

    assert catches_cancellation(mutated) != []


@pytest.mark.parametrize(
    "line",
    [
        "import sqlite3",
        "from harness_agent.adapters.storage import SqliteMemoryStore",
        "from harness_agent.core.loop import AgentLoop",
    ],
)
def test_a_tool_that_imports_a_store_or_the_loop_is_flagged(line: str) -> None:
    mutated = mutate(read(TOOL), "from __future__ import annotations\n", line + "\n\n")

    assert any(module.startswith(TOOL_FORBIDDEN) for module in imported_modules(mutated))


def test_a_tool_built_without_the_switch_is_flagged() -> None:
    mutated = mutate(read(BOOTSTRAP), "if config.memory.enabled:", "if True:")

    assert memory_tool_calls_outside_the_switch(mutated) != []


def test_a_registry_view_that_does_not_hide_the_memory_tool_is_flagged() -> None:
    mutated = mutate(
        read(BOOTSTRAP), "{DELEGATE_TOOL_NAME, MEMORY_TOOL_NAME}", "{DELEGATE_TOOL_NAME}"
    )

    assert registry_views_that_hide_the_memory_tool(mutated) == 0


def test_a_resume_that_loads_the_memory_is_flagged() -> None:
    mutated = mutate(
        read(BOOTSTRAP),
        "        history[:] = resumed.history\n",
        "        history[:] = resumed.history\n        composition.memory.load_into(history)\n",
    )

    assert functions_that_load_the_memory(mutated) == {
        "run_session",
        "_new_command",
        "_resume_command",
    }
