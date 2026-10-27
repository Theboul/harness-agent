"""Tests for the task definition and its Markdown parser (HU-11-01 / T002)."""

from __future__ import annotations

import pytest

from harness_agent.core.tasks import (
    MAX_CRITERIA,
    MAX_FIELD_CHARS,
    MAX_SECTION_CHARS,
    MAX_TASK_CHARS,
    CriterionDefinition,
    CriterionKind,
    TaskDefinition,
    TaskFormatError,
    parse_task,
)

SENTINEL = "VALOR-DE-PRUEBA-123"

VALID = """# TAREA-14: Validar el correo

## Objetivo
El formulario de registro debe exigir el correo.

## Contexto
Formulario en `src/forms/signup.py`.

## Reglas
- No cambiar la API pública.

## Criterios de aceptación
- El correo es obligatorio
  - comando: pytest tests/test_email.py
  - espera: codigo_salida == 0
- El mensaje de error es claro
"""


def code_of(text: str) -> str:
    with pytest.raises(TaskFormatError) as caught:
        parse_task(text)
    return caught.value.code


def test_valid_task_is_parsed_completely() -> None:
    task = parse_task(VALID)
    assert task.title == "TAREA-14: Validar el correo"
    assert task.objective == "El formulario de registro debe exigir el correo."
    assert task.context == "Formulario en `src/forms/signup.py`."
    assert task.rules == "- No cambiar la API pública."
    assert [c.kind for c in task.criteria] == [CriterionKind.OBJECTIVE, CriterionKind.SEMANTIC]
    first, second = task.criteria
    assert first.description == "El correo es obligatorio"
    assert first.command == "pytest tests/test_email.py"
    assert first.expectation == "codigo_salida == 0"
    assert second.command is None and second.expectation is None


def test_minimal_task_only_objective_and_criteria() -> None:
    task = parse_task("## Objetivo\nHacer algo\n## Criterios\n* Funciona\n")
    assert task.title is None
    assert task.context == "" and task.rules == ""
    assert task.criteria == (CriterionDefinition("Funciona"),)


def test_section_names_ignore_case_and_spaces_and_order() -> None:
    text = "##  CRITERIOS   DE  ACEPTACIÓN \n- a\n## objetivo\nx\n"
    assert parse_task(text).objective == "x"


def test_key_lines_accept_dash_prefix_and_any_case() -> None:
    text = "## Objetivo\nx\n## Criterios\n- c\n  - Comando: ls\n\t* ESPERA : codigo_salida == 0\n"
    criterion = parse_task(text).criteria[0]
    assert (criterion.command, criterion.expectation) == ("ls", "codigo_salida == 0")


def test_crlf_line_endings_are_accepted() -> None:
    assert parse_task(VALID.replace("\n", "\r\n")).title == "TAREA-14: Validar el correo"


def test_blank_lines_and_deeper_headings_are_content_of_text_sections() -> None:
    text = "## Objetivo\nUno\n\n### Detalle\nDos\n## Criterios\n- a\n"
    assert parse_task(text).objective == "Uno\n\n### Detalle\nDos"


@pytest.mark.parametrize("text", ["", "   \n\n"])
def test_empty_text_is_rejected(text: str) -> None:
    assert code_of(text) == "vacia"


def test_non_text_is_rejected() -> None:
    with pytest.raises(TaskFormatError) as caught:
        parse_task(None)  # type: ignore[arg-type]
    assert caught.value.code == "vacia"


def test_too_large_text_is_rejected() -> None:
    assert code_of("x" * (MAX_TASK_CHARS + 1)) == "demasiado_grande"


@pytest.mark.parametrize("bad", ["\x00", "\x1b", "\x7f"])
def test_control_characters_are_rejected(bad: str) -> None:
    assert code_of(VALID.replace("correo es", f"correo{bad}es")) == "contenido_no_valido"


def test_missing_objective_is_rejected() -> None:
    assert code_of("## Criterios\n- a\n") == "sin_objetivo"
    assert code_of("## Objetivo\n   \n## Criterios\n- a\n") == "sin_objetivo"


def test_missing_criteria_is_rejected_ac02() -> None:
    assert code_of("## Objetivo\nx\n") == "sin_criterios"
    assert code_of("## Objetivo\nx\n## Criterios\n\n") == "sin_criterios"


def test_missing_message_says_what_is_missing() -> None:
    with pytest.raises(TaskFormatError) as caught:
        parse_task("## Objetivo\nx\n")
    assert "criterios" in str(caught.value).lower()


def test_text_before_first_heading_is_rejected() -> None:
    assert code_of("hola\n## Objetivo\nx\n## Criterios\n- a\n") == "formato_no_valido"


def test_blank_lines_before_first_heading_are_ignored() -> None:
    assert parse_task("\n\n## Objetivo\nx\n## Criterios\n- a\n").objective == "x"


def test_second_title_or_late_title_is_rejected() -> None:
    assert code_of("# A\n# B\n## Objetivo\nx\n## Criterios\n- a\n") == "formato_no_valido"
    assert code_of("## Objetivo\nx\n# A\n## Criterios\n- a\n") == "formato_no_valido"


def test_empty_title_is_rejected() -> None:
    assert code_of("# \n## Objetivo\nx\n## Criterios\n- a\n") == "formato_no_valido"


def test_repeated_and_alias_sections_are_rejected() -> None:
    assert code_of("## Objetivo\nx\n## Objetivo\ny\n## Criterios\n- a\n") == "seccion_repetida"
    assert (
        code_of("## Objetivo\nx\n## Criterios\n- a\n## Criterios de aceptación\n- b\n")
        == "seccion_repetida"
    )


