"""Integration of the tool registry with a minimal consumer that imitates the loop (T017).

HU-01-02. ``execute_tool_call`` is everything the loop has to do with one call of the model:
validate it through the ``ToolRegistry`` port, run the tool only if the call is valid, and answer
with a ``ToolResult``. It is written FIRST, before any test registers the "new" tool, and it is
never edited afterwards: AC-02 is that a tool that the function has never heard of works anyway.
It knows only the port: it does not use ``InMemoryToolRegistry`` and it names no tool.
"""

from __future__ import annotations

import inspect
from typing import Any, cast

import pytest

from harness_agent.core import (
    InMemoryToolRegistry,
    RiskLevel,
    ToolCall,
    ToolDefinition,
    ToolRegistry,
    ToolRegistryError,
    ToolResult,
)
from tests.doubles.dummy_tool import DummyTool


async def execute_tool_call(registry: ToolRegistry, call: ToolCall) -> ToolResult:
    """Validate ``call`` through the registry, run the tool if it is valid, and answer."""
    try:
        args = registry.validate_args(call.name, call.arguments)
    except ToolRegistryError as error:
        # Nothing has been run: the text is the error for the model, as the registry wrote it.
        return ToolResult(call.id, str(error), is_error=True)
    tool = registry.get(call.name)
    assert tool is not None, "validate_args accepted a name that get does not know"
    result = await tool.run(args)
    return ToolResult(call.id, result.content, is_error=result.is_error)


# --- The tools of the tests: the first one exists before the registry is used, the second one is
# --- the "new" tool of AC-02 ------------------------------------------------------------------

READ_RESULT = ToolResult("id-de-la-herramienta", "contenido del archivo")
RUN_RESULT = ToolResult("id-de-la-herramienta", "salida del comando")


def read_file_tool() -> DummyTool:
    schema = {
        "type": "object",
        "properties": {"ruta": {"type": "string", "minLength": 1}, "limite": {"type": "integer"}},
        "required": ["ruta"],
    }
    return DummyTool(
        name="leer_archivo",
        description="Lee un archivo del espacio de trabajo",
        risk=RiskLevel.LOW,
        canned_result=READ_RESULT,
        schema=schema,
    )


def run_command_tool() -> DummyTool:
    """A tool with another name, another schema and another risk than the first one."""
    schema = {
        "type": "object",
        "properties": {"comando": {"type": "string", "minLength": 1}},
        "required": ["comando"],
    }
    return DummyTool(
        name="ejecutar_comando",
        description="Ejecuta un comando del sistema",
        risk=RiskLevel.HIGH,
        canned_result=RUN_RESULT,
        schema=schema,
    )


@pytest.fixture
def read_tool() -> DummyTool:
    return read_file_tool()


@pytest.fixture
def registry(read_tool: DummyTool) -> ToolRegistry:
    registry = InMemoryToolRegistry()
    registry.register(read_tool)
    return registry


# --- A valid call ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_valid_call_runs_the_tool_once_and_answers_with_its_content(
    registry: ToolRegistry, read_tool: DummyTool
) -> None:
    call = ToolCall("call-1", "leer_archivo", {"ruta": "a.txt", "limite": 10})

    result = await execute_tool_call(registry, call)

    assert result == ToolResult("call-1", "contenido del archivo")
    assert read_tool.recorded_executions == [{"ruta": "a.txt", "limite": 10}]


# --- Invalid calls (AC-01) ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_invalid_call_is_an_error_naming_the_field_and_runs_nothing(
    registry: ToolRegistry, read_tool: DummyTool
) -> None:
    call = ToolCall("call-2", "leer_archivo", {"limite": "diez"})

    result = await execute_tool_call(registry, call)

    assert result.call_id == "call-2"
    assert result.is_error is True
    assert result.content == (
        "Argumentos inválidos para la herramienta 'leer_archivo':\n"
        "- ruta: falta el campo requerido.\n"
        "- limite: se esperaba un entero."
    )
    assert read_tool.recorded_executions == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments, field",
    [({}, "ruta"), ({"ruta": 5}, "ruta"), ({"ruta": "a.txt", "extra": 1}, "extra")],
)
async def test_each_invalid_call_names_its_field_and_runs_nothing(
    registry: ToolRegistry, read_tool: DummyTool, arguments: dict[str, Any], field: str
) -> None:
    result = await execute_tool_call(registry, ToolCall("call-3", "leer_archivo", arguments))

    assert result.is_error is True
    assert f"- {field}:" in result.content
    assert read_tool.recorded_executions == []


