"""Boundaries after widening the Provider port (HU-00-03 / T009).

``core/`` stays pure: no module imports ``tests``, ``cli`` or ``adapters``, and ``provider.py``
only uses the standard library. The simulated provider only depends on the standard library, the
core and its sibling double.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "src" / "harness_agent" / "core"
PROVIDER_PORT = CORE / "interfaces" / "provider.py"
FAKE_PROVIDER = ROOT / "tests" / "doubles" / "fake_provider.py"

STDLIB = set(sys.stdlib_module_names) | {"__future__"}
CORE_FORBIDDEN_ROOTS = {"tests"}
CORE_FORBIDDEN_PREFIXES = ("harness_agent.cli", "harness_agent.adapters")


def imported_modules(source: str) -> list[str]:
    """Dotted names imported by ``source``; relative imports keep their leading dots."""
    modules: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append("." * node.level + (node.module or ""))
    return modules


def core_violations(source: str) -> list[str]:
    """Imports that a ``core/`` module must not have."""
    found: list[str] = []
    for module in imported_modules(source):
        root = module.split(".")[0]
        if root in CORE_FORBIDDEN_ROOTS or module.startswith(CORE_FORBIDDEN_PREFIXES):
            found.append(module)
    return found


def non_stdlib_outside_core(source: str, allowed: tuple[str, ...]) -> list[str]:
    """Imports that are neither the standard library nor one of the ``allowed`` prefixes."""
    found: list[str] = []
    for module in imported_modules(source):
        if module.startswith("."):
            found.append(module)
        elif module.split(".")[0] in STDLIB:
            continue
        elif not module.startswith(allowed):
            found.append(module)
    return found


def test_no_core_module_imports_tests_cli_or_adapters() -> None:
    files = sorted(CORE.rglob("*.py"))
    assert len(files) >= 18

    offenders = {
        str(path.relative_to(ROOT)): hits
        for path in files
        if (hits := core_violations(path.read_text(encoding="utf-8")))
    }

    assert offenders == {}


def test_the_provider_port_only_uses_the_standard_library_and_the_core() -> None:
    source = PROVIDER_PORT.read_text(encoding="utf-8")

    assert non_stdlib_outside_core(source, allowed=("harness_agent.core",)) == []


def test_the_fake_provider_only_uses_the_standard_library_the_core_and_its_sibling_double() -> None:
    source = FAKE_PROVIDER.read_text(encoding="utf-8")

    assert (
        non_stdlib_outside_core(
            source, allowed=("harness_agent.core", "tests.doubles.scripted_provider")
        )
        == []
    )


def test_the_fake_provider_does_not_use_the_network_the_clock_or_randomness() -> None:
    roots = {module.split(".")[0] for module in imported_modules(FAKE_PROVIDER.read_text())}

    assert roots.isdisjoint({"socket", "ssl", "http", "urllib", "random", "secrets", "time"})
    assert roots.isdisjoint({"os", "asyncio", "datetime", "uuid", "litellm", "openai"})


# --- detector self-tests: the detectors must catch what they claim to catch -------------------


def test_core_detector_catches_each_forbidden_import() -> None:
    for line in (
        "import tests.doubles",
        "from tests.doubles import FakeProvider",
        "import harness_agent.cli",
        "from harness_agent.cli import render",
        "from harness_agent.adapters.converters import base",
    ):
        assert core_violations(line), line


def test_core_detector_lets_the_allowed_imports_through() -> None:
    for line in (
        "import copy",
        "from dataclasses import dataclass",
        "from harness_agent.core.entities import Message",
        "from . import entities",
    ):
        assert core_violations(line) == [], line


def test_stdlib_detector_catches_third_party_and_relative_imports() -> None:
    allowed = ("harness_agent.core",)
    for line in ("import litellm", "from openai import OpenAI", "from . import x"):
        assert non_stdlib_outside_core(line, allowed), line
    for line in ("import copy", "from harness_agent.core.entities import Message"):
        assert non_stdlib_outside_core(line, allowed) == [], line
