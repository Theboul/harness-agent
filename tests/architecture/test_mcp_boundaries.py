"""Boundaries of ``adapters/mcp/`` and of the import of the MCP SDK (HU-08-01 / T012).

``mcp`` is an optional dependency and the adapter is the one place that talks to it. Rules:

* No file of ``src/harness_agent/`` has a static ``import`` of ``mcp`` (so ``core/`` never sees it
  and importing the adapter never needs the library).
* ``importlib.import_module("mcp...")`` appears only inside a function of
  ``adapters/mcp/sdk.py``: the load is lazy and in one place.
* ``adapters/mcp/`` imports only the standard library, the public API of the core and its own
  package: no ``config``, ``cli``, ``observability``, ``bootstrap`` or other adapter. It reads no
  environment or configuration and does not use the terminal. The only module that opens a file is
  ``stderr_log.py`` and it opens it for writing.
* Cancellation is never swallowed: every handler of ``CancelledError`` ends with ``raise``, and
  nothing catches ``BaseException`` or uses a bare ``except``.
* Only ``bootstrap.py`` (the composition root) builds a ``McpStdioClient``.

Why not ``GUARDED`` of ``test_adapters_boundaries.py``: this package has its own rules (the lazy
SDK load, the write-only log). The detectors of that module are reused, not copied, and each rule
has a self-test and a mutation test on a copy of the real package.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

from tests.architecture.test_adapters_boundaries import guarded_imports, imported_modules
from tests.architecture.test_bootstrap_boundaries import importers_of
from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
MCP_DIR = PACKAGE_DIR / "adapters" / "mcp"
MCP_PACKAGE = "harness_agent.adapters.mcp"
SDK_LOADER = "sdk.py"
LOG_MODULE = "stderr_log.py"
SDK = "mcp"


def package_of(path: Path, root: Path) -> str:
    """Dotted package of ``path``; ``root`` is the folder that holds ``harness_agent``."""
    return ".".join(path.relative_to(root).parts[:-1])


def static_sdk_imports(source: str, package: str) -> list[str]:
    """``import`` statements of the MCP SDK, wherever they are in the file."""
    return [
        f"{module} at line {line}"
        for module, line in imported_modules(source, package)
        if module.split(".")[0] == SDK
    ]


class _DynamicImports(ast.NodeVisitor):
    """Calls to ``import_module`` / ``__import__`` with the SDK as a literal argument."""

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
        if name in {"import_module", "__import__"} and node.args:
            first = node.args[0]
            if (
                isinstance(first, ast.Constant)
                and isinstance(first.value, str)
                and first.value.split(".")[0] == SDK
            ):
                self.found.append((node.lineno, self.depth > 0))
        self.generic_visit(node)


def dynamic_sdk_imports(source: str) -> list[tuple[int, bool]]:
    """``(line, inside_a_function)`` of every dynamic import of the SDK."""
    visitor = _DynamicImports()
    visitor.visit(ast.parse(source))
    return visitor.found


def _is_cancelled(node: ast.expr | None) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr == "CancelledError"
    return isinstance(node, ast.Name) and node.id == "CancelledError"


def swallowed_cancellations(source: str) -> list[str]:
    """Handlers that catch everything or catch ``CancelledError`` without re-raising it."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ExceptHandler):
            continue
        caught = node.type
        if caught is None or (isinstance(caught, ast.Name) and caught.id == "BaseException"):
            found.append(f"catches everything at line {node.lineno}")
        elif _is_cancelled(caught) and not isinstance(node.body[-1], ast.Raise):
            found.append(f"CancelledError not re-raised at line {node.lineno}")
    return found


