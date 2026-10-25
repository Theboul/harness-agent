"""Tests for the output limit applied by InMemoryToolRegistry (HU-02-02 / T004)."""

from __future__ import annotations

import asyncio

import pytest

from harness_agent.core.entities import ToolResult
from harness_agent.core.interfaces.tool import RiskLevel
from harness_agent.core.tools import DEFAULT_MAX_OUTPUT_CHARS, InMemoryToolRegistry
from harness_agent.core.tools.errors import (
    DuplicateToolError,
    InvalidToolDefinitionError,
    UnknownToolError,
)
from tests.doubles.dummy_tool import DummyTool

SENTINEL = "VALOR-DE-PRUEBA-123"
BIG = "INICIO" + "x" * 5_000 + "FINAL"


def big_tool(name: str = "grande") -> DummyTool:
    return DummyTool(
        name=name,
        description="Devuelve mucho",
        risk=RiskLevel.MEDIUM,
        canned_result=ToolResult(call_id="c1", content=BIG),
    )


def run(registry: InMemoryToolRegistry, name: str) -> ToolResult:
    tool = registry.get(name)
    assert tool is not None
    return asyncio.run(tool.run({}))


# --------------------------------------------------------------- without a maximum


def test_without_a_maximum_the_registered_instance_is_served() -> None:
    registry = InMemoryToolRegistry()
    tool = big_tool()
    registry.register(tool)
    assert registry.get("grande") is tool
    assert registry.list() == [tool]
    assert run(registry, "grande").content == BIG


# ------------------------------------------------------------------ with a maximum


def test_with_a_maximum_the_served_tool_cuts_its_result() -> None:
    registry = InMemoryToolRegistry(max_output_chars=600)
    registry.register(big_tool())
    result = run(registry, "grande")
    assert len(result.content) <= 600
    assert result.content.startswith("INICIO")
    assert result.content.endswith("FINAL")
    assert "[salida recortada: se omitieron " in result.content
    assert result.call_id == "c1"


def test_the_served_tool_has_the_same_definition() -> None:
    registry = InMemoryToolRegistry(max_output_chars=600)
    tool = big_tool()
    registry.register(tool)
    served = registry.get("grande")
    assert served is not None
    assert (served.name, served.description, served.risk) == (
        "grande",
        "Devuelve mucho",
        RiskLevel.MEDIUM,
    )
    assert served.schema == tool.schema


def test_list_keeps_the_registration_order_and_serves_bounded_tools() -> None:
    registry = InMemoryToolRegistry(max_output_chars=600)
    for name in ("b", "a", "c"):
        registry.register(big_tool(name))
    listed = registry.list()
    assert [tool.name for tool in listed] == ["b", "a", "c"]
    assert asyncio.run(listed[0].run({})).content.endswith("FINAL")
    assert len(asyncio.run(listed[0].run({})).content) <= 600
    assert listed is not registry.list()


def test_a_result_that_fits_goes_through_unchanged() -> None:
    registry = InMemoryToolRegistry(max_output_chars=DEFAULT_MAX_OUTPUT_CHARS)
    result = ToolResult(call_id="c2", content="corto")
    registry.register(DummyTool(name="corta", canned_result=result))
    assert run(registry, "corta") is result


def test_two_registries_apply_their_own_maximum() -> None:
    small = InMemoryToolRegistry(max_output_chars=300)
    large = InMemoryToolRegistry(max_output_chars=10_000)
    for registry in (small, large):
        registry.register(big_tool())
    assert len(run(small, "grande").content) <= 300
    assert run(large, "grande").content == BIG


def test_an_error_result_is_still_an_error_after_the_cut() -> None:
    registry = InMemoryToolRegistry(max_output_chars=300)
    registry.register(
        DummyTool(
            name="falla",
            canned_result=ToolResult(call_id="c3", content="[error] " + "z" * 2_000, is_error=True),
        )
    )
    result = run(registry, "falla")
    assert result.is_error is True
    assert result.content.startswith("[error] ")
    assert len(result.content) <= 300


# --------------------------------------------------------- the rest of the registry


def test_failed_registrations_leave_no_trace_with_a_maximum() -> None:
    registry = InMemoryToolRegistry(max_output_chars=600)
    registry.register(big_tool())
    with pytest.raises(DuplicateToolError):
        registry.register(big_tool())
    with pytest.raises(InvalidToolDefinitionError):
        registry.register(DummyTool(name="mal nombre"))
    assert [tool.name for tool in registry.list()] == ["grande"]
    assert registry.get("mal nombre") is None


def test_validate_args_and_unknown_tools_do_not_change() -> None:
    registry = InMemoryToolRegistry(max_output_chars=600)
    registry.register(big_tool())
    assert registry.validate_args("grande", {"input": "x"}) == {"input": "x"}
    with pytest.raises(UnknownToolError):
        registry.validate_args("nada", {})
    assert registry.get("nada") is None
    assert registry.get(5) is None  # type: ignore[arg-type]


# ------------------------------------------------------------- the maximum is checked


@pytest.mark.parametrize("value", [True, 0, -1, 255, 12.5, "1000", SENTINEL])
def test_an_invalid_maximum_is_rejected_without_echoing_it(value: object) -> None:
    with pytest.raises(ValueError) as caught:
        InMemoryToolRegistry(max_output_chars=value)  # type: ignore[arg-type]
    assert SENTINEL not in str(caught.value)


def test_the_minimum_maximum_is_accepted() -> None:
    registry = InMemoryToolRegistry(max_output_chars=256)
    registry.register(big_tool())
    assert len(run(registry, "grande").content) <= 256
