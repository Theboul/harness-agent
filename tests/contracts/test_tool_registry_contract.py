"""Contract tests for the ToolRegistry port: register, get and list (HU-01-02 / T007) and
validate_args (T013, at the end of the file).

The suite checks only the behaviour that the port declares, so any implementation of
``ToolRegistry`` can reuse it: add its factory to ``REGISTRY_FACTORIES`` and every test runs
against it. ``InMemoryToolRegistry`` is the only implementation today.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest

from harness_agent.core.interfaces.tool import ToolRegistry
from harness_agent.core.tools.registry import InMemoryToolRegistry
from tests.doubles.dummy_tool import DummyTool

# One zero-argument factory per implementation of the port.
REGISTRY_FACTORIES: list[Callable[[], ToolRegistry]] = [InMemoryToolRegistry]


@pytest.fixture(params=REGISTRY_FACTORIES, ids=lambda factory: factory.__name__)
def registry(request: pytest.FixtureRequest) -> ToolRegistry:
    factory: Callable[[], ToolRegistry] = request.param
    return factory()


def test_registered_tool_is_returned_by_get(registry: ToolRegistry) -> None:
    tool = DummyTool(name="leer_archivo")

    registry.register(tool)

    assert registry.get("leer_archivo") is tool


def test_get_returns_none_for_an_unknown_name(registry: ToolRegistry) -> None:
    assert registry.get("desconocida") is None

    registry.register(DummyTool(name="conocida"))

    assert registry.get("desconocida") is None


NON_TEXT_NAMES: list[Any] = [None, 5, True, [], ["conocida"], {}, {"conocida": 1}, b"conocida"]


@pytest.mark.parametrize("name", NON_TEXT_NAMES)
def test_get_returns_none_for_a_name_that_is_not_text(registry: ToolRegistry, name: Any) -> None:
    registry.register(DummyTool(name="conocida"))

    assert registry.get(name) is None


def test_list_of_an_empty_registry_is_empty(registry: ToolRegistry) -> None:
    assert registry.list() == []


def test_list_keeps_the_registration_order(registry: ToolRegistry) -> None:
    tools = [DummyTool(name=name) for name in ("c", "a", "b")]
    for tool in tools:
        registry.register(tool)

    assert registry.list() == tools


def test_list_returns_a_new_list_every_time(registry: ToolRegistry) -> None:
    tool = DummyTool(name="t")
    registry.register(tool)

    first = registry.list()
    first.clear()

    assert registry.list() == [tool]
    assert registry.list() is not registry.list()


def test_tools_with_different_names_are_all_available(registry: ToolRegistry) -> None:
    first, second = DummyTool(name="primera"), DummyTool(name="segunda")

    registry.register(first)
    registry.register(second)

    assert registry.get("primera") is first
    assert registry.get("segunda") is second


def test_repeating_a_name_raises_value_error_and_keeps_the_original(
    registry: ToolRegistry,
) -> None:
    original = DummyTool(name="t")
    registry.register(original)

    with pytest.raises(ValueError):
        registry.register(DummyTool(name="t"))

    assert registry.get("t") is original
    assert registry.list() == [original]


# --- validate_args (T013) -----------------------------------------------------------------------


def read_file_tool() -> DummyTool:
    """A tool whose schema requires the text field ``ruta``."""
    schema = {
        "type": "object",
        "properties": {"ruta": {"type": "string"}, "limite": {"type": "integer"}},
        "required": ["ruta"],
    }
    return DummyTool(name="leer_archivo", schema=schema)


def test_validate_args_raises_value_error_for_an_unknown_name(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError):
        registry.validate_args("desconocida", {})

    registry.register(read_file_tool())

    with pytest.raises(ValueError):
        registry.validate_args("desconocida", {"ruta": "a.txt"})


@pytest.mark.parametrize(
    "args",
    [{}, {"ruta": 5}, {"ruta": "a.txt", "limite": "diez"}, {"ruta": "a.txt", "extra": 1}],
)
def test_validate_args_raises_value_error_for_invalid_arguments(
    registry: ToolRegistry, args: dict[str, Any]
) -> None:
    registry.register(read_file_tool())

    with pytest.raises(ValueError):
        registry.validate_args("leer_archivo", args)


def test_validate_args_returns_a_dict_for_valid_arguments(registry: ToolRegistry) -> None:
    registry.register(read_file_tool())
    args = {"ruta": "a.txt", "limite": 3}

    result = registry.validate_args("leer_archivo", args)

    assert isinstance(result, dict)
    assert result == args


def test_validate_args_does_not_modify_the_arguments(registry: ToolRegistry) -> None:
    registry.register(read_file_tool())
    valid = {"ruta": "a.txt", "limite": 3}
    invalid = {"ruta": 5, "extra": [1]}
    valid_before, invalid_before = copy.deepcopy(valid), copy.deepcopy(invalid)

    registry.validate_args("leer_archivo", valid)
    with pytest.raises(ValueError):
        registry.validate_args("leer_archivo", invalid)

    assert valid == valid_before
    assert invalid == invalid_before


def test_validate_args_never_runs_the_tool(registry: ToolRegistry) -> None:
    tool = read_file_tool()
    registry.register(tool)

    registry.validate_args("leer_archivo", {"ruta": "a.txt"})
    for name, args in [("leer_archivo", {}), ("desconocida", {"ruta": "a.txt"})]:
        with pytest.raises(ValueError):
            registry.validate_args(name, args)

    assert tool.recorded_executions == []
