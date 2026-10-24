"""Keeps LiteLLM from downloading its tokenizer file during the tests (HU-07-02).

LiteLLM 1.106.2 asks for the ``cl100k_base`` encoding of ``tiktoken`` on every provider path
(``litellm.main._get_encoding``). That file is not bundled with the package: the first time it is
needed it is downloaded from the network into the folder of the package. A test must never reach
the network, and a fresh environment (the CI) does not have the file, so the tests that run the
real library replace the encoding with this offline stand-in. The responses of the tests carry
their own ``usage``, so no real token count is needed.

The stand-in is applied only to the module attribute LiteLLM reads; nothing is written to disk.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterable
from typing import Any

import pytest


class OfflineEncoding:
    """A tokenizer that counts words: enough for the code paths that only need a number."""

    name = "cl100k_base"

    def encode(self, text: str, **kwargs: Any) -> list[int]:
        return list(range(len(text.split())))

    def decode(self, tokens: Iterable[int], **kwargs: Any) -> str:
        return ""


def keep_litellm_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the lazily loaded encoding of LiteLLM; a no-op if the library is not loaded."""
    if "litellm" not in sys.modules:
        return
    main = importlib.import_module("litellm.main")
    monkeypatch.setattr(main, "_encoding_cache", OfflineEncoding())
