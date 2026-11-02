"""Boundaries of the composition root ``bootstrap.py`` (propuesta HU-00-08 / T009, FR-011, FR-014).

``bootstrap.py`` is the one place that knows every layer and joins them, so it is the one
exception to "do not know the adapters". The rules that keep that exception small:

* ``bootstrap.py`` imports only the standard library, the public API (``__all__``; for the
  plain module ``config``, its public names) of ``harness_agent.core``, ``harness_agent.config``,
  ``harness_agent.cli`` and of ``harness_agent.adapters.storage``, ``.system`` and ``.tools``,
  plus exactly three submodules that have no public way in: ``harness_agent.core.loop``
  (``AgentLoop`` is not in ``core.__all__``),
  ``harness_agent.adapters.providers.litellm_provider`` and
  ``harness_agent.adapters.providers.retrying_provider`` (HU-07-04) (``providers/__init__.py``
  holds only a docstring by rule of ``test_providers_boundaries.py``). Any other submodule is a
  violation.
* ``bootstrap.py`` does not read the environment and does not call ``print`` or ``input``: the
  environment and the streams enter by parameter (``sys.stdin``/``stdout``/``stderr`` are only the
  defaults of those parameters).
* ``__main__.py`` imports only ``harness_agent.bootstrap``.
* Only ``__main__.py`` imports ``bootstrap``; nobody imports ``__main__``.
* ``bootstrap.py`` is the only module of the package that imports the core, the adapters, the CLI
  and the configuration at the same time.

That ``core/``, ``cli/`` and ``adapters/`` do not import ``bootstrap`` is already guarded by the
other architecture tests; here the rule is stated once for the whole package (the second-to-last
point). Each detector has a self-test with synthetic fragments and a mutation test on a copy of
the package: the real code is never edited.
"""

from __future__ import annotations

import ast
import importlib
import shutil
from pathlib import Path

import pytest

from tests.architecture.test_adapters_boundaries import STDLIB, imported_modules

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
ROOT_PACKAGE = "harness_agent"
BOOTSTRAP = "harness_agent.bootstrap"
MAIN = "harness_agent.__main__"
PUBLIC_API = frozenset(
    {
        "harness_agent.core",
        "harness_agent.config",
        "harness_agent.cli",
        "harness_agent.adapters.mcp",
        "harness_agent.adapters.storage",
        "harness_agent.adapters.system",
        "harness_agent.adapters.tasks",
        "harness_agent.adapters.tools",
    }
)
AUTHORIZED_SUBMODULES = frozenset(
    {
        "harness_agent.core.loop",
        "harness_agent.adapters.providers.litellm_provider",
        "harness_agent.adapters.providers.model_switch",
        "harness_agent.adapters.providers.retrying_provider",
    }
)
LAYERS = {
    "core": "harness_agent.core",
    "adapters": "harness_agent.adapters",
    "cli": "harness_agent.cli",
    "config": "harness_agent.config",
}


