"""The composition root gives the tool registry the configured output limit (HU-02-02 / T006)."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition
from harness_agent.config import Limits
from harness_agent.core import Role, ToolCall
from harness_agent.core.interfaces.provider import ProviderResponse
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config, one_turn


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


async def read_through_the_loop(
    tmp_path: Path, opened: list[Composition], content: str, limits: Limits | None
) -> str:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    (workspace / "grande.txt").write_text(content, encoding="utf-8", newline="")
    config = make_config(tmp_path, workspace=workspace)
    if limits is not None:
        config = dataclasses.replace(config, limits=limits)
    provider = FakeProvider(
        [
            ProviderResponse(
                tool_calls=[
                    ToolCall(id="c1", name="leer_archivo", arguments={"path": "grande.txt"})
                ]
            ),
            ProviderResponse(content="listo"),
        ]
    )
    result = await one_turn(build(opened, config, provider))
    tool_messages = [m for m in result.history if m.role is Role.TOOL]
    return str(tool_messages[0].content)


class TestTheComposedRegistryBoundsToolResults:
    async def test_the_configured_maximum_is_applied(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        content = "INICIO" + "x" * 5_000 + "FINAL"

        seen = await read_through_the_loop(
            tmp_path, opened, content, Limits(max_tool_output_chars=400)
        )

        assert len(seen) <= 400
        assert seen.startswith("INICIO")
        assert seen.endswith("FINAL")
        assert "[salida recortada: se omitieron " in seen

    async def test_the_default_maximum_cuts_a_file_longer_than_24000_characters(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        content = "a" * 30_000

        seen = await read_through_the_loop(tmp_path, opened, content, limits=None)

        assert 20_000 < len(seen) <= 24_000
        assert "[salida recortada: se omitieron " in seen

    async def test_a_short_file_reaches_the_model_whole(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        seen = await read_through_the_loop(tmp_path, opened, "hola", limits=None)

        assert "hola" in seen
        assert "salida recortada" not in seen
