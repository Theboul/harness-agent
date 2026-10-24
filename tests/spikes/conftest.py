"""Fixtures of the spikes: the LiteLLM spike (SPK-01) must not download the tokenizer file."""

from __future__ import annotations

import pytest

from tests.litellm_offline import keep_litellm_offline


@pytest.fixture(autouse=True)
def litellm_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    keep_litellm_offline(monkeypatch)
