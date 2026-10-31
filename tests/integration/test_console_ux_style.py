"""Color end to end (HU-06-05 / T013, AC-09): painted only on a terminal, same text without it.

A whole session (activity lines, approval block, command output) runs on a stream that pretends to
be a terminal and on one that is not. Removing the codes from the first must give the second.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from harness_agent import bootstrap
from harness_agent.bootstrap import Composition, run_session
from harness_agent.cli import ConsoleApprover
from harness_agent.cli.style import ESCAPE
from harness_agent.config import HarnessConfig
from harness_agent.core import ProviderResponse, ToolCall
from tests.doubles import FakeProvider
from tests.integration.test_essential_context_agent_loop import NoShell
from tests.unit.bootstrap_support import build, make_config

CODES = re.compile(re.escape(ESCAPE) + r"\[[0-9;]*m")
DURATION = re.compile(r" \(\d+ ms\)")
COMMAND = "pytest -q tests/"


class FakeTerminal(io.StringIO):
    """A stream that says it is a terminal."""

    def isatty(self) -> bool:
        return True


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


@pytest.fixture(autouse=True)
def a_known_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """A terminal that understands ANSI, on any platform; each test changes what it needs."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("WT_SESSION", "prueba")
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: NoShell())


def config_for(tmp_path: Path) -> HarnessConfig:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(parents=True)
    return replace(make_config(tmp_path, workspace=workspace), model="openai/modelo-de-prueba")


async def session(tmp_path: Path, opened: list[Composition], output: io.StringIO) -> str:
    """One request that needs approval (and is rejected), then two commands; returns the output."""
    provider = FakeProvider(
        [
            ProviderResponse(tool_calls=[ToolCall("c1", "shell", {"command": COMMAND})]),
            ProviderResponse(content="listo"),
        ]
    )
    approver = ConsoleApprover(io.StringIO("3\n\n"), output)
    composition = build(
        opened, config_for(tmp_path), provider, approver=approver, system_name="Linux"
    )
    await run_session(
        composition,
        input_stream=io.StringIO("corre las pruebas\n/model\n/sesiones\n/salir\n"),
        output=output,
    )
    return output.getvalue()


def plain_of(text: str) -> str:
    return DURATION.sub("", CODES.sub("", text))


class TestColorOnATerminal:
    async def test_a_terminal_gets_color_and_the_text_is_the_same_without_it(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        painted = await session(tmp_path / "a", opened, FakeTerminal())
        plain = await session(tmp_path / "b", opened, io.StringIO())

        assert ESCAPE in painted
        assert ESCAPE not in plain
        # the rows of /sesiones carry identifiers and times that differ between the two runs
        assert [line for line in plain_of(painted).splitlines() if "UTC" not in line] == [
            line for line in plain_of(plain).splitlines() if "UTC" not in line
        ]

    async def test_the_approval_block_and_the_activity_lines_are_painted(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        painted = await session(tmp_path, opened, FakeTerminal())

        assert f"{ESCAPE}[1m" in painted  # the title (bold)
        assert f"{ESCAPE}[31;1m" in painted or f"{ESCAPE}[31m" in painted  # high risk, a failure
        assert COMMAND in CODES.sub("", painted)

    async def test_no_color_turns_it_off(
        self, tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NO_COLOR", "1")

        shown = await session(tmp_path, opened, FakeTerminal())

        assert ESCAPE not in shown

    async def test_a_dumb_terminal_gets_no_color(
        self, tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERM", "dumb")

        shown = await session(tmp_path, opened, FakeTerminal())

        assert ESCAPE not in shown

    async def test_a_stream_that_is_not_a_terminal_gets_no_color(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        shown = await session(tmp_path, opened, io.StringIO())

        assert ESCAPE not in shown
