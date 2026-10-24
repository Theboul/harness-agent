"""The providers admitted by the configuration, with the additions of HU-07-02 (FR-013, FR-014).

``PROVIDER_KEY_VARIABLES`` is the only place that knows provider names. HU-07-02 extends it with
providers that have a free tier or run locally; the three original entries do not change.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import (
    PROVIDER_KEY_VARIABLES,
    InvalidConfigError,
    MissingKeyError,
    Secret,
    load_config,
)
from tests.unit.config_support import SENTINEL, write_config

HIDDEN = "<secreto oculto>"
KEYED = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


class TestTheTable:
    def test_it_holds_exactly_the_admitted_providers(self) -> None:
        assert dict(PROVIDER_KEY_VARIABLES) == {
            "anthropic": "ANTHROPIC_API_KEY",
            "fake": None,
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "ollama": None,
        }

    def test_the_original_entries_did_not_change(self) -> None:
        assert PROVIDER_KEY_VARIABLES["anthropic"] == "ANTHROPIC_API_KEY"
        assert PROVIDER_KEY_VARIABLES["openai"] == "OPENAI_API_KEY"
        assert PROVIDER_KEY_VARIABLES["fake"] is None

    def test_the_table_is_read_only(self) -> None:
        with pytest.raises(TypeError):
            PROVIDER_KEY_VARIABLES["otro"] = None  # type: ignore[index]


class TestProvidersWithAKey:
    @pytest.mark.parametrize(("provider", "variable"), sorted(KEYED.items()))
    def test_the_key_comes_from_its_variable_and_travels_in_a_secret(
        self, tmp_path: Path, provider: str, variable: str
    ) -> None:
        path = write_config(tmp_path, f'model = "{provider}/x"\n')

        config = load_config(path, environ={variable: SENTINEL})

        assert config.model == f"{provider}/x"
        assert config.key_variable == variable
        assert isinstance(config.api_key, Secret)
        assert config.api_key.reveal() == SENTINEL
        assert SENTINEL not in repr(config)
        assert HIDDEN in repr(config)

    @pytest.mark.parametrize(("provider", "variable"), sorted(KEYED.items()))
    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_a_missing_empty_or_blank_variable_fails_closed(
        self, tmp_path: Path, provider: str, variable: str, value: str | None
    ) -> None:
        path = write_config(tmp_path, f'model = "{provider}/x"\n')
        environ = {} if value is None else {variable: value}

        with pytest.raises(MissingKeyError) as raised:
            load_config(path, environ=environ)

        assert raised.value.variable == variable
        assert raised.value.provider == provider

    @pytest.mark.parametrize(("provider", "variable"), sorted(KEYED.items()))
    def test_the_variable_of_another_provider_does_not_serve(
        self, tmp_path: Path, provider: str, variable: str
    ) -> None:
        path = write_config(tmp_path, f'model = "{provider}/x"\n')
        others = {name: SENTINEL for name in KEYED.values() if name != variable}

        with pytest.raises(MissingKeyError):
            load_config(path, environ=others)


class TestProvidersWithoutAKey:
    @pytest.mark.parametrize("provider", ["fake", "ollama"])
    def test_no_variable_is_needed_and_no_key_is_kept(self, tmp_path: Path, provider: str) -> None:
        path = write_config(tmp_path, f'model = "{provider}/x"\n')

        config = load_config(path, environ={})

        assert config.api_key is None
        assert config.key_variable is None

    def test_a_local_provider_ignores_the_keys_that_are_defined(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, 'model = "ollama/x"\n')

        config = load_config(path, environ={"GROQ_API_KEY": SENTINEL})

        assert config.api_key is None
        assert SENTINEL not in repr(config)


class TestAProviderThatIsNotInTheTable:
    def test_it_still_fails_closed_and_lists_the_admitted_ones(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, 'model = "otro/x"\n')

        with pytest.raises(InvalidConfigError) as raised:
            load_config(path, environ={})

        (problem,) = raised.value.problems
        assert problem.field == "model"
        for provider in PROVIDER_KEY_VARIABLES:
            assert provider in problem.message
        assert "otro" not in problem.message
