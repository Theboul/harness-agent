"""Architecture test: where color and the environment may be touched (HU-06-05 / T014).

Three rules of the console UX, checked on the syntax tree (never by importing the modules):

1. Only ``cli/style.py`` knows about ANSI: no other module of ``cli/`` has the escape character
   (``\\x1b``, ``\\033``, ``\\u001b``, ``chr(27)``) in a string.
2. Only ``cli/style.py`` reads the environment: no other module of ``cli/`` uses ``os.environ``,
   ``os.getenv`` or ``os.putenv`` (nor imports them by name).
3. ``bootstrap.py`` never calls ``print``: what it writes goes through the streams it is given.

The import frontier of ``cli/`` is already guarded by ``test_cli_boundaries.py``, which walks every
module of the directory, so the new modules are covered by it. The detectors have a self-test with
synthetic fragments and a mutation test on a copy of ``cli/`` in ``tmp_path``.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
CLI_DIR = SRC / "cli"
BOOTSTRAP = SRC / "bootstrap.py"
STYLE_MODULE = "style.py"
ESCAPE_CHAR = chr(27)
ENVIRONMENT_NAMES = frozenset({"environ", "getenv", "putenv"})


def escape_uses(source: str) -> list[str]:
    """Strings with the escape character, and ``chr(27)`` calls, in ``source``."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if ESCAPE_CHAR in node.value:
                found.append(f"line {node.lineno}: a string with the escape character")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "chr"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == ord(ESCAPE_CHAR)
        ):
            found.append(f"line {node.lineno}: chr(27)")
    return found


def environment_uses(source: str) -> list[str]:
    """Reads of the environment: ``os.environ``, ``os.getenv``, ``os.putenv`` or their imports."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in ENVIRONMENT_NAMES
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
        ):
            found.append(f"line {node.lineno}: os.{node.attr}")
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            found.extend(
                f"line {node.lineno}: from os import {alias.name}"
                for alias in node.names
                if alias.name in ENVIRONMENT_NAMES
            )
    return found


def print_calls(source: str) -> list[str]:
    """Calls to the builtin ``print``."""
    return [
        f"line {node.lineno}: print()"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]


def cli_violations(directory: Path) -> list[str]:
    """Rules 1 and 2 over every module of ``directory`` except the style module."""
    found: list[str] = []
    for path in sorted(directory.glob("*.py")):
        if path.name == STYLE_MODULE:
            continue
        source = path.read_text(encoding="utf-8")
        found.extend(f"{path.name} {issue}" for issue in escape_uses(source))
        found.extend(f"{path.name} {issue}" for issue in environment_uses(source))
    return found


class TestDetectors:
    def test_the_escape_character_is_found_in_every_spelling(self) -> None:
        for fragment in ('x = "\\x1b[0m"', 'x = "\\033[0m"', 'x = "\\u001b[0m"', "x = chr(27)"):
            assert escape_uses(fragment), fragment

    def test_ordinary_code_has_no_escape(self) -> None:
        assert escape_uses('x = "[ok]"\ny = chr(65)\nz = ord("a")') == []

    def test_the_environment_is_found_in_every_form(self) -> None:
        for fragment in (
            "import os\nx = os.environ['A']",
            "import os\nx = os.getenv('A')",
            "import os\nos.putenv('A', 'B')",
            "from os import environ",
            "from os import getenv as g",
        ):
            assert environment_uses(fragment), fragment

    def test_other_uses_of_os_are_allowed(self) -> None:
        assert environment_uses("import os\nx = os.path.join('a', 'b')\nfrom os import path") == []
        assert environment_uses("def f(environ):\n    return environ.get('A')") == []

    def test_print_is_found_and_other_calls_are_not(self) -> None:
        assert print_calls("print('hola')")
        assert print_calls("def f():\n    print('a')\n    print('b')") != []
        assert print_calls("stream.write('hola')\nlog.print('x')") == []


class TestRealCode:
    def test_only_the_style_module_has_ansi_and_reads_the_environment(self) -> None:
        assert cli_violations(CLI_DIR) == []

    def test_the_style_module_is_where_both_live(self) -> None:
        source = (CLI_DIR / STYLE_MODULE).read_text(encoding="utf-8")

        assert escape_uses(source)
        assert environment_uses(source)

    def test_the_composition_root_never_prints(self) -> None:
        assert print_calls(BOOTSTRAP.read_text(encoding="utf-8")) == []

    def test_the_rule_looks_at_the_modules_that_exist(self) -> None:
        names = {path.name for path in CLI_DIR.glob("*.py")}

        assert {"style.py", "approval_view.py", "activity.py", "session_commands.py"} <= names


class TestMutation:
    """The real code is never edited: the mutations go to a copy of ``cli/``."""

    def copy(self, tmp_path: Path) -> Path:
        target = tmp_path / "cli"
        shutil.copytree(CLI_DIR, target, ignore=shutil.ignore_patterns("__pycache__"))
        return target

    def test_the_copy_starts_clean(self, tmp_path: Path) -> None:
        assert cli_violations(self.copy(tmp_path)) == []

    def test_an_escape_in_another_module_is_caught(self, tmp_path: Path) -> None:
        copy = self.copy(tmp_path)
        module = copy / "render.py"
        module.write_text(
            module.read_text(encoding="utf-8") + '\nBAD = "\\x1b[31m"\n', encoding="utf-8"
        )

        assert any("render.py" in issue for issue in cli_violations(copy))

    def test_an_environment_read_in_another_module_is_caught(self, tmp_path: Path) -> None:
        copy = self.copy(tmp_path)
        module = copy / "activity.py"
        module.write_text(
            module.read_text(encoding="utf-8") + "\nimport os\nBAD = os.environ.get('X')\n",
            encoding="utf-8",
        )

        assert any("activity.py" in issue for issue in cli_violations(copy))

    def test_a_print_in_the_composition_root_is_caught(self, tmp_path: Path) -> None:
        mutated = BOOTSTRAP.read_text(encoding="utf-8") + "\nprint('x')\n"

        assert print_calls(mutated)
