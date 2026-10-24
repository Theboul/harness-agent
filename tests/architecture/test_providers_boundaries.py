"""Boundaries of ``adapters/providers/`` and of the LiteLLM import (HU-07-02 / T008).

``litellm`` is an optional dependency and the adapter is the one place that talks to it. Rules:

* No file of ``src/harness_agent/`` has an ``import`` of a model SDK (``litellm``, ``openai``,
  ``anthropic``, ``google``); not even ``adapters/providers/`` at module level.
* ``importlib.import_module("litellm")`` (or ``__import__``) appears only inside a function of
  ``adapters/providers/``: the load is lazy, so importing the adapter never needs the library.
* ``adapters/providers/`` imports only the standard library, the public API of the core, the
  public API of ``adapters/converters`` and its own package: no ``config``, ``cli``,
  ``observability``, ``bootstrap`` or other adapter. It reads no environment or file and does not
  use the terminal.
* No string literal of ``adapters/providers/`` (docstrings aside) names a provider of
  ``PROVIDER_KEY_VARIABLES``: the adapter has no branch per provider. Identifiers such as
  ``to_openai_messages`` do not count: that is the name of the common wire format.
* ``adapters/providers/__init__.py`` holds only a docstring.

Why not ``GUARDED`` of ``test_adapters_boundaries.py``: that list allows only the standard library,
the core API and the own package; this package also needs ``adapters.converters`` and the lazy
load. The detectors of that module are reused, not copied, and each rule has a self-test and a
mutation test on a copy of the real package.
"""

from __future__ import annotations

import ast
import re
import shutil
from pathlib import Path

import pytest

from harness_agent.config import PROVIDER_KEY_VARIABLES
from tests.architecture.test_adapters_boundaries import guarded_imports, imported_modules
from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
PROVIDERS_DIR = PACKAGE_DIR / "adapters" / "providers"
PROVIDERS_PACKAGE = "harness_agent.adapters.providers"
CONVERTERS_API = "harness_agent.adapters.converters"
MODEL_LIBRARIES = {"litellm", "openai", "anthropic", "google"}
DYNAMIC_IMPORTS = {"import_module", "__import__"}


def package_of(path: Path, root: Path) -> str:
    """Dotted package of ``path``; ``root`` is the folder that holds ``harness_agent``."""
    return ".".join(path.relative_to(root).parts[:-1])


def sdk_imports(source: str, package: str) -> list[str]:
    """``import`` statements of a model SDK, wherever they are in the file."""
    return [
        f"{module} at line {line}"
        for module, line in imported_modules(source, package)
        if module.split(".")[0] in MODEL_LIBRARIES
    ]


class _DynamicImports(ast.NodeVisitor):
    """Calls to ``import_module`` / ``__import__`` with a model SDK as a literal argument."""

    def __init__(self) -> None:
        self.depth = 0
        self.found: list[tuple[int, bool]] = []

    def _function(self, node: ast.AST) -> None:
        self.depth += 1
        self.generic_visit(node)
        self.depth -= 1

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function
    visit_Lambda = _function

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        name = function.id if isinstance(function, ast.Name) else None
        if isinstance(function, ast.Attribute):
            name = function.attr
        if name in DYNAMIC_IMPORTS and node.args:
            first = node.args[0]
            if (
                isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and first.value.split(".")[0] in MODEL_LIBRARIES
            ):
                self.found.append((node.lineno, self.depth > 0))
        self.generic_visit(node)


def dynamic_sdk_imports(source: str) -> list[tuple[int, bool]]:
    """``(line, inside_a_function)`` of every dynamic import of a model SDK."""
    visitor = _DynamicImports()
    visitor.visit(ast.parse(source))
    return visitor.found


def not_allowed_imports(source: str, package: str) -> list[str]:
    """Imports that are not stdlib, the core API, the converters API or the own package."""
    return [
        message
        for message in guarded_imports(source, package)
        if not message.startswith(f"{CONVERTERS_API} at line ")
    ]


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            first = node.body[0] if node.body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                ids.add(id(first.value))
    return ids


def provider_name_literals(source: str, names: list[str]) -> list[str]:
    """String literals (docstrings aside) that contain a provider name as a word."""
    tree = ast.parse(source)
    skip = _docstring_nodes(tree)
    pattern = re.compile(r"\b(" + "|".join(re.escape(name) for name in names) + r")\b", re.I)
    found: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skip
            and (match := pattern.search(node.value))
        ):
            found.append(f"{match.group(1)!r} in a literal at line {node.lineno}")
    return found


def is_docstring_only(source: str) -> bool:
    body = ast.parse(source).body
    return (
        len(body) == 1
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    )


