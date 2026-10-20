"""AC-02 of HU-01-05: the core does not print and does not depend on the terminal (T005).

AC-02 (literal): "Dado el núcleo, cuando se revisa su código, entonces no contiene llamadas de
impresión ni dependencias de la terminal."

It extends what already exists instead of copying it: ``console_uses`` of ``test_loop_boundaries``
(``print``, ``input`` and ``sys.stdout``/``stderr``/``stdin``, until now applied only to
``core/loop.py``) is applied to every module of ``core/``, and this module adds what neither that
file nor ``test_core_boundaries`` covers: terminal libraries, aliases of ``sys``,
``from sys import stdout`` and ``builtins.print``. It also checks the module of the in-memory bus:
standard library and ``harness_agent.core`` only, and no definition of event types (business rule
2: the events are defined in one place, ``core/events.py``).

The detectors have a self-test with synthetic fragments and a mutation test on a copy of ``core/``
in ``tmp_path``: the real code is never edited.
"""

from __future__ import annotations

import ast
import hashlib
import shutil
from pathlib import Path

import pytest

from tests.architecture.test_loop_boundaries import console_uses, forbidden_imports

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core"
BUS_FILE = CORE_DIR / "in_memory_event_bus.py"
TERMINAL_LIBRARIES = {
    "curses",
    "readline",
    "rich",
    "typer",
    "click",
    "prompt_toolkit",
    "colorama",
    "blessed",
    "urwid",
    "textual",
    "tty",
    "termios",
    "msvcrt",
    "getpass",
    "pty",
}
STREAMS = {"stdout", "stderr", "stdin"}
CONSOLE_BUILTINS = {"print", "input"}
EVENT_BASES = {"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag", "Event", "EventType"}
EVENT_NAMES = {"Event", "EventType"}


