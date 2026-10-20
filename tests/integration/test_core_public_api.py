"""Public API of ``core.tools`` and its re-export from ``core`` (HU-01-02 / T018).

``core.tools`` re-exports the registry, its errors, ``Violation`` and the two functions of the
validator; ``core`` re-exports the registry, the errors and ``Violation`` (contract, section 1).
The helpers that the package keeps for itself, such as ``clip``, are not public API. Every module
must also import in a fresh interpreter on its own, which proves that there are no import cycles.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import harness_agent.core as core
import harness_agent.core.tools as tools
from harness_agent.core.tools import errors, registry, schema_validator

SRC = Path(__file__).resolve().parents[2] / "src"

TOOLS_API = {
    "InMemoryToolRegistry",
    "ToolRegistryError",
    "InvalidToolDefinitionError",
    "DuplicateToolError",
    "UnknownToolError",
    "ToolValidationError",
    "Violation",
    "check_schema",
    "validate_arguments",
}
CORE_REEXPORTS = TOOLS_API - {"check_schema", "validate_arguments"}


# --- core.tools --------------------------------------------------------------------------------


def test_core_tools_exports_exactly_the_public_api() -> None:
    assert set(tools.__all__) == TOOLS_API
    assert len(tools.__all__) == len(TOOLS_API)  # no repeated name
    for name in tools.__all__:
        assert hasattr(tools, name), name


def test_the_exported_symbols_are_the_ones_defined_in_their_modules() -> None:
    assert tools.InMemoryToolRegistry is registry.InMemoryToolRegistry
    assert tools.Violation is errors.Violation
    for name in (
        "ToolRegistryError",
        "InvalidToolDefinitionError",
        "DuplicateToolError",
        "UnknownToolError",
        "ToolValidationError",
    ):
        assert getattr(tools, name) is getattr(errors, name), name
    assert tools.check_schema is schema_validator.check_schema
    assert tools.validate_arguments is schema_validator.validate_arguments


def test_the_helpers_of_the_package_are_not_public_api() -> None:
    assert "clip" not in tools.__all__
    assert "clip" not in core.__all__
    assert not hasattr(tools, "clip")
    assert not hasattr(core, "clip")


# --- core --------------------------------------------------------------------------------------


def test_core_reexports_the_registry_the_errors_and_violation() -> None:
    for name in CORE_REEXPORTS:
        assert name in core.__all__, name
        assert getattr(core, name) is getattr(tools, name), name


def test_core_leaves_the_validator_functions_in_core_tools() -> None:
    for name in ("check_schema", "validate_arguments"):
        assert name not in core.__all__, name


def test_core_has_no_repeated_name_in_its_public_api() -> None:
    assert len(core.__all__) == len(set(core.__all__))
    for name in core.__all__:
        assert hasattr(core, name), name


# --- No import cycles ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "statement",
    [
        "import harness_agent",
        "import harness_agent.core",
        "import harness_agent.core.tools",
        "import harness_agent.core.tools.registry",
        "import harness_agent.core.tools.errors",
        "import harness_agent.core.tools.schema_validator",
        "from harness_agent.core import InMemoryToolRegistry, ToolRegistryError, Violation",
    ],
)
def test_a_fresh_interpreter_runs_the_import_on_its_own(statement: str, tmp_path: Path) -> None:
    # Hermetic on purpose, so that it means the same on Linux and on Windows: no site (``-S``: no
    # site-packages and no ``.pth`` of an editable install, which would find the package even if
    # the path below were wrong), the source folder as the one and only PYTHONPATH (not ``-I``,
    # which ignores PYTHONPATH) and an empty working directory instead of the repository root.
    env = {**os.environ, "PYTHONPATH": str(SRC)}

    result = subprocess.run(
        [sys.executable, "-S", "-c", statement],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
