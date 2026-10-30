"""Boundaries of the retry wrapper of ``adapters/providers/`` (HU-07-04 / T015).

``retrying_provider.py`` and ``errors.py`` hold the policy of the retries. Rules:

* They import only the standard library, the public API of the core and their own package: no
  ``config``, ``cli``, ``bootstrap`` or other adapter (``bootstrap`` is the one that connects them).
* They know nothing of events: no ``Event``/``EventType``/``EventBus`` (the observer is a plain
  callable; the composition root publishes the event).
* They never block the loop: no ``time`` and no ``threading``; the wait is an injected awaitable.
* They never swallow a cancellation (D-01): the only exceptions a handler catches are the
  transient provider errors and ``Exception`` (``CancelledError`` is a ``BaseException``); no bare
  ``except:`` and no ``BaseException``.

Each rule has a self-test over synthetic sources, so a detector that stops detecting fails here.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.architecture.test_adapters_boundaries import guarded_imports, imported_modules

PROVIDERS_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "adapters" / "providers"
)
PACKAGE = "harness_agent.adapters.providers"
FILES = ("retrying_provider.py", "errors.py")
EVENT_NAMES = {"Event", "EventType", "EventBus", "InMemoryEventBus"}
BLOCKING_MODULES = {"time", "threading"}
ALLOWED_HANDLERS = {"TRANSIENT_ERRORS", "Exception"}


def foreign_imports(source: str) -> list[str]:
    return guarded_imports(source, PACKAGE)


def event_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    return [
        f"{alias.name} at line {node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if alias.name in EVENT_NAMES
    ]


def blocking_imports(source: str) -> list[str]:
    return [
        f"{module} at line {line}"
        for module, line in imported_modules(source, PACKAGE)
        if module.split(".")[0] in BLOCKING_MODULES
    ]


def risky_handlers(source: str) -> list[str]:
    """Handlers that could swallow a cancellation or that catch something not on the list."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            found.append(f"bare except at line {node.lineno}")
            continue
        names = (
            [element for element in node.type.elts]
            if isinstance(node.type, ast.Tuple)
            else [node.type]
        )
        for name in names:
            label = name.id if isinstance(name, ast.Name) else ast.dump(name)
            if label not in ALLOWED_HANDLERS:
                found.append(f"except {label} at line {node.lineno}")
    return found


# --- the real code --------------------------------------------------------------------------


def sources() -> list[tuple[str, str]]:
    return [(name, (PROVIDERS_DIR / name).read_text(encoding="utf-8")) for name in FILES]


def test_the_files_exist() -> None:
    for name in FILES:
        assert (PROVIDERS_DIR / name).is_file()


def test_imports_are_stdlib_core_and_the_own_package_only() -> None:
    for name, source in sources():
        assert foreign_imports(source) == [], name


def test_the_wrapper_knows_nothing_of_events() -> None:
    for name, source in sources():
        assert event_imports(source) == [], name


def test_the_wrapper_never_blocks_the_loop() -> None:
    for name, source in sources():
        assert blocking_imports(source) == [], name


def test_no_handler_can_swallow_a_cancellation() -> None:
    for name, source in sources():
        assert risky_handlers(source) == [], name


# --- the detectors detect -------------------------------------------------------------------


def test_foreign_imports_are_reported() -> None:
    assert foreign_imports("from harness_agent.config import Secret\n")
    assert foreign_imports("from harness_agent.adapters.storage import SqliteSessionStore\n")
    assert not foreign_imports("import asyncio\nfrom harness_agent.core import Provider\n")


def test_event_imports_are_reported() -> None:
    assert event_imports("from harness_agent.core import EventType\n")
    assert not event_imports("from harness_agent.core import Provider\n")


def test_blocking_imports_are_reported() -> None:
    assert blocking_imports("import time\n")
    assert blocking_imports("from threading import Lock\n")
    assert not blocking_imports("import asyncio\n")


def test_risky_handlers_are_reported() -> None:
    assert risky_handlers("try:\n    pass\nexcept:\n    pass\n")
    assert risky_handlers("try:\n    pass\nexcept BaseException:\n    pass\n")
    assert risky_handlers("try:\n    pass\nexcept (Exception, asyncio.CancelledError):\n    pass\n")
    assert risky_handlers("try:\n    pass\nexcept ValueError:\n    pass\n")
    assert not risky_handlers("try:\n    pass\nexcept TRANSIENT_ERRORS:\n    pass\n")
    assert not risky_handlers("try:\n    pass\nexcept Exception:\n    pass\n")
