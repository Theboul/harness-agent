"""``HARNESS_DEBUG_PROVIDER`` in the composition root (HU-06-07 / FR-001, AC-01, AC-05).

Off by default; on, the detail of a failed provider call goes to standard error as one line with
the secrets hidden. Nothing is written to disk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.bootstrap import Composition, compose
from harness_agent.config import Secret
from harness_agent.core import Provider, ProviderResponse
from tests.unit.bootstrap_support import SENTINEL, make_config


def capture_debug(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    seen: list[Any] = []

    class RecordingProvider(Provider):
        def __init__(self, model: str, *, debug: Any = None, **_: Any) -> None:
            seen.append(debug)

        async def complete(self, messages: Any, tools: Any = None) -> ProviderResponse:
            return ProviderResponse(content="x")

    monkeypatch.setattr(bootstrap, "LiteLLMProvider", RecordingProvider)
    return seen


@pytest.mark.parametrize("value", ["1", "true", "TRUE", " yes ", "on", "si", "sí"])
def test_a_true_value_gives_the_provider_a_sink_that_writes_one_clean_line_to_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    value: str,
) -> None:
    seen = capture_debug(monkeypatch)
    config = make_config(tmp_path, workspace=tmp_path, api_key=Secret(SENTINEL))

    composition = compose(config, environ={"HARNESS_DEBUG_PROVIDER": value})
    try:
        seen[0](f"400 bad\nrequest with {SENTINEL} inside")
    finally:
        composition.close()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        captured.err == "[depuración del proveedor] 400 bad request with <secreto oculto> inside\n"
    )
    assert SENTINEL not in captured.err


@pytest.mark.parametrize(
    "env", [{}, {"HARNESS_DEBUG_PROVIDER": "0"}, {"HARNESS_DEBUG_PROVIDER": ""}]
)
def test_without_a_true_value_there_is_no_sink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    seen = capture_debug(monkeypatch)

    composition: Composition = compose(make_config(tmp_path, workspace=tmp_path), environ=env)
    composition.close()

    assert seen == [None]