def scan_providers(directory: Path) -> list[str]:
    """Every rule of ``adapters/providers/`` over the ``.py`` files of ``directory``."""
    files = sorted(directory.rglob("*.py"))
    assert files, f"No Python files found under {directory}"
    names = sorted(PROVIDER_KEY_VARIABLES)
    violations: list[str] = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        package = PROVIDERS_PACKAGE
        label = path.name
        violations.extend(f"{label}: SDK import {m}" for m in sdk_imports(source, package))
        violations.extend(
            f"{label}: dynamic import of an SDK outside a function (line {line})"
            for line, inside in dynamic_sdk_imports(source)
            if not inside
        )
        violations.extend(f"{label}: {m}" for m in not_allowed_imports(source, package))
        violations.extend(f"{label}: {m}" for m in find_config_reads(source, label, package))
        violations.extend(f"{label}: {m}" for m in terminal_uses(source))
        violations.extend(f"{label}: {m}" for m in provider_name_literals(source, names))
        if path.name == "__init__.py" and not is_docstring_only(source):
            violations.append(f"{label}: must hold only a docstring")
    return violations


def scan_everything_else(root: Path, providers: Path) -> list[str]:
    """No SDK import anywhere, and no dynamic import of an SDK outside ``adapters/providers/``."""
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        package = package_of(path, root.parent)
        relative = path.relative_to(root)
        violations.extend(f"{relative}: {m}" for m in sdk_imports(source, package))
        if providers not in path.parents:
            violations.extend(
                f"{relative}: dynamic import of an SDK at line {line}"
                for line, _ in dynamic_sdk_imports(source)
            )
    return violations


# --- the real code --------------------------------------------------------------------------


def test_the_package_exists_with_the_adapter() -> None:
    assert (PROVIDERS_DIR / "litellm_provider.py").is_file()
    assert (PROVIDERS_DIR / "__init__.py").is_file()


def test_adapters_providers_respects_every_rule() -> None:
    assert scan_providers(PROVIDERS_DIR) == []


def test_no_sdk_is_imported_anywhere_and_the_lazy_load_is_only_in_the_providers_package() -> None:
    assert scan_everything_else(PACKAGE_DIR, PROVIDERS_DIR) == []


def test_the_adapter_loads_the_library_lazily_inside_a_function() -> None:
    source = (PROVIDERS_DIR / "litellm_provider.py").read_text(encoding="utf-8")

    assert [inside for _, inside in dynamic_sdk_imports(source)] == [True]


def test_the_provider_names_come_from_the_one_table() -> None:
    assert {"anthropic", "gemini", "groq", "ollama", "openai", "openrouter"} <= set(
        PROVIDER_KEY_VARIABLES
    )


# --- detector self-tests --------------------------------------------------------------------

PKG = PROVIDERS_PACKAGE


@pytest.mark.parametrize(
    "source",
    [
        "import litellm\n",
        "import litellm.exceptions\n",
        "from litellm import acompletion\n",
        "import openai\n",
        "from anthropic import Anthropic\n",
        "from google import genai\n",
        "def f():\n    import litellm\n",
    ],
)
def test_the_sdk_import_detector_flags_each_form(source: str) -> None:
    assert sdk_imports(source, PKG) != []


@pytest.mark.parametrize(
    "source",
    [
        "import os\n",
        "from harness_agent.core import Provider\n",
        "import importlib\nimportlib.import_module('json')\n",
        "from harness_agent.adapters.converters import to_openai_messages\n",
    ],
)
def test_the_sdk_import_detector_lets_the_rest_through(source: str) -> None:
    assert sdk_imports(source, PKG) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import importlib\nimportlib.import_module('litellm')\n", [(2, False)]),
        ("from importlib import import_module\nimport_module('litellm.main')\n", [(2, False)]),
        ("__import__('openai')\n", [(1, False)]),
        (
            "import importlib\ndef f():\n    return importlib.import_module('litellm')\n",
            [(3, True)],
        ),
        ("import importlib\nasync def f():\n    importlib.import_module('litellm')\n", [(3, True)]),
        ("import importlib\ng = lambda: importlib.import_module('litellm')\n", [(2, True)]),
        ("import importlib\nimportlib.import_module('json')\n", []),
        ("import importlib\nimportlib.import_module(name)\n", []),
        ("import importlib\nimportlib.import_module()\n", []),
    ],
)
def test_the_dynamic_import_detector_tells_module_level_from_inside_a_function(
    source: str, expected: list[tuple[int, bool]]
) -> None:
    assert dynamic_sdk_imports(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "from harness_agent.config import load_config\n",
        "from harness_agent.cli import render\n",
        "import harness_agent.observability\n",
        "from harness_agent.bootstrap import build\n",
        "from harness_agent.core.loop import AgentLoop\n",
        "from harness_agent.core.interfaces import Provider\n",
        "from harness_agent.adapters.tools import ReadFileTool\n",
        "from harness_agent.adapters.storage import SqliteSessionStore\n",
        "from harness_agent.adapters.converters.base import ConversionError\n",
        "import httpx\n",
    ],
)
def test_the_import_rule_flags_each_forbidden_form(source: str) -> None:
    assert not_allowed_imports(source, PKG) != []


