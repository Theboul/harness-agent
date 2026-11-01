"""Tests for the question view and the console questioner (HU-06-02 / FR-005)."""

from __future__ import annotations

import io
from dataclasses import dataclass

import pytest

from harness_agent.cli import ConsoleQuestioner, Reply, question_block
from harness_agent.cli.style import PLAIN

SENTINEL = "VALOR-DE-PRUEBA-123"


@dataclass(frozen=True)
class Request:
    text: str = "¿Dónde guardo el resultado?"
    options: tuple[str, ...] = ("informe.md", "resultados/", "otra ruta")
    allow_free_text: bool = True


async def ask(
    typed: str,
    request: Request = Request(),
    **options: int,  # noqa: B008 (immutable)
) -> tuple[Reply | None, str]:
    out = io.StringIO()
    questioner = ConsoleQuestioner(io.StringIO(typed), out, style=PLAIN, **options)
    return await questioner(request), out.getvalue()


class TestView:
    def test_numbered_options_and_the_question(self) -> None:
        text = "\n".join(question_block(Request().text, Request().options, True, PLAIN))

        assert "¿Dónde guardo el resultado?" in text
        for number, option in enumerate(Request().options, start=1):
            assert f"[{number}] {option}" in text
        assert "escribe" in text.lower()

    def test_without_free_text_the_help_asks_for_a_number_only(self) -> None:
        text = "\n".join(question_block("x", ("a", "b"), False, PLAIN))

        assert "escribe tu respuesta" not in text.lower()
        assert "número" in text.lower()

    def test_data_of_the_model_is_cleaned_and_bounded(self) -> None:
        lines = question_block("hola\x1b[31m\nmundo" + "q" * 900, ("a\nb\x07", "c"), True, PLAIN)

        assert all("\x1b" not in line and "\x07" not in line for line in lines)
        assert not any("mundo" in line and "\n" in line for line in lines)
        assert max(len(line) for line in lines) < 700


class TestChoosing:
    async def test_a_number_is_a_choice(self) -> None:
        reply, shown = await ask("2\n")

        assert reply == Reply(number=2, text="")
        assert "[2] resultados/" in shown

    async def test_free_text_is_accepted_when_allowed(self) -> None:
        reply, _ = await ask("en docs/\n")

        assert reply == Reply(number=None, text="en docs/")

    async def test_a_number_out_of_range_is_asked_again(self) -> None:
        reply, shown = await ask("0\n4\n3\n")

        assert reply == Reply(number=3, text="")
        assert shown.count("no válida") == 2

    async def test_without_free_text_the_text_is_invalid(self) -> None:
        request = Request(allow_free_text=False)
        reply, shown = await ask("otra cosa\n1\n", request)

        assert reply == Reply(number=1, text="")
        assert "otra cosa" not in shown

    async def test_the_invalid_text_is_never_echoed(self) -> None:
        _, shown = await ask(f"{SENTINEL}\n", Request(allow_free_text=False), max_attempts=1)

        assert SENTINEL not in shown


class TestFailClosed:
    async def test_end_of_input_is_no_answer(self) -> None:
        reply, _ = await ask("")

        assert reply is None

    async def test_exit_command_is_no_answer(self) -> None:
        reply, _ = await ask("/salir\n1\n")

        assert reply is None

    async def test_invalid_attempts_are_no_answer(self) -> None:
        reply, _ = await ask("9\n9\n9\n1\n", max_attempts=3)

        assert reply is None

    async def test_an_empty_line_is_asked_again_and_counts(self) -> None:
        reply, _ = await ask("\n\n\n1\n", max_attempts=3)

        assert reply is None

    async def test_free_text_is_cut_to_a_bounded_read(self) -> None:
        reply, _ = await ask("z" * 5000 + "\n")

        assert reply is not None and reply.text is not None and len(reply.text) <= 1000


def test_attempts_must_be_positive() -> None:
    with pytest.raises(ValueError):
        ConsoleQuestioner(io.StringIO(""), io.StringIO(), max_attempts=0)
