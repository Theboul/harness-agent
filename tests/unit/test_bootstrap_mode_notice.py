"""The model is told about the planning mode (HU-06-07 / FR-002, AC-02).

``/plan`` and ``/implementar`` leave a notice that rides in front of the next request of the person
(one ``USER`` message, so the history keeps its shape). It enters once per change of mode.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.bootstrap import (
    IMPLEMENTING_NOTICE,
    PLANNING_NOTICE,
    Composition,
    compose,
    run_session,
)
from harness_agent.core import ProviderResponse, Role
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import make_config


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


async def run(
    tmp_path: Path, opened: list[Composition], *lines: str, read_only: bool = False
) -> list[str]:
    """Run the lines; return the text of the last ``USER`` message of every model request."""
    folder = tmp_path / "trabajo"
    folder.mkdir(exist_ok=True)
    provider = FakeProvider([ProviderResponse(content="ok")] * 6)
    composition = compose(
        make_config(tmp_path, workspace=folder),
        provider_factory=lambda _config: provider,
        system_name="Linux",
        read_only=read_only,
    )
    opened.append(composition)
    stdin = io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir")))
    await run_session(composition, input_stream=stdin, output=io.StringIO())
    return [
        [m for m in messages if m.role is Role.USER][-1].content for messages in provider.received
    ]


def test_the_notices_are_one_clear_paragraph_each() -> None:
    assert "solo lectura" in PLANNING_NOTICE and "shell" in PLANNING_NOTICE
    assert "escribir" in IMPLEMENTING_NOTICE
    for text in (PLANNING_NOTICE, IMPLEMENTING_NOTICE):
        assert "\n" not in text and len(text) < 500


async def test_without_a_change_of_mode_the_request_is_untouched(
    tmp_path: Path, opened: list[Composition]
) -> None:
    assert await run(tmp_path, opened, "hola") == ["hola"]


async def test_after_plan_the_next_request_carries_the_notice_once(
    tmp_path: Path, opened: list[Composition]
) -> None:
    sent = await run(tmp_path, opened, "/plan", "primera", "segunda")

    assert sent[0].startswith(PLANNING_NOTICE) and sent[0].endswith("primera")
    assert sent[1] == "segunda"


async def test_planning_twice_does_not_repeat_the_notice(
    tmp_path: Path, opened: list[Composition]
) -> None:
    sent = await run(tmp_path, opened, "/plan", "uno", "/plan", "dos")

    assert sent[0].startswith(PLANNING_NOTICE)
    assert sent[1] == "dos"


async def test_implement_after_a_planning_request_sends_the_opposite_notice(
    tmp_path: Path, opened: list[Composition]
) -> None:
    sent = await run(tmp_path, opened, "/plan", "uno", "/implementar", "dos", "tres")

    assert sent[1].startswith(IMPLEMENTING_NOTICE) and sent[1].endswith("dos")
    assert sent[2] == "tres"


async def test_going_and_coming_back_before_a_request_sends_nothing(
    tmp_path: Path, opened: list[Composition]
) -> None:
    assert await run(tmp_path, opened, "/plan", "/implementar", "hola") == ["hola"]


async def test_a_new_session_while_planning_tells_the_model_again(
    tmp_path: Path, opened: list[Composition]
) -> None:
    sent = await run(tmp_path, opened, "/plan", "uno", "/nueva", "dos")

    assert sent[0].startswith(PLANNING_NOTICE)
    assert sent[1].startswith(PLANNING_NOTICE) and sent[1].endswith("dos")


async def test_a_read_only_mode_fixed_at_the_start_gets_no_notice_from_implement(
    tmp_path: Path, opened: list[Composition]
) -> None:
    sent = await run(tmp_path, opened, "/implementar", "hola", read_only=True)

    assert sent == ["hola"]