@pytest.mark.parametrize(
    "source",
    [
        "import json\n",
        "from __future__ import annotations\n",
        "from harness_agent.core import Provider, Message\n",
        "from harness_agent.adapters.converters import to_openai_messages\n",
        "from .other import helper\n",
    ],
)
def test_the_import_rule_lets_the_allowed_forms_through(source: str) -> None:
    assert not_allowed_imports(source, PKG) == []


NAMES = ["anthropic", "groq", "ollama", "openai"]


@pytest.mark.parametrize(
    "source",
    [
        'x = "groq"\n',
        'x = "Se usa Anthropic aquí"\n',
        'x = f"{y}-ollama"\n',
        'if name == "openai":\n    pass\n',
        'table = {"groq": 1}\n',
    ],
)
def test_the_name_rule_flags_a_provider_name_in_a_literal(source: str) -> None:
    assert provider_name_literals(source, NAMES) != []


@pytest.mark.parametrize(
    "source",
    [
        'def f():\n    """Uses groq."""\n',
        '"""Module about openai."""\nx = 1\n',
        'class C:\n    """Anthropic wire."""\n',
        "from harness_agent.adapters.converters import to_openai_messages as f\nf([])\n",
        'x = "openaiish"\n',
        'x = "proveedor"\n',
    ],
)
def test_the_name_rule_ignores_docstrings_identifiers_and_other_words(source: str) -> None:
    assert provider_name_literals(source, NAMES) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('"""Only a docstring."""\n', True),
        ('"""Doc."""\nx = 1\n', False),
        ('"""Doc."""\nfrom os import path\n', False),
        ("x = 1\n", False),
        ("", False),
    ],
)
def test_the_docstring_only_check(source: str, expected: bool) -> None:
    assert is_docstring_only(source) is expected


# --- mutations on a copy of the real package -------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "import litellm\n",
        "from litellm import acompletion\n",
        "import openai\n",
        "import importlib\nimportlib.import_module('litellm')\n",
        "from harness_agent.config import load_config\n",
        "from harness_agent.adapters.tools import ReadFileTool\n",
        "from harness_agent.core.loop import AgentLoop\n",
        "import os\nKEY = os.environ['X']\n",
        "print('hola')\n",
        "PROVIDER = 'groq'\n",
        "PROVIDER = 'anthropic/algo'\n",
    ],
)
def test_mutation_each_forbidden_line_added_to_a_copy_of_the_real_package_is_caught(
    tmp_path: Path, line: str
) -> None:
    copy = tmp_path / "providers"
    shutil.copytree(PROVIDERS_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
    target = copy / "litellm_provider.py"
    target.write_text(line + target.read_text("utf-8"), "utf-8")

    assert scan_providers(copy) != []


def test_mutation_an_init_with_code_is_caught(tmp_path: Path) -> None:
    copy = tmp_path / "providers"
    shutil.copytree(PROVIDERS_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
    init = copy / "__init__.py"
    init.write_text(init.read_text("utf-8") + "from .litellm_provider import LiteLLMProvider\n")

    assert scan_providers(copy) != []


def test_mutation_a_dynamic_import_in_another_package_is_caught(tmp_path: Path) -> None:
    root = tmp_path / "harness_agent"
    shutil.copytree(PACKAGE_DIR, root, ignore=shutil.ignore_patterns("__pycache__"))
    target = root / "cli" / "app.py"
    target.write_text(
        "import importlib\nimportlib.import_module('litellm')\n" + target.read_text("utf-8"),
        "utf-8",
    )

    assert scan_everything_else(root, root / "adapters" / "providers") != []


def test_mutation_an_sdk_import_in_the_core_is_caught(tmp_path: Path) -> None:
    root = tmp_path / "harness_agent"
    shutil.copytree(PACKAGE_DIR, root, ignore=shutil.ignore_patterns("__pycache__"))
    target = root / "core" / "entities.py"
    target.write_text("import litellm\n" + target.read_text("utf-8"), "utf-8")

    assert scan_everything_else(root, root / "adapters" / "providers") != []


def test_the_real_sources_were_not_edited_by_the_mutations() -> None:
    source = (PROVIDERS_DIR / "litellm_provider.py").read_text(encoding="utf-8")

    assert "import litellm" not in source
    assert "print(" not in source
