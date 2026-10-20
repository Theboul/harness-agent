"""Architecture test: the core receives the configuration, it never reads it (HU-00-04 / T022).

Enforces FR-011 / RNF-21 / Principio III: no file under ``core/`` imports ``tomllib`` or
``harness_agent.config``, uses ``os.environ``, ``os.getenv`` or ``os.getenvb``, or opens or reads a
file (``open(...)``, ``.read_text``, ``.read_bytes``). The detector has a self-test with synthetic
snippets and a mutation test on a copy of ``core/`` in ``tmp_path``: the real code is never edited.
"""

from __future__ import annotations

import ast
import hashlib
import shutil
from pathlib import Path

import pytest

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core"
CORE_PACKAGE = "harness_agent.core"
CONFIG_MODULE = "harness_agent.config"
ENVIRONMENT_NAMES = {"environ", "getenv", "getenvb"}
READ_METHODS = {"read_text", "read_bytes"}


def _resolve(node: ast.ImportFrom, package: str) -> str:
    """The absolute name of the module of a ``from ... import`` (relative ones are resolved)."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def _is_config_module(module: str) -> bool:
    return module == CONFIG_MODULE or module.startswith(CONFIG_MODULE + ".")


def find_config_reads(
    source: str, filename: str = "<source>", package: str = CORE_PACKAGE
) -> list[str]:
    """One message per construct that reads configuration (file, environment or ``config.py``)."""
    tree = ast.parse(source, filename=filename)
    os_names = {"os"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            os_names.update(
                alias.asname or alias.name for alias in node.names if alias.name == "os"
            )

    found: list[str] = []

    def report(node: ast.AST, what: str) -> None:
        found.append(f"{filename}:{getattr(node, 'lineno', 0)}: {what}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "tomllib":
                    report(node, "imports 'tomllib'")
                if _is_config_module(alias.name):
                    report(node, f"imports '{alias.name}'")
        elif isinstance(node, ast.ImportFrom):
            module = _resolve(node, package)
            names = {alias.name for alias in node.names}
            if module.split(".")[0] == "tomllib":
                report(node, "imports from 'tomllib'")
            if _is_config_module(module) or (module == "harness_agent" and "config" in names):
                report(node, f"imports '{CONFIG_MODULE}'")
            if module == "os" and names & ENVIRONMENT_NAMES:
                report(node, f"imports {sorted(names & ENVIRONMENT_NAMES)} from 'os'")
        elif isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id in os_names
                and node.attr in ENVIRONMENT_NAMES
            ):
                report(node, f"uses 'os.{node.attr}'")
            if node.attr in READ_METHODS:
                report(node, f"calls '.{node.attr}'")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open"
        ):
            report(node, "calls 'open'")
    return found


def scan_directory(directory: Path, package: str = CORE_PACKAGE) -> list[str]:
    python_files = sorted(directory.rglob("*.py"))
    assert python_files, f"No Python files found under {directory}"
    violations: list[str] = []
    for file_path in python_files:
        relative = file_path.relative_to(directory)
        file_package = ".".join([package, *relative.parent.parts])
        violations.extend(
            find_config_reads(
                file_path.read_text(encoding="utf-8"), str(relative), package=file_package
            )
        )
    return violations


def fingerprint(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*.py"))
    }


FORBIDDEN_SNIPPETS = {
    "import tomllib": "import tomllib\n",
    "from tomllib import": "from tomllib import loads\n",
    "import harness_agent.config": "import harness_agent.config\n",
    "from harness_agent.config import": "from harness_agent.config import load_config\n",
    "from harness_agent import config": "from harness_agent import config\n",
    "relative import of config": "from .. import config\n",
    "relative import from config": "from ..config import load_config\n",
    "os.environ": "import os\nvalue = os.environ['X']\n",
    "os.environ.get": "import os\nvalue = os.environ.get('X')\n",
    "os.getenv": "import os\nvalue = os.getenv('X')\n",
    "os.getenvb": "import os\nvalue = os.getenvb(b'X')\n",
    "os alias": "import os as sistema\nvalue = sistema.environ\n",
    "from os import environ": "from os import environ\n",
    "from os import getenv": "from os import getenv\n",
    "open": "with open('x') as handle:\n    handle.read()\n",
    "read_text": "from pathlib import Path\ntext = Path('x').read_text()\n",
    "read_bytes": "from pathlib import Path\ndata = Path('x').read_bytes()\n",
}
CLEAN_SNIPPETS = {
    "plain code": "def total(limits):\n    return limits.max_turns * 2\n",
    "dataclasses": "import dataclasses\nfrom harness_agent.core.events import Event\n",
    "os.path": "import os\nname = os.path.join('a', 'b')\n",
    "a parameter named config": "def run(config):\n    return config.limits\n",
    "a core module named like a setting": "from .limits import Limits\n",
    "a method that is not a read": "result = store.read(1)\nitems = environment_names()\n",
}


class TestAutopruebaDelDetector:
    @pytest.mark.parametrize("label", sorted(FORBIDDEN_SNIPPETS))
    def test_each_forbidden_construct_is_detected(self, label: str) -> None:
        assert find_config_reads(FORBIDDEN_SNIPPETS[label], "fragmento.py"), label

    @pytest.mark.parametrize("label", sorted(CLEAN_SNIPPETS))
    def test_clean_code_is_not_flagged(self, label: str) -> None:
        assert find_config_reads(CLEAN_SNIPPETS[label], "fragmento.py") == []

    def test_a_message_names_the_file_and_the_line(self) -> None:
        messages = find_config_reads("x = 1\nimport tomllib\n", "modulo.py")

        assert messages == ["modulo.py:2: imports 'tomllib'"]


class TestNucleoReal:
    def test_the_core_reads_no_file_nor_environment_nor_config(self) -> None:
        violations = scan_directory(CORE_DIR)

        assert violations == [], "core/ lee configuración:\n" + "\n".join(violations)


class TestMutacionSobreUnaCopia:
    def test_the_detector_fails_on_a_copy_of_the_core_with_an_environment_read(
        self, tmp_path: Path
    ) -> None:
        before = fingerprint(CORE_DIR)
        copy = tmp_path / "core"
        shutil.copytree(CORE_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
        assert scan_directory(copy) == []
        target = sorted(copy.rglob("*.py"))[0]
        with target.open("a", encoding="utf-8") as handle:
            handle.write("\nimport os\n\nVALUE = os.environ.get('X')\n")

        violations = scan_directory(copy)

        assert violations
        assert any("os.environ" in message for message in violations)
        assert fingerprint(CORE_DIR) == before