@pytest.mark.asyncio
async def test_a_rejected_call_does_not_stop_the_next_valid_one(
    registry: ToolRegistry, read_tool: DummyTool
) -> None:
    rejected = await execute_tool_call(registry, ToolCall("a", "leer_archivo", {}))
    accepted = await execute_tool_call(registry, ToolCall("b", "leer_archivo", {"ruta": "a.txt"}))

    assert rejected.is_error is True
    assert accepted == ToolResult("b", "contenido del archivo")
    assert read_tool.recorded_executions == [{"ruta": "a.txt"}]


# --- Unknown tools -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_unknown_tool_is_an_error_and_runs_nothing(
    registry: ToolRegistry, read_tool: DummyTool
) -> None:
    result = await execute_tool_call(registry, ToolCall("call-4", "inexistente", {"ruta": "a"}))

    assert result == ToolResult("call-4", "Herramienta desconocida: 'inexistente'.", is_error=True)
    assert read_tool.recorded_executions == []


@pytest.mark.asyncio
@pytest.mark.parametrize("name", [None, 5, ["leer_archivo"], {"leer_archivo": 1}])
async def test_a_name_that_is_not_text_is_an_unknown_tool_end_to_end(
    registry: ToolRegistry, read_tool: DummyTool, name: Any
) -> None:
    call = ToolCall("call-5", cast(str, name), {"ruta": "a.txt"})  # what the JSON can bring

    result = await execute_tool_call(registry, call)

    assert result.is_error is True
    assert result.content.startswith("Herramienta desconocida: '")
    assert read_tool.recorded_executions == []


# --- AC-02: a tool that the consumer has never heard of ----------------------------------------


@pytest.mark.asyncio
async def test_a_new_tool_works_with_the_same_function_without_changing_it(
    registry: ToolRegistry, read_tool: DummyTool
) -> None:
    call = ToolCall("call-6", "ejecutar_comando", {"comando": "ls"})
    before = await execute_tool_call(registry, call)
    new_tool = run_command_tool()

    registry.register(new_tool)  # the only thing that is done to add it
    after = await execute_tool_call(registry, call)

    assert before == ToolResult("call-6", "Herramienta desconocida: 'ejecutar_comando'.", True)
    assert after == ToolResult("call-6", "salida del comando")
    assert new_tool.recorded_executions == [{"comando": "ls"}]
    assert read_tool.recorded_executions == []


@pytest.mark.asyncio
async def test_a_new_tool_is_validated_against_its_own_schema(registry: ToolRegistry) -> None:
    new_tool = run_command_tool()
    registry.register(new_tool)

    result = await execute_tool_call(registry, ToolCall("call-7", "ejecutar_comando", {}))

    assert result.is_error is True
    assert "- comando: falta el campo requerido." in result.content
    assert new_tool.recorded_executions == []


def test_the_consumer_knows_only_the_port_and_names_no_tool() -> None:
    source = inspect.getsource(execute_tool_call)
    parameters = inspect.signature(execute_tool_call).parameters

    assert parameters["registry"].annotation == "ToolRegistry"
    for forbidden in ("InMemoryToolRegistry", "DummyTool", "leer_archivo", "ejecutar_comando"):
        assert forbidden not in source


# --- What the loop reads from the registry, with no code specific to any tool ---------------------


def test_the_risk_of_every_tool_is_read_from_the_listing(registry: ToolRegistry) -> None:
    registry.register(run_command_tool())

    risks = {tool.name: tool.risk for tool in registry.list()}

    assert risks == {"leer_archivo": RiskLevel.LOW, "ejecutar_comando": RiskLevel.HIGH}


def test_the_definitions_for_the_model_are_built_from_the_listing(registry: ToolRegistry) -> None:
    registry.register(run_command_tool())

    definitions = [
        ToolDefinition(name=tool.name, description=tool.description, parameters=tool.schema)
        for tool in registry.list()
    ]

    assert [definition.name for definition in definitions] == ["leer_archivo", "ejecutar_comando"]
    assert definitions[0].description == "Lee un archivo del espacio de trabajo"
    assert definitions[0].parameters == read_file_tool().schema
    assert definitions[1] == ToolDefinition(
        "ejecutar_comando", "Ejecuta un comando del sistema", run_command_tool().schema
    )