def terminal_uses(source: str) -> list[str]:
    """Constructs that print, read from the terminal or import a terminal library."""
    tree = ast.parse(source)
    found = list(console_uses(source))
    sys_aliases = {
        alias.asname
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "sys" and alias.asname
    }
    builtins_aliases = {"builtins"} | {
        alias.asname
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "builtins" and alias.asname
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(
                f"import {alias.name} at line {node.lineno}"
                for alias in node.names
                if alias.name.split(".")[0] in TERMINAL_LIBRARIES
            )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            top = node.module.split(".")[0]
            names = {alias.name for alias in node.names}
            if top in TERMINAL_LIBRARIES:
                found.append(f"from {node.module} import ... at line {node.lineno}")
            if node.module == "sys" and names & STREAMS:
                found.append(f"from sys import {sorted(names & STREAMS)} at line {node.lineno}")
            if node.module == "builtins" and names & CONSOLE_BUILTINS:
                found.append(f"from builtins import {sorted(names & CONSOLE_BUILTINS)}")
        elif (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and (
                (node.value.id in sys_aliases and node.attr in STREAMS)
                or (node.value.id in builtins_aliases and node.attr in CONSOLE_BUILTINS)
            )
        ):
            found.append(f"{node.value.id}.{node.attr} at line {node.lineno}")
    return found


def event_type_definitions(source: str) -> list[str]:
    """Classes that define an event type or an event: named like one, or based on an enum."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = {
            base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
            for base in node.bases
        }
        if node.name in EVENT_NAMES or bases & EVENT_BASES:
            found.append(f"class {node.name} at line {node.lineno}")
    return found


def scan_core(directory: Path) -> list[str]:
    python_files = sorted(directory.rglob("*.py"))
    assert python_files, f"No Python files found under {directory}"
    violations: list[str] = []
    for file_path in python_files:
        relative = file_path.relative_to(directory)
        violations.extend(
            f"{relative}: {message}"
            for message in terminal_uses(file_path.read_text(encoding="utf-8"))
        )
    return violations


def fingerprint(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*.py"))
    }


FORBIDDEN_SNIPPETS = {
    "print": "print('x')\n",
    "input": "value = input()\n",
    "sys.stdout": "import sys\nsys.stdout.write('x')\n",
    "sys.stderr": "import sys\nsys.stderr.write('x')\n",
    "sys.stdin": "import sys\nline = sys.stdin.readline()\n",
    "alias of sys": "import sys as system\nsystem.stdout.write('x')\n",
    "from sys import stdout": "from sys import stdout\n",
    "from sys import stderr as err": "from sys import stderr as err\n",
    "import curses": "import curses\n",
    "import curses.ascii": "import curses.ascii\n",
    "from rich": "from rich.console import Console\n",
    "import typer": "import typer\n",
    "import click": "import click\n",
    "import getpass": "import getpass\n",
    "import termios": "import termios\n",
    "from prompt_toolkit": "from prompt_toolkit import prompt\n",
    "builtins.print": "import builtins\nbuiltins.print('x')\n",
    "alias of builtins": "import builtins as b\nb.input()\n",
    "from builtins import input": "from builtins import input\n",
}
CLEAN_SNIPPETS = {
    "plain code": "def total(values):\n    return sum(values)\n",
    "logging": "import logging\nlogging.getLogger('x').info('y')\n",
    "sys that is not a stream": "import sys\nversion = sys.version_info\npath = sys.path\n",
    "from sys import something else": "from sys import version_info\n",
    "a method named print": "class Printer:\n    def print(self) -> None: ...\nPrinter().print()\n",
    "a variable named like a library": "rich = 1\nclick = rich\n",
}
EVENT_SAMPLES = {
    "a class named Event": "class Event:\n    pass\n",
    "a class named EventType": "class EventType:\n    pass\n",
    "an enum": "from enum import Enum\n\nclass Kind(Enum):\n    A = 1\n",
    "a str enum": "import enum\n\nclass Kind(enum.StrEnum):\n    A = 'a'\n",
    "a subclass of Event": "class Mine(Event):\n    pass\n",
}
NOT_EVENT_SAMPLES = {
    "a group of errors": "class Failure(ExceptionGroup[Exception]):\n    pass\n",
    "a plain bus": "class Bus:\n    pass\n",
    "a class that mentions Event": "class Bus:\n    def emit(self, event: Event) -> None: ...\n",
}


class TestAutopruebaDelDetector:
    @pytest.mark.parametrize("label", sorted(FORBIDDEN_SNIPPETS))
    def test_each_forbidden_construct_is_detected(self, label: str) -> None:
        assert terminal_uses(FORBIDDEN_SNIPPETS[label]), label

    @pytest.mark.parametrize("label", sorted(CLEAN_SNIPPETS))
    def test_clean_code_is_not_flagged(self, label: str) -> None:
        assert terminal_uses(CLEAN_SNIPPETS[label]) == []

    @pytest.mark.parametrize("label", sorted(EVENT_SAMPLES))
    def test_a_definition_of_an_event_type_is_detected(self, label: str) -> None:
        assert event_type_definitions(EVENT_SAMPLES[label]), label

    @pytest.mark.parametrize("label", sorted(NOT_EVENT_SAMPLES))
    def test_other_classes_are_not_flagged(self, label: str) -> None:
        assert event_type_definitions(NOT_EVENT_SAMPLES[label]) == []

    def test_the_existing_console_detector_is_reused_not_copied(self) -> None:
        assert terminal_uses("print('x')\n")[0].startswith("print() at line 1")


class TestNucleoReal:
    def test_no_module_of_the_core_prints_or_uses_the_terminal(self) -> None:
        assert len(list(CORE_DIR.rglob("*.py"))) >= 8

        violations = scan_core(CORE_DIR)

        assert violations == [], "core/ usa la terminal:\n" + "\n".join(violations)

    def test_the_bus_module_exists_and_is_scanned(self) -> None:
        assert BUS_FILE.is_file()
        assert terminal_uses(BUS_FILE.read_text(encoding="utf-8")) == []


class TestModuloDelBus:
    def test_it_imports_only_the_standard_library_and_the_core(self) -> None:
        source = BUS_FILE.read_text(encoding="utf-8")

        assert forbidden_imports(source) == []

    def test_it_imports_nothing_from_the_outer_layers(self) -> None:
        source = BUS_FILE.read_text(encoding="utf-8")

        for layer in ("adapters", "cli", "observability", "bootstrap"):
            assert f"harness_agent.{layer}" not in source

    def test_it_defines_no_event_type(self) -> None:
        source = BUS_FILE.read_text(encoding="utf-8")

        assert event_type_definitions(source) == []


class TestMutacionSobreUnaCopia:
    def test_the_detector_fails_on_a_copy_of_the_core_with_a_print(self, tmp_path: Path) -> None:
        before = fingerprint(CORE_DIR)
        copy = tmp_path / "core"
        shutil.copytree(CORE_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
        assert scan_core(copy) == []
        target = sorted(copy.rglob("*.py"))[0]
        with target.open("a", encoding="utf-8") as handle:
            handle.write("\nprint('x')\n")

        violations = scan_core(copy)

        assert any("print() at line" in message for message in violations)
        assert fingerprint(CORE_DIR) == before
