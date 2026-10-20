"""Architecture test: the frontier between ``core/`` and ``cli/`` (HU-06-01 / T007).

Business rule 1 of HU-06-01 (the CLI has no logic of the core) and the hexagonal dependency rule:
no module of ``core/`` imports ``harness_agent.cli``, and the modules of ``cli/`` only import the
standard library, their own package and the public API of the core, that is, names of
``harness_agent.core.__all__`` with ``from harness_agent.core import <name>`` (never a submodule
such as ``harness_agent.core.loop``, and never adapters, observability, the composition root or
the configuration). The detectors have a self-test with synthetic fragments and a mutation test on
copies of both directories in ``tmp_path``: the real code is never edited.
"""

from __future__ import annotations

import ast
import hashlib
import shutil
import sys
from pathlib import Path

import pytest

import harness_agent.core as core_api

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
CORE_DIR = SRC / "core"
CLI_DIR = SRC / "cli"
CORE_PACKAGE = "harness_agent.core"
CLI_PACKAGE = "harness_agent.cli"
PUBLIC_NAMES = frozenset(core_api.__all__)


def imports_of(source: str, package: str) -> list[tuple[str, tuple[str, ...], int, bool]]:
    """``(absolute module, imported names, line, is_from)`` of every import of ``source``."""
    found: list[tuple[str, tuple[str, ...], int, bool]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend((alias.name, (), node.lineno, False) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                module = node.module or ""
            else:
                parts = package.split(".")
                base = parts[: len(parts) - (node.level - 1)]
                module = ".".join([*base, node.module] if node.module else base)
            names = tuple(alias.name for alias in node.names)
            found.append((module, names, node.lineno, True))
    return found


def _is_cli(module: str) -> bool:
    return module == CLI_PACKAGE or module.startswith(CLI_PACKAGE + ".")


def core_imports_cli(source: str, package: str = CORE_PACKAGE) -> list[str]:
    """Imports of ``harness_agent.cli`` found in a module of the core."""
    found: list[str] = []
    for module, names, line, _is_from in imports_of(source, package):
        if _is_cli(module) or (module == "harness_agent" and "cli" in names):
            found.append(f"line {line}: imports the CLI ({module or 'harness_agent'})")
    return found


def cli_violations(
    source: str, package: str = CLI_PACKAGE, public: frozenset[str] = PUBLIC_NAMES
) -> list[str]:
    """Imports of a module of ``cli/`` that are not stdlib, own package or the public core API."""
    found: list[str] = []
    for module, names, line, is_from in imports_of(source, package):
        top = module.split(".")[0]
        if top in sys.stdlib_module_names or top == "__future__" or _is_cli(module):
            continue
        if module == CORE_PACKAGE:
            if not is_from:
                found.append(f"line {line}: 'import {module}' (use 'from {module} import name')")
            found.extend(
                f"line {line}: '{name}' is not in harness_agent.core.__all__"
                for name in names
                if name not in public
            )
            continue
        if module == "harness_agent" and set(names) <= {"cli"}:
            continue
        found.append(f"line {line}: imports '{module}' (outside stdlib, cli and the core API)")
    return found


def scan(directory: Path, package: str, check: str) -> list[str]:
    files = sorted(directory.rglob("*.py"))
    assert files, f"No Python files found under {directory}"
    violations: list[str] = []
    for file_path in files:
        relative = file_path.relative_to(directory)
        file_package = ".".join([package, *relative.parent.parts])
        source = file_path.read_text(encoding="utf-8")
        found = (
            core_imports_cli(source, file_package)
            if check == "core"
            else cli_violations(source, file_package)
        )
        violations.extend(f"{relative}: {message}" for message in found)
    return violations


def fingerprint(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*.py"))
    }


CORE_FORBIDDEN = {
    "absolute import": "import harness_agent.cli\n",
    "absolute from-import": "from harness_agent.cli import render\n",
    "from a submodule": "from harness_agent.cli.app import run_cli\n",
    "from the package": "from harness_agent import cli\n",
    "relative import of the package": "from .. import cli\n",
    "relative import of a module": "from ..cli import app\n",
}
CORE_CLEAN = {
    "its own code": "from harness_agent.core.events import Event\nimport os\n",
    "a relative import inside the core": "from .events import Event\n",
    "other layers are another test": "import harness_agent.adapters\n",
}
CLI_FORBIDDEN = {
    "a core submodule": "from harness_agent.core.loop import AgentLoop\n",
    "a core interfaces submodule": "from harness_agent.core.interfaces import EventBus\n",
    "import of a core submodule": "import harness_agent.core.loop\n",
    "plain import of the core": "import harness_agent.core\n",
    "a name that is not public": "from harness_agent.core import _Progress\n",
    "adapters": "from harness_agent.adapters import litellm_provider\n",
    "observability": "import harness_agent.observability\n",
    "the composition root": "from harness_agent.bootstrap import build\n",
    "the configuration": "from harness_agent.config import load_config\n",
    "a third-party package": "import rich\n",
    "a module of the package root": "from harness_agent import config\n",
}
CLI_CLEAN = {
    "stdlib": "import sys\nfrom typing import TextIO\nfrom __future__ import annotations\n",
    "the public API": "from harness_agent.core import Event, EventBus, EventType\n",
    "an alias of a public name": "from harness_agent.core import Event as E\n",
    "its own package, relative": "from .render import render_event\nfrom . import app\n",
    "its own package, absolute": "from harness_agent.cli.render import SHOWN_TYPES\n",
}


class TestAutopruebaDeLosDetectores:
    @pytest.mark.parametrize("label", sorted(CORE_FORBIDDEN))
    def test_the_core_detector_finds_each_import_of_the_cli(self, label: str) -> None:
        assert core_imports_cli(CORE_FORBIDDEN[label]), label

    @pytest.mark.parametrize("label", sorted(CORE_CLEAN))
    def test_the_core_detector_does_not_flag_clean_code(self, label: str) -> None:
        assert core_imports_cli(CORE_CLEAN[label]) == []

    @pytest.mark.parametrize("label", sorted(CLI_FORBIDDEN))
    def test_the_cli_detector_finds_each_forbidden_import(self, label: str) -> None:
        assert cli_violations(CLI_FORBIDDEN[label]), label

    @pytest.mark.parametrize("label", sorted(CLI_CLEAN))
    def test_the_cli_detector_does_not_flag_allowed_imports(self, label: str) -> None:
        assert cli_violations(CLI_CLEAN[label]) == []

    def test_a_relative_import_is_resolved_against_the_package_of_the_module(self) -> None:
        # From core/tools/ the package is harness_agent.core.tools: three dots reach the root.
        assert core_imports_cli("from ...cli import app\n", "harness_agent.core.tools")
        # Two dots from core/tools/ is harness_agent.core.cli, which is not the CLI package.
        assert core_imports_cli("from ..cli import app\n", "harness_agent.core.tools") == []
        assert core_imports_cli("from .cli import app\n", "harness_agent.core") == []


class TestLineaBase:
    def test_no_module_of_the_core_imports_the_cli(self) -> None:
        assert len(list(CORE_DIR.rglob("*.py"))) >= 8

        violations = scan(CORE_DIR, CORE_PACKAGE, "core")

        assert violations == [], "core/ importa cli/:\n" + "\n".join(violations)

    def test_the_cli_only_uses_the_stdlib_its_own_package_and_the_public_core_api(self) -> None:
        names = {path.name for path in CLI_DIR.rglob("*.py")}
        assert {"__init__.py", "app.py", "render.py"} <= names

        violations = scan(CLI_DIR, CLI_PACKAGE, "cli")

        assert violations == [], "cli/ usa algo fuera de la API pública:\n" + "\n".join(violations)

    def test_the_names_the_cli_imports_from_the_core_are_public(self) -> None:
        for file_path in CLI_DIR.rglob("*.py"):
            for module, names, _line, _from in imports_of(
                file_path.read_text(encoding="utf-8"), CLI_PACKAGE
            ):
                if module == CORE_PACKAGE:
                    assert set(names) <= PUBLIC_NAMES, (file_path.name, names)


class TestMutacionSobreCopias:
    def test_the_core_detector_fails_on_a_copy_of_the_core_that_imports_the_cli(
        self, tmp_path: Path
    ) -> None:
        before = fingerprint(CORE_DIR)
        copy = tmp_path / "core"
        shutil.copytree(CORE_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
        assert scan(copy, CORE_PACKAGE, "core") == []
        target = sorted(copy.rglob("*.py"))[0]
        with target.open("a", encoding="utf-8") as handle:
            handle.write("\nfrom harness_agent.cli import render\n")

        violations = scan(copy, CORE_PACKAGE, "core")

        assert any("imports the CLI" in message for message in violations)
        assert fingerprint(CORE_DIR) == before

    def test_the_cli_detector_fails_on_a_copy_of_the_cli_that_uses_a_core_submodule(
        self, tmp_path: Path
    ) -> None:
        before = fingerprint(CLI_DIR)
        copy = tmp_path / "cli"
        shutil.copytree(CLI_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
        assert scan(copy, CLI_PACKAGE, "cli") == []
        target = copy / "app.py"
        with target.open("a", encoding="utf-8") as handle:
            handle.write("\nfrom harness_agent.core.loop import AgentLoop\n")

        violations = scan(copy, CLI_PACKAGE, "cli")

        assert any("outside stdlib, cli and the core API" in message for message in violations)
        assert fingerprint(CLI_DIR) == before