def test_unknown_section_is_rejected() -> None:
    assert code_of("## Objetivo\nx\n## Extras\ny\n## Criterios\n- a\n") == "seccion_desconocida"


@pytest.mark.parametrize(
    "criteria",
    [
        "- a\n  - comando: ls\n",
        "- a\n  - espera: ok\n",
        "- a\n  - comando:\n  - espera: ok\n",
        "- a\n  - comando: ls\n  - espera:   \n",
    ],
)
def test_unpaired_or_empty_command_expectation_is_rejected(criteria: str) -> None:
    assert code_of(f"## Objetivo\nx\n## Criterios\n{criteria}") == "criterio_incompleto"


def test_duplicated_key_is_rejected() -> None:
    text = "## Objetivo\nx\n## Criterios\n- a\n  - comando: ls\n  - comando: dir\n"
    assert code_of(text) == "criterio_incompleto"


@pytest.mark.parametrize(
    "criteria",
    [
        "texto suelto\n",
        "- \n",
        "  - comando: ls\n",
        "- a\n  sin clave\n",
        "- a\n  - otra: cosa\n",
    ],
)
def test_malformed_criteria_lines_are_rejected(criteria: str) -> None:
    assert code_of(f"## Objetivo\nx\n## Criterios\n{criteria}") == "formato_no_valido"


def test_too_many_criteria_is_rejected() -> None:
    items = "".join(f"- c{i}\n" for i in range(MAX_CRITERIA + 1))
    assert code_of(f"## Objetivo\nx\n## Criterios\n{items}") == "demasiados_criterios"
    ok = "".join(f"- c{i}\n" for i in range(MAX_CRITERIA))
    assert len(parse_task(f"## Objetivo\nx\n## Criterios\n{ok}").criteria) == MAX_CRITERIA


def test_long_fields_are_rejected() -> None:
    long = "x" * (MAX_FIELD_CHARS + 1)
    assert code_of(f"## Objetivo\nx\n## Criterios\n- {long}\n") == "texto_demasiado_largo"
    assert (
        code_of(f"## Objetivo\nx\n## Criterios\n- a\n  - comando: {long}\n  - espera: ok\n")
        == "texto_demasiado_largo"
    )
    assert (
        code_of(f"## Objetivo\nx\n## Criterios\n- a\n  - comando: ls\n  - espera: {long}\n")
        == "texto_demasiado_largo"
    )
    section = "y" * (MAX_SECTION_CHARS + 1)
    assert code_of(f"## Objetivo\n{section}\n## Criterios\n- a\n") == "texto_demasiado_largo"
    assert code_of(f"# {long}\n## Objetivo\nx\n## Criterios\n- a\n") == "texto_demasiado_largo"


def test_error_messages_are_fixed_spanish_and_never_echo_the_input() -> None:
    inputs = [
        f"{SENTINEL}\n",
        f"## Objetivo\n{SENTINEL}\n",
        f"## {SENTINEL}\nx\n",
        f"## Objetivo\nx\n## Criterios\n- {SENTINEL}\n  - comando: ls\n",
        f"## Objetivo\nx\n## Criterios\n{SENTINEL}\n",
    ]
    for text in inputs:
        with pytest.raises(TaskFormatError) as caught:
            parse_task(text)
        assert SENTINEL not in str(caught.value)
        assert str(caught.value).strip()


def test_criterion_definition_invariants() -> None:
    assert CriterionDefinition("a", "ls", "ok").kind is CriterionKind.OBJECTIVE
    assert CriterionDefinition("a").kind is CriterionKind.SEMANTIC
    for args in [("", None, None), ("a", "ls", None), ("a", None, "ok"), ("a", " ", " ")]:
        with pytest.raises(ValueError):
            CriterionDefinition(*args)


def test_task_definition_invariants() -> None:
    criterion = CriterionDefinition("a")
    TaskDefinition(title=None, objective="o", context="", rules="", criteria=(criterion,))
    with pytest.raises(ValueError):
        TaskDefinition(title=None, objective=" ", context="", rules="", criteria=(criterion,))
    with pytest.raises(ValueError):
        TaskDefinition(title=None, objective="o", context="", rules="", criteria=())


def test_with_title_fills_only_a_missing_title() -> None:
    task = parse_task("## Objetivo\nx\n## Criterios\n- a\n")
    assert task.with_title("Del issue").title == "Del issue"
    titled = parse_task(VALID)
    assert titled.with_title("Otro") is titled
    assert task.with_title("  ") is task


# --- the expected condition (HU-11-04.1) ----------------------------------------------------------

CONDITION_TASK = "## Objetivo\nx\n## Criterios\n- a\n  - comando: ls\n  - espera: {condition}\n"


@pytest.mark.parametrize(
    "condition", ["salida 0", "ok", "codigo_salida >= 0", "codigo_salida == -1"]
)
def test_an_unsupported_condition_makes_the_task_invalid(condition: str) -> None:
    assert code_of(CONDITION_TASK.format(condition=condition)) == "condicion_no_soportada"


def test_the_unsupported_condition_message_does_not_repeat_the_text() -> None:
    with pytest.raises(TaskFormatError) as caught:
        parse_task(CONDITION_TASK.format(condition=SENTINEL))
    assert SENTINEL not in str(caught.value)
    assert "codigo_salida == N" in str(caught.value)


def test_a_not_equal_condition_is_accepted() -> None:
    task = parse_task(CONDITION_TASK.format(condition="codigo_salida != 1"))
    assert task.criteria[0].expectation == "codigo_salida != 1"


def test_the_pair_check_comes_before_the_condition_check() -> None:
    text = "## Objetivo\nx\n## Criterios\n- a\n  - comando: ls\n"
    assert code_of(text) == "criterio_incompleto"
