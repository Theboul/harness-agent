"""The offer to leave the planning mode (HU-06-07 / T005, FR-004, AC-04).

When a turn ends in the planning mode the harness (never the model) asks whether to implement.
Only a clear ``1`` changes the mode; anything else, or a failure of the question, keeps the
read-only mode. A mode fixed at the start is never offered.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.tools import Answer, Question
from harness_agent.bootstrap import IMPLEMENTING_NOTICE, Composition, compose, run_session
from harness_agent.cli import OFFER_OPTIONS, OFFER_QUESTION
from harness_agent.core import ProviderResponse, Role
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import make_config


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class Asker:
    """An ``AskFn`` double: records the questions and replays the scripted answers."""

    def __init__(self, *answers: Answer | None | BaseException) -> None:
        self.questions: list[Question] = []
        self._answers = list(answers)

    async def __call__(self, question: Question) -> Answer | None:
        self.questions.append(question)
        outcome = self._answers.pop(0) if self._answers else None
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class Run:
    def __init__(self, composition: Composition, provider: FakeProvider, shown: str) -> None:
        self.composition = composition
        self.provider = provider
        self.shown = shown

    def last_user_texts(self) -> list[str]:
        return [
            [m for m in messages if m.role is Role.USER][-1].content
            for messages in self.provider.received
        ]


async def run(
    tmp_path: Path,
    opened: list[Composition],
    asker: Asker | None,
    *lines: str,
    read_only: bool = False,
) -> Run:
    folder = tmp_path / "trabajo"
    folder.mkdir(exist_ok=True)
    provider = FakeProvider([ProviderResponse(content="ok")] * 6)
    composition = compose(
        make_config(tmp_path, workspace=folder),
        provider_factory=lambda _config: provider,
        system_name="Linux",
        read_only=read_only,
        ask=asker,
    )
    opened.append(composition)
    output = io.StringIO()
    stdin = io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir")))
    await run_session(composition, input_stream=stdin, output=output)
    return Run(composition, provider, output.getvalue())


def planning(composition: Composition) -> bool:
    return composition.work_mode.planning


async def test_the_question_has_the_two_options_and_no_free_text(
    tmp_path: Path, opened: list[Composition]
) -> None:
    asker = Asker(None)

    await run(tmp_path, opened, asker, "/plan", "explora")

    (question,) = asker.questions
    assert question.text == OFFER_QUESTION
    assert question.options == OFFER_OPTIONS and len(OFFER_OPTIONS) == 2
    assert question.allow_free_text is False


async def test_answering_one_applies_implement_and_the_next_request_is_told(
    tmp_path: Path, opened: list[Composition]
) -> None:
    result = await run(tmp_path, opened, Asker(Answer(number=1)), "/plan", "explora", "haz")

    assert not planning(result.composition)
    read_switch = result.composition.read_only_switch
    assert read_switch is not None and not read_switch.enabled
    assert "Modo implementación" in result.shown
    assert result.last_user_texts()[1].startswith(IMPLEMENTING_NOTICE)


@pytest.mark.parametrize(
    "outcome",
    [Answer(number=2), Answer(number=None, text="1"), Answer(number=3), None, OSError("x")],
)
async def test_any_other_outcome_keeps_the_read_only_mode(
    tmp_path: Path, opened: list[Composition], outcome: Answer | None | BaseException
) -> None:
    result = await run(tmp_path, opened, Asker(outcome), "/plan", "explora")

    assert planning(result.composition)
    read_switch = result.composition.read_only_switch
    assert read_switch is not None and read_switch.enabled
    assert "Modo implementación" not in result.shown


async def test_each_turn_in_planning_asks_again(tmp_path: Path, opened: list[Composition]) -> None:
    asker = Asker(Answer(number=2), Answer(number=2))

    await run(tmp_path, opened, asker, "/plan", "uno", "dos")

    assert len(asker.questions) == 2


async def test_nothing_is_asked_outside_the_planning_mode(
    tmp_path: Path, opened: list[Composition]
) -> None:
    asker = Asker()

    await run(tmp_path, opened, asker, "hola")

    assert asker.questions == []


async def test_a_read_only_mode_fixed_at_the_start_is_never_offered(
    tmp_path: Path, opened: list[Composition]
) -> None:
    asker = Asker(Answer(number=1))

    result = await run(tmp_path, opened, asker, "/plan", "explora", read_only=True)

    assert asker.questions == []
    read_switch = result.composition.read_only_switch
    assert read_switch is not None and read_switch.enabled


async def test_without_a_question_function_there_is_no_offer(
    tmp_path: Path, opened: list[Composition]
) -> None:
    result = await run(tmp_path, opened, None, "/plan", "explora")

    assert planning(result.composition)


async def test_a_cancellation_of_the_question_is_not_swallowed(
    tmp_path: Path, opened: list[Composition]
) -> None:
    import asyncio

    with pytest.raises(asyncio.CancelledError):
        await run(tmp_path, opened, Asker(asyncio.CancelledError()), "/plan", "explora")
