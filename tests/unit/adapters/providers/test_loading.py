"""Lazy loading of LiteLLM (HU-07-02 / FR-003, FR-017).

LiteLLM is an optional dependency: importing the adapter module never imports it, an injected
completion function never needs it, and its absence is reported with the install command.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from harness_agent.adapters.providers.litellm_provider import (
    LiteLLMProvider,
    ProviderDependencyError,
)
from harness_agent.core import ProviderError
from tests.unit.adapters.providers.support import MAX_OUTPUT_TOKENS, MODEL

SRC = Path(__file__).resolve().parents[4] / "src"


async def fake_acompletion(**kwargs: Any) -> Any:
    return {"choices": []}


class TestTheModuleImportIsLazy:
    def test_importing_the_adapter_does_not_import_litellm(self) -> None:
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]);"
            "import harness_agent.adapters.providers.litellm_provider;"
            "assert 'litellm' not in sys.modules"
        )

        result = subprocess.run(
            [sys.executable, "-c", code, str(SRC)], capture_output=True, text=True, check=False
        )

        assert result.returncode == 0, result.stderr

    def test_an_injected_function_never_needs_the_library(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "litellm", None)

        provider = LiteLLMProvider(
            MODEL, max_output_tokens=MAX_OUTPUT_TOKENS, completion=fake_acompletion
        )

        assert provider.completion is fake_acompletion


class TestTheDefaultFunction:
    def test_it_is_the_async_completion_of_the_library(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_acompletion))

        provider = LiteLLMProvider(MODEL, max_output_tokens=MAX_OUTPUT_TOKENS)

        assert provider.completion is fake_acompletion


class TestAMissingLibrary:
    def test_it_fails_when_the_adapter_is_built_with_the_install_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "litellm", None)

        with pytest.raises(ProviderDependencyError) as raised:
            LiteLLMProvider(MODEL, max_output_tokens=MAX_OUTPUT_TOKENS)

        message = str(raised.value)
        assert 'pip install -e ".[litellm]"' in message
        assert "ruta corta" in message
        assert "C:\\tmp" in message

    def test_the_original_import_error_is_kept_as_the_cause(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "litellm", None)

        with pytest.raises(ProviderDependencyError) as raised:
            LiteLLMProvider(MODEL, max_output_tokens=MAX_OUTPUT_TOKENS)

        assert isinstance(raised.value.__cause__, ImportError)

    def test_it_is_a_construction_failure_not_a_provider_failure(self) -> None:
        assert not issubclass(ProviderDependencyError, ProviderError)
        assert issubclass(ProviderDependencyError, Exception)
