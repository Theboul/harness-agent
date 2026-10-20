"""Tests for InMemoryToolRegistry: registering, looking up and listing tools (HU-01-02 / T006) and
validating the arguments of a call (``validate_args``, T013, at the end of the file).

Every definition problem is a sentence that ends with a period and starts with the attribute it
is about (``nombre:``, ``descripción:``, ``riesgo:``) or with ``esquema `` followed by a problem
of ``check_schema``.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Callable, Coroutine
from typing import Any, cast

import pytest

from harness_agent.core.entities import ToolResult
from harness_agent.core.interfaces.tool import RiskLevel, Tool, ToolRegistry
from harness_agent.core.tools.errors import (
    DuplicateToolError,
    InvalidToolDefinitionError,
    ToolRegistryError,
    ToolValidationError,
    UnknownToolError,
    Violation,
)
from harness_agent.core.tools.registry import InMemoryToolRegistry
from tests.doubles.dummy_tool import DummyTool

NAME_PROBLEM = (
    "nombre: solo se admiten letras ASCII, dígitos, guion bajo y guion (1 a 64 caracteres)."
)
DESCRIPTION_PROBLEM = "descripción: no puede estar vacía."
RISK_PROBLEM = "riesgo: debe ser un RiskLevel (low, medium o high)."
PATTERN_PROBLEM = "esquema properties.limite: palabra clave no soportada 'pattern'."
DEPTH_SENTENCE = "se supera la profundidad máxima de 32 niveles de anidamiento."
COPY_PROBLEM = (
    "esquema (raíz): contiene valores que no se pueden copiar; solo se admiten datos JSON."
)
PREFIXES = ("nombre:", "descripción:", "riesgo:", "esquema ")

_DEFAULT = object()


def pattern_schema() -> dict[str, Any]:
    """A schema with exactly one problem: the unsupported keyword ``pattern``."""
    return {
        "type": "object",
        "properties": {"limite": {"type": "integer", "pattern": "^[0-9]+$"}},
    }


def circular_schema() -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": {}}
    schema["properties"]["self"] = schema
    return schema


class OddTool(DummyTool):
    """DummyTool whose attributes can be any object, to exercise invalid definitions."""

    def __init__(
        self,
        *,
        name: object = "odd",
        description: object = "Odd tool",
        risk: object = RiskLevel.LOW,
        schema: object = _DEFAULT,
    ) -> None:
        super().__init__()
        self._odd_name = name
        self._odd_description = description
        self._odd_risk = risk
        self._odd_schema = schema

    @property
    def name(self) -> str:
        return cast(str, self._odd_name)

    @property
    def description(self) -> str:
        return cast(str, self._odd_description)

    @property
    def risk(self) -> RiskLevel:
        return cast(RiskLevel, self._odd_risk)

    @property
    def schema(self) -> dict[str, Any]:
        if self._odd_schema is _DEFAULT:
            return super().schema
        return cast(dict[str, Any], self._odd_schema)


class CountingTool(DummyTool):
    """DummyTool that counts how many times each attribute is read."""

    def __init__(self) -> None:
        super().__init__(name="counted", schema={"type": "object"})
        self.reads = {"name": 0, "description": 0, "risk": 0, "schema": 0}

    @property
    def name(self) -> str:
        self.reads["name"] += 1
        return super().name

    @property
    def description(self) -> str:
        self.reads["description"] += 1
        return super().description

    @property
    def risk(self) -> RiskLevel:
        self.reads["risk"] += 1
        return super().risk

    @property
    def schema(self) -> dict[str, Any]:
        self.reads["schema"] += 1
        return super().schema


class ShiftingNameTool(DummyTool):
    """DummyTool whose name is different every time it is read."""

    def __init__(self) -> None:
        super().__init__()
        self._reads = 0

    @property
    def name(self) -> str:
        self._reads += 1
        return f"name{self._reads}"


def registered_names(registry: ToolRegistry) -> list[str]:
    return [tool.name for tool in registry.list()]


def rejected(tool: Tool, registry: ToolRegistry | None = None) -> InvalidToolDefinitionError:
    """Register ``tool`` expecting an invalid definition and return the error."""
    target = registry if registry is not None else InMemoryToolRegistry()
    with pytest.raises(InvalidToolDefinitionError) as info:
        target.register(tool)
    return info.value


# --- The registry as an implementation of the port --------------------------------------------


def test_registry_implements_the_port_and_needs_no_constructor_arguments() -> None:
    assert isinstance(InMemoryToolRegistry(), ToolRegistry)


# --- Registering, looking up and listing --------------------------------------------------------


def test_get_returns_the_registered_instance() -> None:
    registry = InMemoryToolRegistry()
    tool = DummyTool(name="leer_archivo")

    registry.register(tool)

    assert registry.get("leer_archivo") is tool


def test_get_returns_none_for_an_unknown_name() -> None:
    registry = InMemoryToolRegistry()
    assert registry.get("nada") is None

    registry.register(DummyTool(name="algo"))

    assert registry.get("nada") is None


def test_list_of_an_empty_registry_is_empty() -> None:
    assert InMemoryToolRegistry().list() == []


def test_list_keeps_the_registration_order() -> None:
    registry = InMemoryToolRegistry()
    for name in ("c", "a", "b"):
        registry.register(DummyTool(name=name))

    assert registered_names(registry) == ["c", "a", "b"]


def test_list_returns_a_new_list_every_time() -> None:
    registry = InMemoryToolRegistry()
    tool = DummyTool(name="t")
    registry.register(tool)

    first = registry.list()
    first.clear()

    assert registry.list() == [tool]
    assert registry.list() is not registry.list()


def test_duplicate_name_raises_duplicate_error_and_keeps_the_original() -> None:
    registry = InMemoryToolRegistry()
    original = DummyTool(name="t", description="Original")
    registry.register(original)

    with pytest.raises(DuplicateToolError) as info:
        registry.register(DummyTool(name="t", description="Otra"))

    assert isinstance(info.value, ValueError)
    assert info.value.tool_name == "t"
    assert str(info.value) == "Ya existe una herramienta registrada con el nombre 't'."
    assert registry.get("t") is original
    assert registry.list() == [original]


def test_names_are_case_sensitive() -> None:
    registry = InMemoryToolRegistry()
    upper = DummyTool(name="Shell")
    lower = DummyTool(name="shell")

    registry.register(upper)
    registry.register(lower)

    assert registry.get("Shell") is upper
    assert registry.get("shell") is lower
    with pytest.raises(DuplicateToolError):
        registry.register(DummyTool(name="shell"))


# --- Names ----------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["leer_archivo", "a-b_1", "n" * 64, "A", "_", "-"])
def test_valid_names_are_accepted(name: str) -> None:
    registry = InMemoryToolRegistry()
    tool = DummyTool(name=name)

    registry.register(tool)

    assert registry.get(name) is tool


@pytest.mark.parametrize(
    "name",
    ["", "con espacios", "acción", "con.punto", "n" * 65, "nombre\n", "\nnombre", "h٣"],
)
def test_invalid_names_are_rejected_with_the_contract_text(name: str) -> None:
    registry = InMemoryToolRegistry()

    error = rejected(DummyTool(name=name), registry)

    assert error.problems == (NAME_PROBLEM,)
    assert registry.list() == []


@pytest.mark.parametrize("name", [None, 5, b"bytes", ["lista"]])
def test_a_name_that_is_not_text_is_a_clear_problem_not_a_crash(name: object) -> None:
    error = rejected(OddTool(name=name))

    assert error.problems == ("nombre: debe ser un texto.",)
    assert str(error).split("\n")[0] == f"Definición inválida de la herramienta '{name}':"


# --- Descriptions ----------------------------------------------------------------------------


@pytest.mark.parametrize("description", ["x", "  texto con espacios alrededor  "])
def test_non_empty_descriptions_are_accepted(description: str) -> None:
    registry = InMemoryToolRegistry()
    tool = DummyTool(name="t", description=description)

    registry.register(tool)

    assert registry.get("t") is tool


@pytest.mark.parametrize("description", ["", " ", "   ", "\t\n ", " "])
def test_empty_or_blank_descriptions_are_rejected(description: str) -> None:
    error = rejected(DummyTool(name="t", description=description))

    assert error.problems == (DESCRIPTION_PROBLEM,)


@pytest.mark.parametrize("description", [None, 3, b"bytes"])
def test_a_description_that_is_not_text_is_a_clear_problem_not_a_crash(
    description: object,
) -> None:
    error = rejected(OddTool(description=description))

    assert error.problems == ("descripción: debe ser un texto.",)


# --- Risk -------------------------------------------------------------------------------------


@pytest.mark.parametrize("risk", list(RiskLevel))
def test_every_risk_level_is_accepted(risk: RiskLevel) -> None:
    registry = InMemoryToolRegistry()
    tool = DummyTool(name="t", risk=risk)

    registry.register(tool)

    assert registry.get("t") is tool


@pytest.mark.parametrize("risk", ["low", "LOW", None, 1, object()])
def test_a_risk_that_is_not_a_risk_level_is_rejected(risk: object) -> None:
    error = rejected(OddTool(name="t", risk=risk))

    assert error.problems == (RISK_PROBLEM,)


# --- Schema -----------------------------------------------------------------------------------


def test_invalid_schema_is_rejected_with_the_prefixed_check_schema_problem() -> None:
    error = rejected(DummyTool(name="t", schema=pattern_schema()))

    assert error.problems == (PATTERN_PROBLEM,)


def test_every_schema_problem_gets_the_prefix() -> None:
    schema = {"type": "object", "oneOf": [], "pattern": "x"}

    error = rejected(DummyTool(name="t", schema=schema))

    assert error.problems == (
        "esquema (raíz): palabra clave no soportada 'oneOf'.",
        "esquema (raíz): palabra clave no soportada 'pattern'.",
    )


def test_a_schema_that_is_not_a_mapping_is_a_problem_not_a_crash() -> None:
    error = rejected(OddTool(name="t", schema="no soy un esquema"))

    assert error.problems == ("esquema (raíz): el esquema debe ser un objeto.",)


def test_a_circular_schema_is_rejected_without_recursion_errors() -> None:
    registry = InMemoryToolRegistry()

    error = rejected(DummyTool(name="t", schema=circular_schema()), registry)

    assert len(error.problems) == 1
    assert error.problems[0].startswith("esquema properties.self.")
    assert error.problems[0].endswith(DEPTH_SENTENCE)
    assert registry.list() == []


def test_a_schema_that_cannot_be_copied_is_an_invalid_definition_not_a_crash() -> None:
    registry = InMemoryToolRegistry()
    registry.register(DummyTool(name="primera"))
    # check_schema accepts any value in `default`, but a lock cannot be deep-copied.
    schema = {"type": "object", "default": threading.Lock()}

    error = rejected(DummyTool(name="nueva", schema=schema), registry)

    assert error.problems == (COPY_PROBLEM,)
    assert registered_names(registry) == ["primera"]


# --- Several problems, in order ---------------------------------------------------------------


def test_all_problems_are_reported_together_in_attribute_order() -> None:
    tool = OddTool(name="mal nombre", description="  ", risk="low", schema=pattern_schema())

    error = rejected(tool)

    assert error.problems == (NAME_PROBLEM, DESCRIPTION_PROBLEM, RISK_PROBLEM, PATTERN_PROBLEM)
    assert str(error) == (
        "Definición inválida de la herramienta 'mal nombre':\n"
        f"- {NAME_PROBLEM}\n"
        f"- {DESCRIPTION_PROBLEM}\n"
        f"- {RISK_PROBLEM}\n"
        f"- {PATTERN_PROBLEM}"
    )


def test_definition_problems_are_reported_before_the_duplicate_check() -> None:
    registry = InMemoryToolRegistry()
    registry.register(DummyTool(name="t"))

    error = rejected(DummyTool(name="t", description=""), registry)

    assert error.problems == (DESCRIPTION_PROBLEM,)


# --- Atomicity ----------------------------------------------------------------------------------

REJECTED_TOOLS: list[tuple[str, Callable[[], Tool]]] = [
    ("nombre inválido", lambda: DummyTool(name="mal nombre")),
    ("descripción vacía", lambda: DummyTool(name="nueva", description=" ")),
    ("riesgo inválido", lambda: OddTool(name="nueva", risk="low")),
    ("esquema inválido", lambda: DummyTool(name="nueva", schema=pattern_schema())),
    ("esquema circular", lambda: DummyTool(name="nueva", schema=circular_schema())),
    ("varios problemas", lambda: OddTool(name="", description="", risk=None)),
    ("nombre repetido", lambda: DummyTool(name="primera")),
]


@pytest.mark.parametrize("label, make_tool", REJECTED_TOOLS, ids=[row[0] for row in REJECTED_TOOLS])
def test_a_rejected_registration_leaves_the_catalog_unchanged(
    label: str, make_tool: Callable[[], Tool]
) -> None:
    registry = InMemoryToolRegistry()
    first, second = DummyTool(name="primera"), DummyTool(name="segunda")
    registry.register(first)
    registry.register(second)
    before = registry.list()

    with pytest.raises(ToolRegistryError):
        registry.register(make_tool())

    assert registry.list() == before == [first, second]
    assert registry.get("primera") is first
    assert registry.get("segunda") is second
    assert registry.get("nueva") is None


# --- Shape of the problems ------------------------------------------------------------------------

BROKEN_DEFINITIONS: list[Callable[[], Tool]] = [
    lambda: DummyTool(name="mal nombre"),
    lambda: OddTool(name=None),
    lambda: DummyTool(name="t", description=""),
    lambda: OddTool(description=None),
    lambda: OddTool(risk="low"),
    lambda: DummyTool(name="t", schema=pattern_schema()),
    lambda: DummyTool(name="t", schema=circular_schema()),
    lambda: OddTool(schema=None),
    lambda: OddTool(name="mal nombre", description="", risk=None, schema=pattern_schema()),
]


@pytest.mark.parametrize("make_tool", BROKEN_DEFINITIONS)
def test_every_definition_problem_has_a_known_prefix_and_ends_with_a_period(
    make_tool: Callable[[], Tool],
) -> None:
    error = rejected(make_tool())

    assert error.problems
    for problem in error.problems:
        assert problem.startswith(PREFIXES), problem
        assert problem.endswith("."), problem


# --- The attributes are read once ----------------------------------------------------------------


def test_register_reads_each_attribute_exactly_once() -> None:
    registry = InMemoryToolRegistry()
    tool = CountingTool()

    registry.register(tool)

    assert tool.reads == {"name": 1, "description": 1, "risk": 1, "schema": 1}


def test_the_name_read_at_registration_is_the_key_in_the_catalog() -> None:
    registry = InMemoryToolRegistry()
    tool = ShiftingNameTool()

    registry.register(tool)

    assert registry.get("name1") is tool
    assert registry.get("name2") is None


# --- validate_args (T013) -------------------------------------------------------------------------

SENTINEL = "SECRETO-123"
MISSING_ROUTE = Violation("ruta", "falta el campo requerido.")
BAD_LIMIT = Violation("limite", "se esperaba un entero.")
NOT_AN_OBJECT = Violation("", "los argumentos deben ser un objeto.")


def read_file_schema() -> dict[str, Any]:
    """A fresh schema with a required text field and an optional integer."""
    return {
        "type": "object",
        "properties": {
            "ruta": {"type": "string", "minLength": 1},
            "limite": {"type": "integer", "minimum": 1},
        },
        "required": ["ruta"],
    }


class RunSpyTool(DummyTool):
    """DummyTool that notices ANY call to ``run``, even one whose coroutine is never awaited."""

    def __init__(self, name: str = "leer_archivo", schema: dict[str, Any] | None = None) -> None:
        super().__init__(name=name, schema=schema if schema is not None else read_file_schema())
        self.run_calls = 0

    def run(self, args: dict[str, Any]) -> Coroutine[Any, Any, ToolResult]:
        self.run_calls += 1
        return super().run(args)


class LaxAfterRegistrationTool(DummyTool):
    """DummyTool whose ``schema`` is strict when read at registration and lax from then on."""

    def __init__(self) -> None:
        super().__init__(name="leer_archivo")
        self._reads = 0

    @property
    def schema(self) -> dict[str, Any]:
        self._reads += 1
        if self._reads == 1:
            return read_file_schema()
        return {"type": "object", "additionalProperties": True}


def registry_with(*tools: Tool) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def validation_error(registry: ToolRegistry, name: Any, args: Any) -> ToolValidationError:
    """Call ``validate_args`` expecting a validation failure and return the error."""
    with pytest.raises(ToolValidationError) as info:
        registry.validate_args(name, args)
    return info.value


# Unknown tools


def test_an_unregistered_name_raises_unknown_tool_error_citing_the_name() -> None:
    registry = registry_with(RunSpyTool())

    with pytest.raises(UnknownToolError) as info:
        registry.validate_args("inexistente", {})

    assert isinstance(info.value, ToolRegistryError)
    assert isinstance(info.value, ValueError)
    assert info.value.tool_name == "inexistente"
    assert str(info.value) == "Herramienta desconocida: 'inexistente'."


def test_an_empty_registry_has_no_tool_to_validate_against() -> None:
    with pytest.raises(UnknownToolError):
        InMemoryToolRegistry().validate_args("leer_archivo", {})


def test_the_unknown_tool_error_does_not_list_the_available_tools() -> None:
    registry = registry_with(RunSpyTool(name="leer_archivo"), RunSpyTool(name="escribir_archivo"))

    with pytest.raises(UnknownToolError) as info:
        registry.validate_args("otra", {})

    assert "leer_archivo" not in str(info.value)
    assert "escribir_archivo" not in str(info.value)


@pytest.mark.parametrize("name", ["LEER_ARCHIVO", "leer_archivo ", " leer_archivo", "leer", ""])
def test_the_name_must_match_exactly(name: str) -> None:
    registry = registry_with(RunSpyTool(name="leer_archivo"))

    with pytest.raises(UnknownToolError):
        registry.validate_args(name, {"ruta": "a.txt"})


# What the JSON of the model can put where a name should be, hashable or not.
NON_TEXT_NAMES: list[Any] = [
    None,
    5,
    1.5,
    True,
    [],
    ["leer_archivo"],
    {},
    {"leer_archivo": 1},
    ("leer_archivo",),
    b"x",
]


@pytest.mark.parametrize("name", NON_TEXT_NAMES)
def test_a_name_that_is_not_text_is_an_unknown_tool_not_a_type_error(name: Any) -> None:
    # The name comes from the JSON of the model: a list or a mapping is not even hashable. A tool
    # called "None" or "5" must not be found through the text of a name that is not text.
    registry = registry_with(RunSpyTool(), RunSpyTool(name="None"), RunSpyTool(name="5"))

    with pytest.raises(UnknownToolError) as info:
        registry.validate_args(name, {"ruta": "a.txt"})

    assert isinstance(info.value, ValueError)
    assert info.value.tool_name == str(name)
    assert str(info.value).startswith("Herramienta desconocida: '")


@pytest.mark.parametrize("name", NON_TEXT_NAMES)
def test_get_with_a_name_that_is_not_text_returns_none_not_a_type_error(name: Any) -> None:
    # Like validate_args: a name that is not text is an unknown tool, and a tool called "None" or
    # "5" is not found through the text of a name that is not text.
    registry = registry_with(RunSpyTool(), RunSpyTool(name="None"), RunSpyTool(name="5"))

    assert registry.get(name) is None


# Invalid arguments


def test_invalid_arguments_raise_tool_validation_error_with_the_violations() -> None:
    registry = registry_with(RunSpyTool())

    error = validation_error(registry, "leer_archivo", {"limite": "diez"})

    assert isinstance(error, ToolRegistryError)
    assert isinstance(error, ValueError)
    assert error.tool_name == "leer_archivo"
    assert error.violations == (MISSING_ROUTE, BAD_LIMIT)


def test_the_error_text_names_every_invalid_field() -> None:
    registry = registry_with(RunSpyTool())

    error = validation_error(registry, "leer_archivo", {"limite": "diez"})

    assert str(error) == (
        "Argumentos inválidos para la herramienta 'leer_archivo':\n"
        "- ruta: falta el campo requerido.\n"
        "- limite: se esperaba un entero."
    )


@pytest.mark.parametrize(
    "args, expected",
    [
        ({}, (MISSING_ROUTE,)),
        ({"ruta": 5}, (Violation("ruta", "se esperaba una cadena de texto."),)),
        ({"ruta": ""}, (Violation("ruta", "debe tener al menos 1 carácter."),)),
        ({"ruta": "a", "limite": 0}, (Violation("limite", "debe ser mayor o igual que 1."),)),
        ({"ruta": "a", "extra": 1}, (Violation("extra", "campo no declarado en el esquema."),)),
    ],
)
def test_each_kind_of_violation_reaches_the_error_with_the_field_name(
    args: dict[str, Any], expected: tuple[Violation, ...]
) -> None:
    error = validation_error(registry_with(RunSpyTool()), "leer_archivo", args)

    assert error.violations == expected
    assert f"- {expected[0].path}: {expected[0].message}" in str(error)


@pytest.mark.parametrize("args", [None, [], ["ruta"], "ruta", 5, True])
def test_arguments_that_are_not_a_mapping_are_a_single_root_violation(args: Any) -> None:
    error = validation_error(registry_with(RunSpyTool()), "leer_archivo", args)

    assert error.violations == (NOT_AN_OBJECT,)
    assert str(error) == (
        "Argumentos inválidos para la herramienta 'leer_archivo':\n"
        "- (argumentos): los argumentos deben ser un objeto."
    )


def test_the_error_keeps_every_violation_although_its_text_shows_twenty() -> None:
    fields = [f"campo{number:02d}" for number in range(25)]
    schema = {
        "type": "object",
        "properties": {name: {"type": "string"} for name in fields},
        "required": fields,
    }
    registry = registry_with(RunSpyTool(schema=schema))

    error = validation_error(registry, "leer_archivo", {})

    assert [violation.path for violation in error.violations] == fields
    lines = str(error).splitlines()
    assert len(lines) == 1 + 20 + 1
    assert lines[-1] == "- … y 5 violaciones más."


def test_received_values_are_not_echoed_in_the_error() -> None:
    registry = registry_with(RunSpyTool())

    error = validation_error(
        registry, "leer_archivo", {"ruta": 5, "limite": SENTINEL, "extra": SENTINEL}
    )

    assert SENTINEL not in str(error)
    for violation in error.violations:
        assert SENTINEL not in violation.message
        assert SENTINEL not in violation.path


def test_each_tool_is_validated_against_its_own_schema() -> None:
    writer_schema = {
        "type": "object",
        "properties": {"contenido": {"type": "string"}},
        "required": ["contenido"],
    }
    registry = registry_with(
        DummyTool(name="leer_archivo", schema=read_file_schema()),
        DummyTool(name="escribir_archivo", schema=writer_schema),
    )
    args = {"ruta": "a.txt"}

    assert registry.validate_args("leer_archivo", args) == args
    error = validation_error(registry, "escribir_archivo", args)
    assert error.tool_name == "escribir_archivo"
    assert error.violations == (
        Violation("contenido", "falta el campo requerido."),
        Violation("ruta", "campo no declarado en el esquema."),
    )


def test_a_rejection_leaves_no_trace_and_a_later_valid_call_passes() -> None:
    registry = registry_with(RunSpyTool())

    first = validation_error(registry, "leer_archivo", {"limite": "diez"})
    second = validation_error(registry, "leer_archivo", {"limite": "diez"})

    assert first.violations == second.violations
    assert str(first) == str(second)
    assert registry.validate_args("leer_archivo", {"ruta": "a.txt"}) == {"ruta": "a.txt"}
    assert registered_names(registry) == ["leer_archivo"]


# The registry never runs the tool


@pytest.mark.parametrize(
    "name, args",
    [
        ("inexistente", {"ruta": "a.txt"}),
        ("leer_archivo", {}),
        ("leer_archivo", {"ruta": 5}),
        ("leer_archivo", {"ruta": "a.txt", "extra": 1}),
        ("leer_archivo", None),
        ("leer_archivo", ["ruta"]),
    ],
)
def test_a_rejection_never_runs_the_tool(name: str, args: Any) -> None:
    tool = RunSpyTool()
    registry = registry_with(tool)

    with pytest.raises(ToolRegistryError):
        registry.validate_args(name, args)

    assert tool.recorded_executions == []
    assert tool.run_calls == 0


def test_valid_arguments_do_not_run_the_tool_either() -> None:
    tool = RunSpyTool()
    registry = registry_with(tool)

    registry.validate_args("leer_archivo", {"ruta": "a.txt", "limite": 3})

    assert tool.recorded_executions == []
    assert tool.run_calls == 0


# Valid arguments


def test_valid_arguments_return_an_equal_dict_that_is_not_the_same_object() -> None:
    registry = registry_with(RunSpyTool())
    args = {"ruta": "a.txt", "limite": 10}

    result = registry.validate_args("leer_archivo", args)

    assert result == args
    assert result is not args
    assert type(result) is dict


def test_validating_does_not_modify_the_arguments_valid_or_not() -> None:
    registry = registry_with(RunSpyTool())
    valid = {"ruta": "a.txt", "limite": 10}
    invalid = {"ruta": 5, "limite": "diez", "extra": [1, {"k": None}]}
    valid_before, invalid_before = copy.deepcopy(valid), copy.deepcopy(invalid)

    registry.validate_args("leer_archivo", valid)
    with pytest.raises(ToolValidationError):
        registry.validate_args("leer_archivo", invalid)

    assert valid == valid_before
    assert invalid == invalid_before


def test_changing_the_result_does_not_change_the_original_arguments() -> None:
    registry = registry_with(RunSpyTool())
    args = {"ruta": "a.txt"}

    result = registry.validate_args("leer_archivo", args)
    result["ruta"] = "otra.txt"
    result["nuevo"] = 1

    assert args == {"ruta": "a.txt"}


def test_the_copy_is_shallow_nested_values_are_shared() -> None:
    schema = {
        "type": "object",
        "properties": {
            "opciones": {"type": "object", "properties": {"tiempo": {"type": "integer"}}},
            "archivos": {"type": "array", "items": {"type": "string"}},
        },
    }
    registry = registry_with(DummyTool(name="leer_archivo", schema=schema))
    args = {"opciones": {"tiempo": 3}, "archivos": ["a", "b"]}

    result = registry.validate_args("leer_archivo", args)

    assert result == args
    assert result["opciones"] is args["opciones"]
    assert result["archivos"] is args["archivos"]


def test_valid_arguments_come_back_without_coercion_or_default_values() -> None:
    schema = {
        "type": "object",
        "properties": {
            "ruta": {"type": "string"},
            "limite": {"type": "integer", "default": 10},
            "tiempo": {"type": "integer"},
        },
    }
    registry = registry_with(DummyTool(name="leer_archivo", schema=schema))

    result = registry.validate_args("leer_archivo", {"ruta": "a.txt", "tiempo": 3.0})

    assert result == {"ruta": "a.txt", "tiempo": 3.0}
    assert "limite" not in result
    assert type(result["tiempo"]) is float


def test_empty_arguments_are_valid_when_nothing_is_required() -> None:
    registry = registry_with(DummyTool(name="leer_archivo"))
    args: dict[str, Any] = {}

    result = registry.validate_args("leer_archivo", args)

    assert result == {}
    assert result is not args


# The schema is the one taken at registration


def test_removing_required_from_the_tool_schema_does_not_weaken_the_validation() -> None:
    schema = read_file_schema()
    registry = registry_with(DummyTool(name="leer_archivo", schema=schema))

    del schema["required"]  # the tool hands out the very same dict that it keeps

    error = validation_error(registry, "leer_archivo", {})
    assert error.violations == (MISSING_ROUTE,)


def test_other_changes_to_the_tool_schema_after_registering_are_ignored() -> None:
    schema = read_file_schema()
    registry = registry_with(DummyTool(name="leer_archivo", schema=schema))

    schema["properties"]["limite"]["type"] = "string"
    schema["properties"]["ruta"]["minLength"] = 0
    schema["additionalProperties"] = True

    error = validation_error(registry, "leer_archivo", {"ruta": "", "limite": "diez", "extra": 1})
    assert error.violations == (
        Violation("ruta", "debe tener al menos 1 carácter."),
        BAD_LIMIT,
        Violation("extra", "campo no declarado en el esquema."),
    )


def test_a_tool_that_hands_out_another_schema_later_is_still_validated_with_the_first() -> None:
    registry = registry_with(LaxAfterRegistrationTool())

    error = validation_error(registry, "leer_archivo", {})

    assert error.violations == (MISSING_ROUTE,)


def test_validate_args_does_not_read_the_attributes_of_the_tool_again() -> None:
    tool = CountingTool()
    registry = registry_with(tool)

    registry.validate_args("counted", {})

    assert tool.reads == {"name": 1, "description": 1, "risk": 1, "schema": 1}


def test_the_error_carries_the_registered_name_even_if_the_tool_changes_its_name() -> None:
    registry = registry_with(ShiftingNameTool())  # registered as "name1"; later reads say "name2"

    error = validation_error(registry, "name1", {"extra": 1})

    assert error.tool_name == "name1"
    assert str(error).startswith("Argumentos inválidos para la herramienta 'name1':")