def log_opens_not_for_writing(source: str) -> list[str]:
    """Calls to ``open`` whose mode is not the literal ``"w"``."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open"
        ):
            mode = node.args[1] if len(node.args) > 1 else None
            if not (isinstance(mode, ast.Constant) and mode.value == "w"):
                found.append(f"open without the literal mode 'w' at line {node.lineno}")
    return found


def scan_mcp(directory: Path) -> list[str]:
    """Every rule of ``adapters/mcp/`` over the ``.py`` files of ``directory``."""
    files = sorted(directory.rglob("*.py"))
    assert files, f"No Python files found under {directory}"
    violations: list[str] = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        label = path.name
        violations.extend(
            f"{label}: SDK import {m}" for m in static_sdk_imports(source, MCP_PACKAGE)
        )
        violations.extend(f"{label}: {m}" for m in guarded_imports(source, MCP_PACKAGE))
        violations.extend(f"{label}: {m}" for m in terminal_uses(source))
        violations.extend(f"{label}: {m}" for m in swallowed_cancellations(source))
        violations.extend(
            f"{label}: dynamic import of the SDK outside a function (line {line})"
            for line, inside in dynamic_sdk_imports(source)
            if not inside
        )
        if path.name != SDK_LOADER:
            violations.extend(
                f"{label}: dynamic import of the SDK at line {line}"
                for line, _ in dynamic_sdk_imports(source)
            )
        if path.name == LOG_MODULE:
            violations.extend(f"{label}: {m}" for m in log_opens_not_for_writing(source))
        else:
            violations.extend(
                f"{label}: {m}" for m in find_config_reads(source, label, MCP_PACKAGE)
            )
    return violations


def scan_everything_else(root: Path, mcp_dir: Path) -> list[str]:
    """No static SDK import anywhere, and no dynamic one outside ``adapters/mcp/``."""
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        package = package_of(path, root.parent)
        relative = path.relative_to(root)
        violations.extend(f"{relative}: {m}" for m in static_sdk_imports(source, package))
        if mcp_dir not in path.parents:
            violations.extend(
                f"{relative}: dynamic import of the SDK at line {line}"
                for line, _ in dynamic_sdk_imports(source)
            )
    return violations


# --- the real code --------------------------------------------------------------------------


def test_the_package_exists_with_the_adapter() -> None:
    assert (MCP_DIR / "client.py").is_file()
    assert (MCP_DIR / SDK_LOADER).is_file()
    assert (MCP_DIR / "__init__.py").is_file()


def test_adapters_mcp_respects_every_rule() -> None:
    assert scan_mcp(MCP_DIR) == []


def test_no_file_of_the_package_imports_the_sdk_statically_nor_loads_it_elsewhere() -> None:
    assert scan_everything_else(PACKAGE_DIR, MCP_DIR) == []


def test_the_sdk_is_loaded_in_the_loader_and_inside_a_function() -> None:
    found = dynamic_sdk_imports((MCP_DIR / SDK_LOADER).read_text(encoding="utf-8"))

    assert found
    assert all(inside for _, inside in found)


def test_only_the_composition_root_builds_the_client() -> None:
    importers = importers_of(PACKAGE_DIR, MCP_PACKAGE)

    outside = {name for name in importers if not name.startswith(MCP_PACKAGE)}
    assert outside == {"harness_agent.bootstrap"}


def test_the_core_does_not_know_the_sdk() -> None:
    assert scan_everything_else(PACKAGE_DIR / "core", MCP_DIR) == []


# --- the detectors, on synthetic fragments ----------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "import mcp\n",
        "from mcp import ClientSession\n",
        "from mcp.client.stdio import stdio_client\n",
    ],
)
def test_a_static_import_of_the_sdk_is_detected(source: str) -> None:
    assert static_sdk_imports(source, MCP_PACKAGE)


def test_other_imports_are_not_taken_for_the_sdk() -> None:
    assert static_sdk_imports("import mcpx\nimport asyncio\n", MCP_PACKAGE) == []


def test_a_dynamic_import_is_located_inside_or_outside_a_function() -> None:
    source = (
        "import importlib\n"
        "top = importlib.import_module('mcp')\n"
        "def lazy():\n    return importlib.import_module('mcp.client.stdio')\n"
    )

    assert dynamic_sdk_imports(source) == [(2, False), (4, True)]


def test_a_dynamic_import_of_something_else_is_not_reported() -> None:
    assert dynamic_sdk_imports("import importlib\nimportlib.import_module('json')\n") == []


@pytest.mark.parametrize(
    "source",
    [
        "try:\n    pass\nexcept:\n    pass\n",
        "try:\n    pass\nexcept BaseException:\n    pass\n",
        "import asyncio\ntry:\n    pass\nexcept asyncio.CancelledError:\n    print(1)\n",
        "try:\n    pass\nexcept CancelledError:\n    pass\n",
    ],
)
def test_swallowing_the_cancellation_is_detected(source: str) -> None:
    assert swallowed_cancellations(source)


def test_reraising_the_cancellation_is_fine() -> None:
    source = (
        "import asyncio\ntry:\n    pass\nexcept asyncio.CancelledError:\n    x = 1\n    raise\n"
    )

    assert swallowed_cancellations(source) == []


def test_opening_a_file_for_anything_but_writing_is_detected() -> None:
    assert log_opens_not_for_writing("open('a')\n")
    assert log_opens_not_for_writing("open('a', 'r')\n")
    assert log_opens_not_for_writing("open('a', 'w')\n") == []


# --- each rule fails on a real mutation --------------------------------------------------------


@pytest.fixture
def copy_of_the_package(tmp_path: Path) -> Path:
    destination = tmp_path / "harness_agent"
    shutil.copytree(PACKAGE_DIR, destination, ignore=shutil.ignore_patterns("__pycache__"))
    return destination


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


@pytest.mark.parametrize(
    ("file", "addition", "expected"),
    [
        ("client.py", "\nimport mcp\n", "SDK import"),
        ("client.py", "\nfrom harness_agent.config import HarnessConfig\n", "harness_agent.config"),
        (
            "client.py",
            "\nfrom harness_agent.adapters.tools import ReadFileTool\n",
            "adapters.tools",
        ),
        ("client.py", "\nimport os\nVALUE = os.environ['X']\n", "environ"),
        ("client.py", "\nprint('hola')\n", "print"),
        ("client.py", "\nimport importlib\nOTHER = importlib.import_module('mcp')\n", "dynamic"),
        ("translate.py", "\nimport importlib\nOTHER = importlib.import_module('mcp')\n", "dynamic"),
        ("connections.py", "\ntry:\n    pass\nexcept:\n    pass\n", "catches everything"),
        ("stderr_log.py", "\nSOURCE = open('x')\n", "mode 'w'"),
    ],
)
def test_each_rule_fails_on_a_mutation_of_the_real_package(
    copy_of_the_package: Path, file: str, addition: str, expected: str
) -> None:
    mcp_copy = copy_of_the_package / "adapters" / "mcp"
    append(mcp_copy / file, addition)

    violations = scan_mcp(mcp_copy) + scan_everything_else(copy_of_the_package, mcp_copy)

    assert any(expected in message for message in violations), violations


def test_a_static_import_of_the_sdk_in_the_core_is_detected(copy_of_the_package: Path) -> None:
    append(copy_of_the_package / "core" / "entities.py", "\nimport mcp\n")

    violations = scan_everything_else(copy_of_the_package / "core", MCP_DIR)

    assert violations


# --- HU-08-02: a remote tool never lowers its own risk ------------------------------------------


def risk_levels_named(source: str) -> set[str]:
    """Members of ``RiskLevel`` written as ``RiskLevel.X`` anywhere in ``source``."""
    return {
        node.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "RiskLevel"
    }


def test_the_translated_tool_names_only_the_high_risk() -> None:
    source = (MCP_DIR / "tool.py").read_text(encoding="utf-8")

    assert risk_levels_named(source) == {"HIGH"}


def test_naming_a_lower_risk_is_detected() -> None:
    assert risk_levels_named("x = RiskLevel.LOW\ny = RiskLevel.HIGH") == {"LOW", "HIGH"}


def test_only_the_composition_root_calls_the_registration() -> None:
    callers = {
        path.name
        for path in PACKAGE_DIR.rglob("*.py")
        if "register_mcp_tools(" in path.read_text(encoding="utf-8")
    }

    assert callers == {"bootstrap.py", "registration.py"}  # the call and the definition
