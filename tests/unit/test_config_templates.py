"""Tests for the templates ``config.example.toml`` and ``.env.example`` (HU-00-04 / T017).

The templates are the only configuration files that are versioned. The file template must load
without error and give exactly the default values of the schema; the environment template lists
the key variable of every provider that needs one (and only those), empty, and no template holds
anything that looks like a key.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from harness_agent.config import PROVIDER_KEY_VARIABLES, Limits, load_config

ROOT = Path(__file__).resolve().parents[2]
CONFIG_TEMPLATE = ROOT / "config.example.toml"
ENV_TEMPLATE = ROOT / ".env.example"
SCHEMA_FIELDS = {
    "model",
    "limits.max_turns",
    "limits.max_seconds",
    "limits.max_tokens",
    "paths.sessions_db",
}


def text_of(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def code_lines(path: Path) -> list[str]:
    lines = (line.strip() for line in text_of(path).splitlines())
    return [line for line in lines if line and not line.startswith("#")]


class TestConfigExample:
    def test_the_template_exists(self) -> None:
        assert CONFIG_TEMPLATE.is_file()

    def test_the_template_loads_without_error_and_gives_the_defaults(self) -> None:
        config = load_config(CONFIG_TEMPLATE, environ={})

        assert config.model == "fake/test"
        assert config.limits == Limits(max_turns=30, max_seconds=600, max_tokens=200000)
        assert config.paths.workspace_root is None
        assert config.paths.sessions_db == ROOT / ".harness" / "sessions.db"
        assert config.api_key is None

    def test_the_template_declares_every_field_of_the_schema_with_its_default(self) -> None:
        raw = tomllib.loads(text_of(CONFIG_TEMPLATE))

        declared = {
            "model": raw["model"],
            "limits.max_turns": raw["limits"]["max_turns"],
            "limits.max_seconds": raw["limits"]["max_seconds"],
            "limits.max_tokens": raw["limits"]["max_tokens"],
            "paths.sessions_db": raw["paths"]["sessions_db"],
        }
        assert set(declared) == SCHEMA_FIELDS
        assert set(raw) == {"model", "limits", "paths"}
        assert set(raw["limits"]) == {"max_turns", "max_seconds", "max_tokens"}
        assert set(raw["paths"]) == {"sessions_db"}
        assert declared == {
            "model": "fake/test",
            "limits.max_turns": 30,
            "limits.max_seconds": 600,
            "limits.max_tokens": 200000,
            "paths.sessions_db": ".harness/sessions.db",
        }

    def test_the_workspace_root_appears_commented_with_its_explanation(self) -> None:
        lines = text_of(CONFIG_TEMPLATE).splitlines()

        commented = [line for line in lines if line.startswith("#") and "workspace_root" in line]

        assert any(line.lstrip("# ").startswith("workspace_root") for line in commented)
        assert any("área" in line for line in lines if line.startswith("#"))

    def test_the_header_says_to_copy_it_and_that_it_holds_no_keys(self) -> None:
        header = " ".join(text_of(CONFIG_TEMPLATE).splitlines()[:8])

        assert "config.toml" in header
        assert "clave" in header


class TestEnvExample:
    def test_the_template_exists(self) -> None:
        assert ENV_TEMPLATE.is_file()

    def test_it_names_every_key_variable_of_the_providers_and_only_those(self) -> None:
        expected = {variable for variable in PROVIDER_KEY_VARIABLES.values() if variable}

        names = {line.partition("=")[0] for line in code_lines(ENV_TEMPLATE)}

        assert names == expected

    def test_every_variable_is_empty(self) -> None:
        for line in code_lines(ENV_TEMPLATE):
            assert line.endswith("="), line
            assert line.partition("=")[2] == ""

    def test_it_explains_how_to_load_the_variables_and_that_dotenv_is_not_read(self) -> None:
        text = text_of(ENV_TEMPLATE)

        assert "PowerShell" in text
        assert "bash" in text
        assert ".env" in text
        assert "no lee" in text


class TestSinPatronesDeClave:
    @pytest.mark.parametrize("template", [CONFIG_TEMPLATE, ENV_TEMPLATE], ids=lambda p: p.name)
    def test_a_template_holds_nothing_with_the_shape_of_a_key(self, template: Path) -> None:
        text = text_of(template)

        assert "sk-" not in text
        assert "AKIA" not in text
        assert "PRIVATE KEY" not in text
