"""LiteLLM must not print its own help text in the terminal (HU-06-02 / UX-a)."""

from __future__ import annotations

import importlib
import logging
import types
from collections.abc import Iterator
from typing import Any

import pytest

from harness_agent.adapters.providers.litellm_provider import LiteLLMProvider

LOGGER_NAMES = ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy")


def fake_litellm() -> types.ModuleType:
    module = types.ModuleType("litellm")
    module.suppress_debug_info = False  # type: ignore[attr-defined]

    async def acompletion(**_: Any) -> Any:  # pragma: no cover - never called
        raise AssertionError

    module.acompletion = acompletion  # type: ignore[attr-defined]
    return module


@pytest.fixture
def loaded(monkeypatch: pytest.MonkeyPatch) -> Iterator[types.ModuleType]:
    module = fake_litellm()
    real = importlib.import_module

    def import_module(name: str, package: str | None = None) -> types.ModuleType:
        return module if name == "litellm" else real(name, package)

    monkeypatch.setattr(importlib, "import_module", import_module)
    saved = {
        name: (logging.getLogger(name).level, logging.getLogger(name).propagate)
        for name in LOGGER_NAMES
    }
    yield module
    for name, (level, propagate) in saved.items():
        logging.getLogger(name).setLevel(level)
        logging.getLogger(name).propagate = propagate


def test_loading_the_library_silences_its_debug_info(loaded: types.ModuleType) -> None:
    LiteLLMProvider("openai/modelo", max_output_tokens=10)

    assert loaded.suppress_debug_info is True


def test_loading_the_library_silences_its_loggers(loaded: types.ModuleType) -> None:
    LiteLLMProvider("openai/modelo", max_output_tokens=10)

    for name in LOGGER_NAMES:
        logger = logging.getLogger(name)
        assert logger.level >= logging.CRITICAL
        assert logger.propagate is False


def test_an_injected_completion_does_not_load_the_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(name: str, package: str | None = None) -> types.ModuleType:  # pragma: no cover
        raise AssertionError(name)

    monkeypatch.setattr(importlib, "import_module", refuse)

    async def completion(**_: Any) -> Any:  # pragma: no cover - never called
        raise AssertionError

    LiteLLMProvider("openai/modelo", max_output_tokens=10, completion=completion)
