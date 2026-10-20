"""Tests for the tool registry domain errors and their model-facing messages (HU-01-02 / T003).

The texts are the ones defined in contracts/tool_registry_contract.md, section 3. They are
written in Spanish for the language model and must never reproduce received values.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import pytest

from harness_agent.core.tools.errors import (
    MAX_NAME_LENGTH,
    MAX_PATH_DISPLAY,
    MAX_RENDERED_VIOLATIONS,
    DuplicateToolError,
    InvalidToolDefinitionError,
    ToolRegistryError,
    ToolValidationError,
    UnknownToolError,
    Violation,
)


def make_violations(count: int) -> list[Violation]:
    return [Violation(f"campo{index}", f"motivo{index}.") for index in range(count)]


def rendered_lines(error: ToolRegistryError) -> list[str]:
    return str(error).split("\n")


# --- Constants ---------------------------------------------------------------------------


def test_display_limits_match_the_contract() -> None:
    assert MAX_NAME_LENGTH == 64
    assert MAX_RENDERED_VIOLATIONS == 20
    assert MAX_PATH_DISPLAY == 80


# --- Violation ---------------------------------------------------------------------------


def test_violation_exposes_path_and_message() -> None:
    violation = Violation("opciones.tiempo_maximo", "debe ser mayor o igual que 1.")

    assert violation.path == "opciones.tiempo_maximo"
    assert violation.message == "debe ser mayor o igual que 1."


def test_violation_is_frozen() -> None:
    violation = Violation("ruta", "falta el campo requerido.")

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(violation, "path", "otra")


def test_violations_are_equal_by_value() -> None:
    assert Violation("a", "b.") == Violation("a", "b.")
    assert Violation("a", "b.") != Violation("a", "c.")


# --- Hierarchy ---------------------------------------------------------------------------


def test_base_error_is_a_value_error() -> None:
    assert issubclass(ToolRegistryError, ValueError)


@pytest.mark.parametrize(
    "error_class",
    [InvalidToolDefinitionError, DuplicateToolError, UnknownToolError, ToolValidationError],
)
def test_every_error_is_a_tool_registry_error_and_a_value_error(
    error_class: type[ToolRegistryError],
) -> None:
    assert issubclass(error_class, ToolRegistryError)
    assert issubclass(error_class, ValueError)


def test_errors_can_be_caught_as_value_error_and_as_base_error() -> None:
    with pytest.raises(ValueError):
        raise UnknownToolError("x")
    with pytest.raises(ToolRegistryError):
        raise DuplicateToolError("x")


# --- ToolValidationError -----------------------------------------------------------------


def test_validation_error_keeps_tool_name_and_all_violations() -> None:
    violations = make_violations(23)

    error = ToolValidationError("leer_archivo", violations)

    assert error.tool_name == "leer_archivo"
    assert error.violations == tuple(violations)
    assert isinstance(error.violations, tuple)
    assert len(error.violations) == 23


def test_validation_error_text_has_header_and_one_line_per_violation() -> None:
    error = ToolValidationError(
        "leer_archivo",
        [
            Violation("ruta", "falta el campo requerido."),
            Violation("limite", "se esperaba un entero."),
            Violation("modo", 'valor no permitido; valores permitidos: "lectura", "escritura".'),
            Violation("opciones.tiempo_maximo", "debe ser mayor o igual que 1."),
            Violation("extra", "campo no declarado en el esquema."),
        ],
    )

    assert str(error) == (
        "Argumentos inválidos para la herramienta 'leer_archivo':\n"
        "- ruta: falta el campo requerido.\n"
        "- limite: se esperaba un entero.\n"
        '- modo: valor no permitido; valores permitidos: "lectura", "escritura".\n'
        "- opciones.tiempo_maximo: debe ser mayor o igual que 1.\n"
        "- extra: campo no declarado en el esquema."
    )


def test_empty_path_is_shown_as_arguments() -> None:
    error = ToolValidationError(
        "leer_archivo", [Violation("", "los argumentos deben ser un objeto.")]
    )

    assert str(error) == (
        "Argumentos inválidos para la herramienta 'leer_archivo':\n"
        "- (argumentos): los argumentos deben ser un objeto."
    )


def test_message_is_rendered_verbatim_without_adding_punctuation() -> None:
    # The validator guarantees that every reason ends with a period; the renderer adds nothing.
    error = ToolValidationError("t", [Violation("x", "sin punto final")])

    assert rendered_lines(error)[1] == "- x: sin punto final"


def test_exactly_the_maximum_number_of_violations_has_no_summary_line() -> None:
    error = ToolValidationError("t", make_violations(MAX_RENDERED_VIOLATIONS))

    lines = rendered_lines(error)

    assert len(lines) == 1 + MAX_RENDERED_VIOLATIONS
    assert lines[-1] == "- campo19: motivo19."
    assert "más" not in str(error)


def test_one_violation_over_the_maximum_is_summarised_in_singular() -> None:
    error = ToolValidationError("t", make_violations(21))

    lines = rendered_lines(error)

    assert len(lines) == 1 + 20 + 1
    assert lines[1:21] == [f"- campo{i}: motivo{i}." for i in range(20)]
    assert lines[-1] == "- … y 1 violación más."
    assert len(error.violations) == 21


def test_several_violations_over_the_maximum_are_summarised_in_plural() -> None:
    error = ToolValidationError("t", make_violations(23))

    lines = rendered_lines(error)

    assert len(lines) == 1 + 20 + 1
    assert lines[-1] == "- … y 3 violaciones más."
    assert "campo20" not in str(error)
    assert len(error.violations) == 23


def test_long_path_is_clipped_to_the_display_limit_with_an_ellipsis() -> None:
    long_path = "a" * 100

    error = ToolValidationError("t", [Violation(long_path, "motivo.")])

    shown_path = rendered_lines(error)[1].removeprefix("- ").removesuffix(": motivo.")
    assert len(shown_path) == MAX_PATH_DISPLAY
    assert shown_path == long_path[: MAX_PATH_DISPLAY - 1] + "…"
    assert error.violations[0].path == long_path


def test_path_of_exactly_the_display_limit_is_not_clipped() -> None:
    path = "b" * MAX_PATH_DISPLAY

    error = ToolValidationError("t", [Violation(path, "motivo.")])

    assert rendered_lines(error)[1] == f"- {path}: motivo."


def test_path_one_over_the_display_limit_is_clipped_to_the_limit() -> None:
    path = "c" * (MAX_PATH_DISPLAY + 1)

    error = ToolValidationError("t", [Violation(path, "motivo.")])

    shown_path = rendered_lines(error)[1].removeprefix("- ").removesuffix(": motivo.")
    assert len(shown_path) == MAX_PATH_DISPLAY
    assert shown_path == path[: MAX_PATH_DISPLAY - 1] + "…"


def test_long_tool_name_is_clipped_in_the_header() -> None:
    long_name = "n" * 100

    error = ToolValidationError(long_name, [Violation("x", "motivo.")])

    header = rendered_lines(error)[0]
    clipped = long_name[: MAX_NAME_LENGTH - 1] + "…"
    assert header == f"Argumentos inválidos para la herramienta '{clipped}':"
    assert error.tool_name == long_name


def test_tool_name_of_exactly_the_maximum_length_is_not_clipped() -> None:
    name = "m" * MAX_NAME_LENGTH

    error = ToolValidationError(name, [Violation("x", "motivo.")])

    assert rendered_lines(error)[0] == f"Argumentos inválidos para la herramienta '{name}':"


# Every error that shows a tool name, with the template of the line that contains it.
NAME_CASES: list[tuple[Callable[[str], ToolRegistryError], str]] = [
    (
        lambda name: ToolValidationError(name, [Violation("x", "motivo.")]),
        "Argumentos inválidos para la herramienta '{}':",
    ),
    (UnknownToolError, "Herramienta desconocida: '{}'."),
    (DuplicateToolError, "Ya existe una herramienta registrada con el nombre '{}'."),
    (
        lambda name: InvalidToolDefinitionError(name, ["nombre: motivo."]),
        "Definición inválida de la herramienta '{}':",
    ),
]


@pytest.mark.parametrize("make_error, line_template", NAME_CASES)
def test_name_of_exactly_the_maximum_length_is_never_clipped(
    make_error: Callable[[str], ToolRegistryError], line_template: str
) -> None:
    name = "a" * MAX_NAME_LENGTH

    assert rendered_lines(make_error(name))[0] == line_template.format(name)


@pytest.mark.parametrize("make_error, line_template", NAME_CASES)
def test_name_one_over_the_maximum_is_clipped_to_the_maximum_length(
    make_error: Callable[[str], ToolRegistryError], line_template: str
) -> None:
    name = "a" * (MAX_NAME_LENGTH + 1)
    shown_name = "a" * (MAX_NAME_LENGTH - 1) + "…"

    assert len(shown_name) == MAX_NAME_LENGTH
    assert rendered_lines(make_error(name))[0] == line_template.format(shown_name)


# --- UnknownToolError --------------------------------------------------------------------


def test_unknown_tool_error_text_and_attribute() -> None:
    error = UnknownToolError("nombre_pedido")

    assert error.tool_name == "nombre_pedido"
    assert str(error) == "Herramienta desconocida: 'nombre_pedido'."


def test_unknown_tool_error_clips_a_long_requested_name() -> None:
    long_name = "x" * 200

    error = UnknownToolError(long_name)

    assert str(error) == f"Herramienta desconocida: '{long_name[: MAX_NAME_LENGTH - 1]}…'."
    assert error.tool_name == long_name


# --- DuplicateToolError ------------------------------------------------------------------


def test_duplicate_tool_error_text_and_attribute() -> None:
    error = DuplicateToolError("nombre")

    assert error.tool_name == "nombre"
    assert str(error) == "Ya existe una herramienta registrada con el nombre 'nombre'."


def test_duplicate_tool_error_clips_a_long_name() -> None:
    long_name = "y" * 90

    error = DuplicateToolError(long_name)

    assert str(error) == (
        f"Ya existe una herramienta registrada con el nombre '{long_name[:63]}…'."
    )


# --- InvalidToolDefinitionError ----------------------------------------------------------


def test_invalid_definition_error_text_has_header_and_one_line_per_problem() -> None:
    problems = [
        "nombre: solo se admiten letras ASCII, dígitos, guion bajo y guion (1 a 64 caracteres).",
        "descripción: no puede estar vacía.",
        "riesgo: debe ser un RiskLevel (low, medium o high).",
        "esquema properties.limite: palabra clave no soportada 'pattern'.",
    ]

    error = InvalidToolDefinitionError("nombre", problems)

    assert error.tool_name == "nombre"
    assert error.problems == tuple(problems)
    assert isinstance(error.problems, tuple)
    assert str(error) == (
        "Definición inválida de la herramienta 'nombre':\n"
        "- nombre: solo se admiten letras ASCII, dígitos, guion bajo y guion (1 a 64 caracteres).\n"
        "- descripción: no puede estar vacía.\n"
        "- riesgo: debe ser un RiskLevel (low, medium o high).\n"
        "- esquema properties.limite: palabra clave no soportada 'pattern'."
    )


def test_invalid_definition_error_with_one_problem() -> None:
    error = InvalidToolDefinitionError("herramienta", ["descripción: no puede estar vacía."])

    assert str(error) == (
        "Definición inválida de la herramienta 'herramienta':\n- descripción: no puede estar vacía."
    )


def test_invalid_definition_error_clips_a_long_name_in_the_header() -> None:
    long_name = "z" * 80

    error = InvalidToolDefinitionError(long_name, ["nombre: demasiado largo."])

    assert rendered_lines(error)[0] == f"Definición inválida de la herramienta '{'z' * 63}…':"
