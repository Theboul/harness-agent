"""Tests for ``preguntar_usuario`` (HU-06-02 / FR-001 to FR-004)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from harness_agent.adapters.tools import Answer, AskUserTool, Question
from harness_agent.core import InMemoryToolRegistry, RiskLevel
from harness_agent.core.tools import validate_arguments

OPTIONS = ["informe.md", "resultados/", "otra ruta"]
SENTINEL = "VALOR-DE-PRUEBA-123"


class Asker:
    """An ``ask`` double: records the question and returns what it was given."""

    def __init__(self, reply: Any) -> None:
        self.reply = reply
        self.questions: list[Question] = []

    async def __call__(self, question: Question) -> Any:
        self.questions.append(question)
        if isinstance(self.reply, BaseException):
            raise self.reply
        return self.reply


def args(**extra: Any) -> dict[str, Any]:
    return {"pregunta": "¿Dónde guardo el resultado?", "opciones": list(OPTIONS), **extra}


class TestDefinition:
    def test_name_risk_and_description(self) -> None:
        tool = AskUserTool(Asker(None))

        assert tool.name == "preguntar_usuario"
        assert tool.risk is RiskLevel.LOW
        assert tool.description.strip()

    def test_the_registry_accepts_the_schema(self) -> None:
        InMemoryToolRegistry().register(AskUserTool(Asker(None)))

    @pytest.mark.parametrize(
        "arguments",
        [
            {"pregunta": "", "opciones": OPTIONS},
            {"pregunta": "x", "opciones": ["solo una"]},
            {"pregunta": "x", "opciones": [f"o{n}" for n in range(9)]},
            {"pregunta": "x", "opciones": ["a", ""]},
            {"pregunta": "x", "opciones": ["a", "b"], "extra": 1},
            {"pregunta": "x"},
        ],
    )
    def test_the_schema_rejects_bad_arguments(self, arguments: dict[str, Any]) -> None:
        tool = AskUserTool(Asker(None))

        assert validate_arguments(tool.schema, arguments)

    def test_the_schema_accepts_the_example_of_the_card(self) -> None:
        tool = AskUserTool(Asker(None))

        assert not validate_arguments(tool.schema, args())


class TestChoice:
    async def test_choosing_an_option_returns_its_number_and_text(self) -> None:
        asker = Asker(Answer(number=2, text=""))
        result = await AskUserTool(asker).run(args())

        assert not result.is_error
        assert "2" in result.content and "resultados/" in result.content
        assert asker.questions == [
            Question("¿Dónde guardo el resultado?", tuple(OPTIONS), allow_free_text=True)
        ]

    @pytest.mark.parametrize("number", [0, 4, -1, True])
    async def test_a_number_out_of_range_is_no_answer(self, number: int) -> None:
        result = await AskUserTool(Asker(Answer(number, ""))).run(args())

        assert result.is_error and result.content.startswith("[sin_respuesta]")


class TestFreeText:
    async def test_free_text_is_accepted_by_default(self) -> None:
        result = await AskUserTool(Asker(Answer(None, "en docs/salida.txt"))).run(args())

        assert not result.is_error
        assert "docs/salida.txt" in result.content

    async def test_free_text_is_cleaned_like_a_reason(self) -> None:
        raw = f'primera\nsegunda "{SENTINEL}" https://user:pw@host/x \x1b[31m' + "z" * 400
        result = await AskUserTool(Asker(Answer(None, raw))).run(args())

        assert "\n" not in result.content and "\x1b" not in result.content
        assert '"' not in result.content and "pw@" not in result.content
        assert len(result.content) < 400

    async def test_free_text_not_allowed_is_no_answer(self) -> None:
        asker = Asker(Answer(None, "otra cosa"))
        result = await AskUserTool(asker).run(args(permitir_texto_libre=False))

        assert result.is_error and result.content.startswith("[sin_respuesta]")
        assert asker.questions[0].allow_free_text is False

    async def test_an_empty_free_text_is_no_answer(self) -> None:
        result = await AskUserTool(Asker(Answer(None, "  \x07 "))).run(args())

        assert result.is_error and result.content.startswith("[sin_respuesta]")


class TestFailClosed:
    async def test_no_answer_is_an_error_and_never_a_default(self) -> None:
        result = await AskUserTool(Asker(None)).run(args())

        assert result.is_error and result.content.startswith("[sin_respuesta]")
        assert "informe.md" not in result.content

    async def test_an_exception_of_ask_is_no_answer_without_its_text(self) -> None:
        result = await AskUserTool(Asker(RuntimeError(SENTINEL))).run(args())

        assert result.is_error and result.content.startswith("[sin_respuesta]")
        assert SENTINEL not in result.content

    async def test_cancellation_is_not_swallowed(self) -> None:
        with pytest.raises(asyncio.CancelledError):
            await AskUserTool(Asker(asyncio.CancelledError())).run(args())

    async def test_an_answer_that_is_not_an_answer_is_no_answer(self) -> None:
        result = await AskUserTool(Asker("2")).run(args())

        assert result.is_error and result.content.startswith("[sin_respuesta]")

    @pytest.mark.parametrize("options", [["a", "a"], ["a", "  "], ["a", "A "], ["a", "\x07"]])
    async def test_options_that_repeat_or_are_empty_are_invalid_and_not_asked(
        self, options: list[str]
    ) -> None:
        asker = Asker(Answer(1, ""))
        result = await AskUserTool(asker).run({"pregunta": "x", "opciones": options})

        assert result.is_error and result.content.startswith("[opciones_invalidas]")
        assert asker.questions == []

    async def test_a_question_empty_after_cleaning_is_invalid(self) -> None:
        asker = Asker(Answer(1, ""))
        result = await AskUserTool(asker).run({"pregunta": "\x07", "opciones": ["a", "b"]})

        assert result.is_error and result.content.startswith("[pregunta_invalida]")
        assert asker.questions == []

    async def test_options_that_are_not_a_list_are_invalid(self) -> None:
        result = await AskUserTool(Asker(Answer(1, ""))).run({"pregunta": "x", "opciones": "ab"})

        assert result.is_error and result.content.startswith("[opciones_invalidas]")

    async def test_a_question_that_is_not_text_is_invalid(self) -> None:
        asker = Asker(Answer(1, ""))
        result = await AskUserTool(asker).run({"pregunta": 5, "opciones": ["a", "b"]})

        assert result.is_error and result.content.startswith("[pregunta_invalida]")
        assert asker.questions == []
