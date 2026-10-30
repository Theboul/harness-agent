"""Domain errors and settings of the MCP adapter (HU-08-01 / FR-004, FR-009)."""

from __future__ import annotations

import dataclasses

import pytest

from harness_agent.adapters.mcp import (
    McpConnectError,
    McpDependencyError,
    McpError,
    McpServerSettings,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
CODES = ("no_se_pudo_iniciar", "cerro_al_arrancar", "sin_respuesta", "fallo")


class TestConnectError:
    @pytest.mark.parametrize("code", CODES)
    def test_the_text_is_a_fixed_sentence_in_spanish_that_names_the_server(self, code: str) -> None:
        error = McpConnectError("demo", code)

        assert isinstance(error, McpError)
        assert "'demo'" in str(error)
        assert "Se continúa sin sus herramientas." in str(error)
        assert error.code == code
        assert error.server == "demo"

    def test_each_code_has_its_own_text(self) -> None:
        texts = {str(McpConnectError("demo", code)) for code in CODES}

        assert len(texts) == len(CODES)

    def test_an_unknown_code_falls_back_to_the_generic_text(self) -> None:
        assert str(McpConnectError("demo", "inventado")) == str(McpConnectError("demo", "fallo"))

    def test_the_text_never_holds_anything_but_the_name_and_fixed_words(self) -> None:
        text = str(McpConnectError("demo", "fallo"))

        assert SENTINEL not in text


class TestDependencyError:
    def test_it_names_the_extra_to_install(self) -> None:
        error = McpDependencyError("demo")

        assert isinstance(error, McpError)
        assert 'pip install ".[mcp]"' in str(error)
        assert "'demo'" in str(error)


class TestSettings:
    def test_the_defaults_are_the_ones_proposed_by_spk_04(self) -> None:
        settings = McpServerSettings(name="demo", command="python")

        assert settings.args == ()
        assert settings.env_names == ()
        assert settings.startup_timeout_s == 15
        assert settings.call_timeout_s == 60
        assert settings.close_timeout_s == 10

    def test_it_is_immutable(self) -> None:
        settings = McpServerSettings(name="demo", command="python")

        with pytest.raises(dataclasses.FrozenInstanceError):
            settings.command = "otro"  # type: ignore[misc]
