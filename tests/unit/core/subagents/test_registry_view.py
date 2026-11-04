"""The registry a subagent sees: the orchestrator's without the delegation (HU-09-04 / T003).

One level of nesting only: the view hides ``delegar`` so the subagent neither sees it nor can call
it, and everything else (also what is registered later) goes through.
"""

from __future__ import annotations

import pytest

from harness_agent.core import InMemoryToolRegistry, ToolRegistry
from harness_agent.core.subagents.registry import DELEGATE_TOOL_NAME, RegistryView
from harness_agent.core.tools.errors import UnknownToolError
from tests.doubles import DummyTool


def make() -> tuple[InMemoryToolRegistry, RegistryView]:
    registry = InMemoryToolRegistry()
    for name in ("leer", DELEGATE_TOOL_NAME, "escribir"):
        registry.register(DummyTool(name=name))
    return registry, RegistryView(registry, {DELEGATE_TOOL_NAME})


def test_the_name_of_the_delegation_is_the_one_the_user_reads() -> None:
    assert DELEGATE_TOOL_NAME == "delegar"


def test_the_view_is_a_registry() -> None:
    assert isinstance(make()[1], ToolRegistry)


def test_the_listing_leaves_out_the_hidden_names_and_keeps_the_order() -> None:
    _, view = make()

    assert [tool.name for tool in view.list()] == ["leer", "escribir"]


def test_a_hidden_tool_is_not_found() -> None:
    _, view = make()

    assert view.get(DELEGATE_TOOL_NAME) is None
    assert view.get("leer") is not None and view.get("inexistente") is None


def test_arguments_of_a_hidden_tool_are_an_unknown_tool() -> None:
    _, view = make()

    with pytest.raises(UnknownToolError):
        view.validate_args(DELEGATE_TOOL_NAME, {})


def test_arguments_of_the_others_go_to_the_registry() -> None:
    _, view = make()

    assert view.validate_args("leer", {"input": "x"}) == {"input": "x"}


def test_what_the_orchestrator_registers_later_appears_in_the_view() -> None:
    registry, view = make()

    registry.register(DummyTool(name="mcp_buscar"))

    assert [tool.name for tool in view.list()] == ["leer", "escribir", "mcp_buscar"]


def test_the_view_does_not_register_anything() -> None:
    registry, view = make()

    with pytest.raises(TypeError):
        view.register(DummyTool(name="otra"))

    assert view.get("otra") is None and registry.get("otra") is None


def test_the_hidden_names_cannot_be_changed_from_outside() -> None:
    registry = InMemoryToolRegistry()
    registry.register(DummyTool(name=DELEGATE_TOOL_NAME))
    hidden = {DELEGATE_TOOL_NAME}
    view = RegistryView(registry, hidden)

    hidden.clear()

    assert view.get(DELEGATE_TOOL_NAME) is None


def test_a_name_that_is_not_text_is_an_unknown_tool() -> None:
    _, view = make()

    assert view.get(None) is None  # type: ignore[arg-type]
    with pytest.raises(UnknownToolError):
        view.validate_args(None, {})  # type: ignore[arg-type]
