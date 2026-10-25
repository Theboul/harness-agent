"""Tests for the output limit of tool results: ``truncate_output``, ``check_max_output_chars``
and ``TruncatingTool`` (HU-02-02 / T002, T003)."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import pytest

from harness_agent.adapters.system.shell_output import OutputCollector
from harness_agent.core.entities import ToolResult
from harness_agent.core.interfaces.tool import RiskLevel, Tool
from harness_agent.core.tools.output_limit import (
    DEFAULT_MAX_OUTPUT_CHARS,
    MIN_MAX_OUTPUT_CHARS,
    TruncatingTool,
    check_max_output_chars,
    omission_notice,
    truncate_output,
)
from tests.doubles.dummy_tool import DummyTool

SENTINEL = "VALOR-DE-PRUEBA-123"
NOTICE_PATTERN = re.compile(r"\[salida recortada: se omitieron (\d+) caracteres\]")


def omitted_in(text: str) -> int:
    """The number the notice of ``text`` announces; the notice must appear exactly once."""
    found = NOTICE_PATTERN.findall(text)
    assert len(found) == 1
    return int(found[0])


def split_around_notice(text: str, max_chars: int, original: str) -> tuple[str, str]:
    """Head and tail around the notice, checked against ``original``."""
    omitted = omitted_in(text)
    head, tail = text.split(omission_notice(omitted))
    assert original.startswith(head)
    assert original.endswith(tail)
    assert len(original) - len(head) - len(tail) == omitted
    assert len(text) <= max_chars
    return head, tail


# ------------------------------------------------------------------------ constants


def test_default_and_minimum_values() -> None:
    assert DEFAULT_MAX_OUTPUT_CHARS == 24_000
    assert MIN_MAX_OUTPUT_CHARS == 256


def test_default_leaves_room_over_the_bound_of_the_tools() -> None:
    # The tools bound their body to 20 000 characters and the shell adds a short header.
    assert DEFAULT_MAX_OUTPUT_CHARS >= 20_000 + 500


# ------------------------------------------------------------------------ the notice


def test_notice_text() -> None:
    assert omission_notice(7) == "\n[salida recortada: se omitieron 7 caracteres]\n"


def test_notice_is_the_one_of_the_shell() -> None:
    collector = OutputCollector(max_chars=1_000)
    collector.feed(b"x" * 5_000)
    text = collector.finish()
    assert omission_notice(omitted_in(text)) in text


# -------------------------------------------------------------------- truncate_output


def test_text_within_the_maximum_is_the_same_object() -> None:
    text = "a" * 300
    assert truncate_output(text, 300) is text
    assert truncate_output(text, 1_000) is text


def test_empty_text_stays_empty() -> None:
    assert truncate_output("", MIN_MAX_OUTPUT_CHARS) == ""


def test_one_character_over_the_maximum_is_cut_with_a_notice() -> None:
    original = "".join(chr(ord("a") + i % 26) for i in range(301))
    result = truncate_output(original, 300)
    assert result != original
    split_around_notice(result, 300, original)


def test_huge_text_keeps_head_and_tail() -> None:
    original = "INICIO" + "m" * 1_000_000 + "FINAL"
    result = truncate_output(original, 1_000)
    head, tail = split_around_notice(result, 1_000, original)
    assert head.startswith("INICIO")
    assert tail.endswith("FINAL")
    assert len(head) > 100
    assert len(tail) > 100
    assert abs(len(head) - len(tail)) <= 1


def test_the_result_never_exceeds_the_maximum_for_any_length() -> None:
    for maximum in (MIN_MAX_OUTPUT_CHARS, 257, 1_000, DEFAULT_MAX_OUTPUT_CHARS):
        for length in (maximum + 1, maximum + 2, maximum * 3, 10**6):
            original = "z" * length
            result = truncate_output(original, maximum)
            split_around_notice(result, maximum, original)


def test_the_omitted_count_is_exact_when_the_digits_change() -> None:
    # The count is 3 digits here while the reserve is computed with the digits of the length.
    original = "".join(str(i % 10) for i in range(MIN_MAX_OUTPUT_CHARS + 120))
    result = truncate_output(original, MIN_MAX_OUTPUT_CHARS)
    split_around_notice(result, MIN_MAX_OUTPUT_CHARS, original)


def test_non_ascii_text_is_cut_by_characters() -> None:
    original = "ñandú ✓ 😀 " * 400
    result = truncate_output(original, 500)
    split_around_notice(result, 500, original)
    assert "�" not in result
    result.encode("utf-8")


def test_exactly_the_maximum_has_no_notice() -> None:
    text = "q" * 500
    assert "salida recortada" not in truncate_output(text, 500)


@pytest.mark.parametrize("maximum", [MIN_MAX_OUTPUT_CHARS - 1, 0, -5])
def test_a_maximum_below_the_minimum_is_rejected_even_for_short_text(maximum: int) -> None:
    with pytest.raises(ValueError):
        truncate_output("corto", maximum)


# ---------------------------------------------------------- check_max_output_chars


@pytest.mark.parametrize("value", [MIN_MAX_OUTPUT_CHARS, 1_000, DEFAULT_MAX_OUTPUT_CHARS])
def test_valid_maximums_are_returned(value: int) -> None:
    assert check_max_output_chars(value) == value


@pytest.mark.parametrize(
    "value",
    [True, False, 0, -1, MIN_MAX_OUTPUT_CHARS - 1, 300.5, "1000", None, [300], SENTINEL],
)
def test_invalid_maximums_are_rejected_without_echoing_the_value(value: object) -> None:
    with pytest.raises(ValueError) as caught:
        check_max_output_chars(value)
    message = str(caught.value)
    assert SENTINEL not in message
    assert str(MIN_MAX_OUTPUT_CHARS) in message
    assert message.endswith(".")


# ----------------------------------------------------------------- TruncatingTool


class CountingTool(DummyTool):
    """DummyTool that counts attribute reads and keeps the arguments it received."""

    def __init__(self, result: ToolResult | None = None) -> None:
        super().__init__(
            name="contador",
            description="Cuenta lecturas",
            risk=RiskLevel.HIGH,
            canned_result=result,
            schema={"type": "object", "properties": {"x": {"type": "integer"}}},
        )
        self.reads = 0

    @property
    def name(self) -> str:
        self.reads += 1
        return "contador"


class RaisingTool(DummyTool):
    def __init__(self, error: BaseException) -> None:
        super().__init__(name="falla")
        self._error = error

    async def run(self, args: dict[str, Any]) -> ToolResult:
        raise self._error


class OddResultTool(DummyTool):
    def __init__(self, value: object) -> None:
        super().__init__(name="raro")
        self._value = value

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return self._value  # type: ignore[return-value]


def test_it_is_a_tool_that_delegates_its_attributes() -> None:
    inner = CountingTool()
    wrapped = TruncatingTool(inner, 1_000)
    assert isinstance(wrapped, Tool)
    assert wrapped.description == "Cuenta lecturas"
    assert wrapped.risk is RiskLevel.HIGH
    assert wrapped.schema == inner.schema
    before = inner.reads
    assert wrapped.name == "contador"
    assert wrapped.name == "contador"
    assert inner.reads == before + 2  # read from the inner tool each time


def test_the_maximum_is_validated_on_construction() -> None:
    with pytest.raises(ValueError):
        TruncatingTool(DummyTool(), 10)
    with pytest.raises(ValueError):
        TruncatingTool(DummyTool(), True)


def test_a_short_result_is_the_same_object() -> None:
    result = ToolResult(call_id="c1", content="corto")
    wrapped = TruncatingTool(DummyTool(canned_result=result), 500)
    assert asyncio.run(wrapped.run({})) is result


def test_a_result_of_exactly_the_maximum_is_the_same_object() -> None:
    result = ToolResult(call_id="c1", content="x" * 500)
    wrapped = TruncatingTool(DummyTool(canned_result=result), 500)
    assert asyncio.run(wrapped.run({})) is result


def test_a_long_result_is_cut_and_keeps_call_id_and_error_flag() -> None:
    original = "[codigo_de_salida=1] Falló.\n" + "e" * 5_000 + "\nFIN"
    result = ToolResult(call_id="c9", content=original, is_error=True)
    cut = asyncio.run(TruncatingTool(DummyTool(canned_result=result), 600).run({}))
    assert cut is not result
    assert cut.call_id == "c9"
    assert cut.is_error is True
    assert cut.content.startswith("[codigo_de_salida=1] Falló.")
    assert cut.content.endswith("FIN")
    split_around_notice(cut.content, 600, original)
    assert result.content == original  # the original result is not changed


def test_a_long_result_that_is_not_an_error_stays_not_an_error() -> None:
    result = ToolResult(call_id="c2", content="y" * 5_000)
    cut = asyncio.run(TruncatingTool(DummyTool(canned_result=result), 600).run({}))
    assert cut.is_error is False


def test_arguments_reach_the_tool_unchanged() -> None:
    inner = DummyTool()
    args = {"input": "hola", "call_id": "c3"}
    result = asyncio.run(TruncatingTool(inner, 500).run(args))
    assert inner.recorded_executions[0] is args
    assert args == {"input": "hola", "call_id": "c3"}
    assert result.call_id == "c3"


@pytest.mark.parametrize("odd", [None, "texto", 42, {"content": "x"}])
def test_a_result_that_is_not_a_tool_result_is_handed_back_as_it_is(odd: object) -> None:
    assert asyncio.run(TruncatingTool(OddResultTool(odd), 500).run({})) is odd


def test_a_result_with_content_that_is_not_text_is_handed_back_as_it_is() -> None:
    result = ToolResult(call_id="c4", content=b"x" * 5_000)  # type: ignore[arg-type]
    assert asyncio.run(TruncatingTool(OddResultTool(result), 500).run({})) is result


def test_an_exception_of_the_tool_propagates() -> None:
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(TruncatingTool(RaisingTool(RuntimeError("boom")), 500).run({}))


def test_cancellation_propagates() -> None:
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(TruncatingTool(RaisingTool(asyncio.CancelledError()), 500).run({}))