def imported_names(source: str, package: str) -> list[tuple[str, str, int]]:
    """``(module, name, line)`` of every ``from module import name`` (relative resolved)."""
    found: list[tuple[str, str, int]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[: len(package.split(".")) - node.level + 1]
                module = ".".join([*base, node.module] if node.module else base)
            else:
                module = node.module or ""
            found.extend((module, alias.name, node.lineno) for alias in node.names)
    return found


def public_names(module: str) -> frozenset[str]:
    """``__all__`` of the package, or the public names of a plain module such as ``config``."""
    imported = importlib.import_module(module)
    declared = getattr(imported, "__all__", None)
    if declared is not None:
        return frozenset(declared)
    return frozenset(name for name in vars(imported) if not name.startswith("_"))


def bootstrap_imports(source: str, package: str = ROOT_PACKAGE) -> list[str]:
    """Imports of ``bootstrap.py`` that break its rule, one message each."""
    found: list[str] = []
    for module, line in imported_modules(source, package):
        if module.split(".")[0] in STDLIB:
            continue
        if module in PUBLIC_API or module in AUTHORIZED_SUBMODULES:
            continue
        found.append(f"{module} at line {line}")
    for module, name, line in imported_names(source, package):
        if module in PUBLIC_API and name not in public_names(module):
            found.append(f"{module}.{name} is not in __all__ (line {line})")
    return found


def environment_reads(source: str) -> list[str]:
    """Reads of the process environment: ``os.environ``, ``os.getenv`` and ``from os import``."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr in {"environ", "environb", "getenv", "putenv", "unsetenv"}
        ):
            found.append(f"os.{node.attr} at line {node.lineno}")
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            found.extend(
                f"from os import {alias.name} at line {node.lineno}"
                for alias in node.names
                if alias.name in {"environ", "environb", "getenv", "putenv", "unsetenv"}
            )
    return found


def console_calls(source: str) -> list[str]:
    """Calls to the ``print`` and ``input`` builtins."""
    return [
        f"{node.func.id}() at line {node.lineno}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"print", "input"}
    ]


def layers_imported(source: str, package: str) -> set[str]:
    found: set[str] = set()
    for module, _line in imported_modules(source, package):
        for layer, prefix in LAYERS.items():
            if module == prefix or module.startswith(prefix + "."):
                found.add(layer)
    return found


def package_of(path: Path, root: Path) -> str:
    """Dotted package that contains ``path``; ``root`` holds the ``harness_agent`` folder."""
    return ".".join(path.relative_to(root).parts[:-1])


def module_of(path: Path, root: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def source_files(package_dir: Path) -> list[Path]:
    files = sorted(package_dir.rglob("*.py"))
    assert files, f"No Python files found under {package_dir}"
    return files


def importers_of(package_dir: Path, target: str) -> set[str]:
    """Modules of the package that import ``target`` (or one of its submodules)."""
    root = package_dir.parent
    found: set[str] = set()
    for path in source_files(package_dir):
        package = package_of(path, root)
        for module, _line in imported_modules(path.read_text(encoding="utf-8"), package):
            if module == target or module.startswith(target + "."):
                found.add(module_of(path, root))
    return found


def importers_of_all_layers(package_dir: Path) -> set[str]:
    root = package_dir.parent
    return {
        module_of(path, root)
        for path in source_files(package_dir)
        if layers_imported(path.read_text(encoding="utf-8"), package_of(path, root)) == set(LAYERS)
    }


# --- the real code -----------------------------------------------------------------------------


def test_bootstrap_imports_only_what_its_rule_allows() -> None:
    source = (PACKAGE_DIR / "bootstrap.py").read_text(encoding="utf-8")

    assert bootstrap_imports(source) == []


def test_bootstrap_does_not_read_the_environment_nor_use_the_console() -> None:
    source = (PACKAGE_DIR / "bootstrap.py").read_text(encoding="utf-8")

    assert environment_reads(source) == []
    assert console_calls(source) == []


def test_main_module_imports_only_bootstrap() -> None:
    source = (PACKAGE_DIR / "__main__.py").read_text(encoding="utf-8")

    modules = {module for module, _line in imported_modules(source, ROOT_PACKAGE)}

    assert modules == {BOOTSTRAP}


def test_only_the_main_module_imports_bootstrap_and_nobody_imports_main() -> None:
    assert importers_of(PACKAGE_DIR, BOOTSTRAP) == {MAIN}
    assert importers_of(PACKAGE_DIR, MAIN) == set()


def test_bootstrap_is_the_only_module_that_imports_every_layer() -> None:
    assert importers_of_all_layers(PACKAGE_DIR) == {BOOTSTRAP}


def test_the_two_authorized_submodules_exist() -> None:
    for module in AUTHORIZED_SUBMODULES:
        importlib.import_module(module)


# --- self-tests of the detectors ---------------------------------------------------------------


@pytest.mark.parametrize(
    "fragment",
    [
        "from harness_agent.core.in_memory_event_bus import InMemoryEventBus\n",
        "from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore\n",
        "from harness_agent.adapters.tools.read_file import ReadFileTool\n",
        "from harness_agent.adapters.providers import LiteLLMProvider\n",
        "from harness_agent.adapters.converters import to_openai_messages\n",
        "from harness_agent.cli.app import run_cli\n",
        "import litellm\n",
        "from harness_agent.core import NoExisteEnElApi\n",
    ],
    ids=[
        "submodulo-del-nucleo",
        "submodulo-de-storage",
        "submodulo-de-tools",
        "providers-sin-api",
        "converters",
        "submodulo-de-cli",
        "sdk",
        "nombre-fuera-de-all",
    ],
)
def test_bootstrap_imports_detects_a_violation(fragment: str) -> None:
    assert bootstrap_imports(fragment) != []


@pytest.mark.parametrize(
    "fragment",
    [
        "import asyncio\nimport os\nfrom pathlib import Path\n",
        "from harness_agent.core import AuthorizedArea\n",
        "from harness_agent.core.loop import AgentLoop\n",
        "from harness_agent.adapters.providers.litellm_provider import LiteLLMProvider\n",
        "from harness_agent.adapters.storage import SqliteSessionStore\n",
    ],
    ids=["stdlib", "api-del-nucleo", "bucle", "proveedor", "storage"],
)
def test_bootstrap_imports_accepts_what_the_rule_allows(fragment: str) -> None:
    assert bootstrap_imports(fragment) == []


@pytest.mark.parametrize(
    "fragment",
    [
        "import os\nvalue = os.environ['X']\n",
        "import os\nvalue = os.getenv('X')\n",
        "from os import environ\n",
        "from os import getenv\n",
    ],
    ids=["environ", "getenv", "from-environ", "from-getenv"],
)
def test_environment_reads_detects_a_read(fragment: str) -> None:
    assert environment_reads(fragment) != []


def test_environment_reads_accepts_other_os_uses() -> None:
    assert environment_reads("import os\nfrom os import PathLike\nx = os.fspath('a')\n") == []


def test_console_calls_detects_print_and_input_but_not_a_stream_write() -> None:
    assert console_calls("print('x')\n") != []
    assert console_calls("name = input()\n") != []
    assert console_calls("import sys\nstream = sys.stdout\nstream.write('x')\n") == []


def test_layers_imported_sees_each_layer() -> None:
    source = (
        "from harness_agent.core import X\nfrom harness_agent.adapters.tools import Y\n"
        "from harness_agent.cli import Z\nfrom harness_agent.config import W\n"
    )

    assert layers_imported(source, ROOT_PACKAGE) == set(LAYERS)
    assert layers_imported("from harness_agent.core import X\n", ROOT_PACKAGE) == {"core"}


# --- mutation tests on a copy of the package ---------------------------------------------------


def copy_package(tmp_path: Path) -> Path:
    copy = tmp_path / "harness_agent"
    shutil.copytree(PACKAGE_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
    return copy


def append(path: Path, line: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + "\n" + line + "\n", encoding="utf-8")


def test_the_copy_of_the_real_package_has_no_violations(tmp_path: Path) -> None:
    copy = copy_package(tmp_path)

    assert importers_of(copy, BOOTSTRAP) == {MAIN}
    assert importers_of_all_layers(copy) == {BOOTSTRAP}


def test_a_module_that_imports_bootstrap_is_detected(tmp_path: Path) -> None:
    copy = copy_package(tmp_path)
    append(copy / "config.py", "from harness_agent.bootstrap import main")

    assert importers_of(copy, BOOTSTRAP) == {MAIN, "harness_agent.config"}


def test_a_module_that_imports_the_main_module_is_detected(tmp_path: Path) -> None:
    copy = copy_package(tmp_path)
    append(copy / "cli" / "app.py", "import harness_agent.__main__")

    assert importers_of(copy, MAIN) == {"harness_agent.cli.app"}


def test_a_second_module_that_joins_every_layer_is_detected(tmp_path: Path) -> None:
    copy = copy_package(tmp_path)
    (copy / "second_root.py").write_text(
        "from harness_agent.core import X\nfrom harness_agent.adapters.tools import Y\n"
        "from harness_agent.cli import Z\nfrom harness_agent.config import W\n",
        encoding="utf-8",
    )

    assert importers_of_all_layers(copy) == {BOOTSTRAP, "harness_agent.second_root"}


def test_a_forbidden_import_in_a_copy_of_bootstrap_is_detected(tmp_path: Path) -> None:
    copy = copy_package(tmp_path)
    append(copy / "bootstrap.py", "from harness_agent.core.in_memory_event_bus import X")

    source = (copy / "bootstrap.py").read_text(encoding="utf-8")

    assert any("in_memory_event_bus" in message for message in bootstrap_imports(source))


def test_an_environment_read_in_a_copy_of_bootstrap_is_detected(tmp_path: Path) -> None:
    copy = copy_package(tmp_path)
    append(copy / "bootstrap.py", "SNEAKY = os.environ.get('X')")

    source = (copy / "bootstrap.py").read_text(encoding="utf-8")

    assert environment_reads(source) != []
