"""Guards shared by the LiteLLM adapter tests (HU-07-02).

No test of this package may reach the network: name resolution and ``create_connection`` are how
real traffic leaves (``socket.connect`` is not patched because asyncio builds its self-pipe with a
loopback ``socketpair``). The price table of LiteLLM is never downloaded.
"""

from __future__ import annotations

import os
import socket

import pytest

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the adapter tests must not open network connections")

    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
