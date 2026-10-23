"""Canonical provider error hierarchy (HU-00-03 / T002).

The core defines a minimal hierarchy so that a simulated provider and the real adapters raise the
same types. These tests pin the hierarchy, its public export and the fact that the port stays
additive: ``Provider.complete`` keeps its signature and the module imports only the standard
library.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import harness_agent.core as core
import harness_agent.core.interfaces as interfaces
from harness_agent.core.interfaces import provider as provider_module
from harness_agent.core.interfaces.provider import (
    Provider,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
)

CONCRETE = (QuotaExceeded, ProviderTimeout, ProviderUnavailable)
NAMES = ("ProviderError", "QuotaExceeded", "ProviderTimeout", "ProviderUnavailable")


def test_provider_error_is_an_exception() -> None:
    assert issubclass(ProviderError, Exception)
    assert not issubclass(ProviderError, (QuotaExceeded, ProviderTimeout, ProviderUnavailable))


@pytest.mark.parametrize("error_type", CONCRETE)
def test_concrete_errors_derive_from_provider_error(error_type: type[ProviderError]) -> None:
    assert issubclass(error_type, ProviderError)


def test_concrete_errors_are_distinct_siblings() -> None:
    for first in CONCRETE:
        for second in CONCRETE:
            if first is not second:
                assert not issubclass(first, second)


@pytest.mark.parametrize("error_type", (ProviderError, *CONCRETE))
def test_the_message_is_kept(error_type: type[ProviderError]) -> None:
    error = error_type("mensaje de prueba")
    assert str(error) == "mensaje de prueba"
    assert error.args == ("mensaje de prueba",)


@pytest.mark.parametrize("error_type", CONCRETE)
def test_a_concrete_error_is_caught_as_the_base(error_type: type[ProviderError]) -> None:
    with pytest.raises(ProviderError):
        raise error_type("x")


@pytest.mark.parametrize("name", NAMES)
def test_errors_are_exported_from_core_and_interfaces(name: str) -> None:
    assert name in core.__all__
    assert name in interfaces.__all__
    assert getattr(core, name) is getattr(provider_module, name)
    assert getattr(interfaces, name) is getattr(provider_module, name)


def test_core_public_api_has_no_repeated_names() -> None:
    assert len(core.__all__) == len(set(core.__all__))


def test_provider_complete_signature_is_unchanged() -> None:
    parameters = inspect.signature(Provider.complete).parameters
    assert list(parameters) == ["self", "messages", "tools"]
    assert parameters["tools"].default is None
    assert inspect.iscoroutinefunction(Provider.complete)


def test_provider_module_imports_only_the_standard_library_and_the_core() -> None:
    tree = ast.parse(Path(provider_module.__file__ or "").read_text(encoding="utf-8"))
    allowed_roots = {"__future__", "abc", "dataclasses", "typing", "harness_agent"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            roots = {(node.module or "").split(".")[0]}
        else:
            continue
        assert roots <= allowed_roots, roots
