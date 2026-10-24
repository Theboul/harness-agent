"""The guide of HU-07-02 documents what a person needs to try a real model (requisito 6).

``specs/017-litellm-provider-adapter/quickstart.md`` must say how to avoid the download of the
price table, how long the path of the environment may be on Windows and how to measure it, which
variable each provider needs (or that it needs none), the cap of output tokens and how to run the
manual test of Sp1-45 outside the CI. The provider list is read from ``PROVIDER_KEY_VARIABLES``,
so a provider added later without documenting it fails here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import PROVIDER_KEY_VARIABLES

QUICKSTART = (
    Path(__file__).resolve().parents[2] / "specs" / "017-litellm-provider-adapter" / "quickstart.md"
)
EXAMPLES = ("anthropic", "openai", "gemini", "groq", "openrouter", "ollama")


@pytest.fixture(scope="module")
def text() -> str:
    return QUICKSTART.read_text("utf-8")


def test_the_examples_are_exactly_the_real_providers() -> None:
    assert set(EXAMPLES) == set(PROVIDER_KEY_VARIABLES) - {"fake"}


def test_it_explains_how_to_avoid_the_price_table_download(text: str) -> None:
    assert "LITELLM_LOCAL_MODEL_COST_MAP" in text
    assert "LITELLM_LOCAL_MODEL_COST_MAP=True" in text or "LITELLM_LOCAL_MODEL_COST_MAP = " in text


def test_it_gives_the_path_limit_for_windows_and_how_to_measure_it(text: str) -> None:
    assert "130" in text
    assert "site-packages" in text
    assert "sysconfig" in text
    assert "C:" + chr(92) + "tmp" in text


@pytest.mark.parametrize("provider", EXAMPLES)
def test_each_provider_has_a_row_with_its_variable_or_says_it_needs_none(
    text: str, provider: str
) -> None:
    rows = [line for line in text.splitlines() if line.startswith("|") and f"`{provider}/" in line]
    variable = PROVIDER_KEY_VARIABLES[provider]

    assert rows, f"no table row for {provider}"
    for row in rows:
        assert (variable in row) if variable else ("sin clave" in row), row


def test_it_documents_the_cap_of_output_tokens(text: str) -> None:
    assert "limits.max_output_tokens" in text
    assert "4096" in text


def test_it_documents_the_manual_test_and_that_it_stays_out_of_the_ci(text: str) -> None:
    assert "HARNESS_REAL_MODEL" in text
    assert "test_litellm_real_model_manual.py" in text
    assert "fuera de la CI" in text
    assert "Sp1-45" in text


def test_it_warns_about_the_first_call_downloading_the_tokenizer(text: str) -> None:
    assert "cl100k_base" in text
    assert "CUSTOM_TIKTOKEN_CACHE_DIR" in text
