"""Tests for ``delegar``, the delegation tool (HU-09-01 / T008)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from harness_agent.adapters.tools import DelegateTool
from harness_agent.core import (
    RESULT_SCHEMA,
    InMemoryToolRegistry,
    Message,
    RiskLevel,
    Role,
    SubagentResult,
    SubagentRunner,
)
from harness_agent.core.tools import validate_arguments

SENTINEL = "VALOR-DE-PRUEBA-123"
OUTPUT = {
    "resultado": "listo",
    "hallazgos_clave": ["uno"],
    "fuentes": ["a.py"],
    "error": None,
    "parcial": False,
}


class FakeRunner(SubagentRunner):
    """A runner double: records the call and returns (or raises) what it was given."""

    def __init__(self, outcome: SubagentResult | BaseException | object) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, str, list[Message], dict[str, Any]]] = []

    async def execute(
        self, profile: str, goal: str, context: list[Message], output_schema: dict[str, Any]
    ) -> SubagentResult:
        self.calls.append((profile, goal, context, output_schema))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome  # type: ignore[return-value]


def done(**changes: Any) -> SubagentResult:
    return SubagentResult("hija-1", {**OUTPUT, **changes}, bool(changes.get("error")))


def tool_with(outcome: SubagentResult | BaseException | object) -> tuple[DelegateTool, FakeRunner]:
    runner = FakeRunner(outcome)
    return DelegateTool(runner), runner


class TestDefinition:
    def test_name_and_risk(self) -> None:
        tool, _ = tool_with(done())

        assert tool.name == "delegar" and tool.risk is RiskLevel.LOW

    def test_the_description_says_the_subagent_starts_empty_and_returns_a_brief_result(
        self,
    ) -> None:
        text = tool_with(done())[0].description

        assert "contexto vacío" in text and "no la conversación" in text
        assert "no puede delegar" in text

    def test_the_registry_accepts_it(self) -> None:
        registry = InMemoryToolRegistry()

        registry.register(tool_with(done())[0])

        assert registry.validate_args("delegar", {"objetivo": "x"}) == {"objetivo": "x"}

    @pytest.mark.parametrize(
        "arguments",
        [
            {},
            {"objetivo": ""},
            {"objetivo": 3},
            {"objetivo": "x", "extra": "no"},
            {"objetivo": "x", "contexto_minimo": 3},
            {"objetivo": "x", "formato_salida": ["a"]},
            {"objetivo": "x" * 4001},
            {"objetivo": "x", "contexto_minimo": "c" * 8001},
            {"objetivo": "x", "formato_salida": "f" * 1001},
        ],
    )
    def test_the_arguments_are_checked_by_the_schema(self, arguments: dict[str, Any]) -> None:
        schema = tool_with(done())[0].schema

        assert validate_arguments(schema, arguments) != []

    def test_the_three_arguments_are_valid(self) -> None:
        schema = tool_with(done())[0].schema

        assert validate_arguments(schema, {"objetivo": "x", "contexto_minimo": "c"}) == []
        assert validate_arguments(schema, {"objetivo": "x", "formato_salida": "lista"}) == []


class TestRun:
    async def test_it_delegates_to_the_runner_with_the_general_profile_and_the_schema(self) -> None:
        tool, runner = tool_with(done())

        await tool.run({"objetivo": "Resume el módulo."})

        profile, goal, context, schema = runner.calls[0]
        assert (profile, goal, context) == ("general", "Resume el módulo.", [])
        assert schema == RESULT_SCHEMA

    async def test_the_schema_given_is_a_copy(self) -> None:
        tool, runner = tool_with(done())

        await tool.run({"objetivo": "x"})
        runner.calls[0][3]["properties"].clear()

        assert RESULT_SCHEMA["properties"]

    async def test_the_minimum_context_goes_as_one_message_of_the_person(self) -> None:
        tool, runner = tool_with(done())

        await tool.run({"objetivo": "x", "contexto_minimo": "  el dato  "})

        assert runner.calls[0][2] == [Message(Role.USER, "el dato")]

    async def test_a_blank_context_is_no_context(self) -> None:
        tool, runner = tool_with(done())

        await tool.run({"objetivo": "x", "contexto_minimo": "   "})

        assert runner.calls[0][2] == []

    async def test_the_output_format_is_added_to_the_goal(self) -> None:
        tool, runner = tool_with(done())

        await tool.run({"objetivo": "Resume.", "formato_salida": "tres viñetas"})

        assert runner.calls[0][1] == "Resume.\n\nFormato de salida solicitado: tres viñetas"

    async def test_the_result_is_the_json_of_the_output(self) -> None:
        tool, _ = tool_with(done())

        result = await tool.run({"objetivo": "x"})

        assert result.is_error is False and result.call_id == ""
        assert json.loads(result.content) == OUTPUT

    async def test_an_error_of_the_subagent_is_an_error_result_with_the_same_json(self) -> None:
        tool, _ = tool_with(done(error="no pude"))

        result = await tool.run({"objetivo": "x"})

        assert result.is_error is True
        assert json.loads(result.content)["error"] == "no pude"

    @pytest.mark.parametrize("objective", [None, "", "   ", 3])
    async def test_a_goal_that_is_not_usable_is_a_tagged_error_and_nothing_runs(
        self, objective: object
    ) -> None:
        tool, runner = tool_with(done())

        result = await tool.run({"objetivo": objective})

        assert result.is_error is True and result.content.startswith("[objetivo_invalido]")
        assert runner.calls == []

    async def test_an_exception_of_the_runner_is_a_fixed_error_without_its_text(self) -> None:
        tool, _ = tool_with(RuntimeError(SENTINEL))

        result = await tool.run({"objetivo": "x"})

        assert result.is_error is True and result.content.startswith("[subagente_fallo]")
        assert SENTINEL not in result.content

    async def test_something_that_is_not_a_result_is_a_fixed_error(self) -> None:
        tool, _ = tool_with(SENTINEL)

        result = await tool.run({"objetivo": "x"})

        assert result.is_error is True and result.content.startswith("[subagente_fallo]")
        assert SENTINEL not in result.content

    async def test_an_output_that_is_not_json_is_a_fixed_error(self) -> None:
        tool, _ = tool_with(SubagentResult("hija-1", {"resultado": {1, 2}}, False))

        result = await tool.run({"objetivo": "x"})

        assert result.is_error is True and result.content.startswith("[subagente_fallo]")

    async def test_a_cancellation_goes_up(self) -> None:
        tool, _ = tool_with(asyncio.CancelledError())

        with pytest.raises(asyncio.CancelledError):
            await tool.run({"objetivo": "x"})
