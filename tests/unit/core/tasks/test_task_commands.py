"""Tests for the verification commands of a task: the ``## Comandos`` section (HU-11-03 / T002).

The extension of the task format is additive: a task without the section is parsed as before
(``tests/unit/core/tasks/test_task_parser.py`` stays unchanged), while a task with it declares at
most one command for the tests and one for the lint, each with an optional time limit.
"""

from __future__ import annotations

import pytest

import harness_agent.core as core
from harness_agent.core.tasks import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    MAX_COMMAND_TEXT_CHARS,
    MAX_COMMAND_TIMEOUT_SECONDS,
    MAX_FIELD_CHARS,
    CommandKind,
    CriterionDefinition,
    TaskCommand,
    TaskDefinition,
    TaskFormatError,
    commands_notice,
    parse_task,
)

SENTINEL = "VALOR-DE-PRUEBA-123"

BASE = """## Objetivo
Corregir el cálculo.

## Criterios de aceptación
- Las pruebas pasan
  - comando: python -m pytest
  - espera: codigo_salida == 0
"""


def with_commands(section: str) -> str:
    return BASE + "\n## Comandos\n" + section


def code_of(text: str) -> str:
    with pytest.raises(TaskFormatError) as caught:
        parse_task(text)
    assert SENTINEL not in str(caught.value)
    return caught.value.code


# --- TaskCommand -------------------------------------------------------------------------------


class TestTaskCommand:
    def test_the_constants(self) -> None:
        assert DEFAULT_COMMAND_TIMEOUT_SECONDS == 300
        assert MAX_COMMAND_TIMEOUT_SECONDS == 600
        assert MAX_COMMAND_TEXT_CHARS == MAX_FIELD_CHARS

    def test_the_kinds_are_named_as_in_the_task(self) -> None:
        assert CommandKind.TESTS.value == "pruebas"
        assert CommandKind.LINT.value == "lint"

    def test_the_default_time_limit_is_300_seconds(self) -> None:
        command = TaskCommand(CommandKind.TESTS, "python -m pytest")

        assert command.timeout_seconds == DEFAULT_COMMAND_TIMEOUT_SECONDS

    @pytest.mark.parametrize("seconds", [1, 120, 600])
    def test_a_time_limit_from_1_to_600_is_valid(self, seconds: int) -> None:
        assert TaskCommand(CommandKind.LINT, "ruff check .", seconds).timeout_seconds == seconds

    @pytest.mark.parametrize("seconds", [0, -1, 601, True, False, 1.5, "300", None])
    def test_any_other_time_limit_is_rejected(self, seconds: object) -> None:
        with pytest.raises(ValueError) as caught:
            TaskCommand(CommandKind.TESTS, "x", seconds)  # type: ignore[arg-type]

        assert "tiempo" in str(caught.value)

    @pytest.mark.parametrize(
        "text",
        ["", "   ", " x", "x ", "a\nb", "a\tb", "a\x00b", "a\x7fb", "x" * (MAX_FIELD_CHARS + 1), 3],
    )
    def test_the_text_must_be_one_trimmed_line_within_the_limit(self, text: object) -> None:
        with pytest.raises(ValueError) as caught:
            TaskCommand(CommandKind.TESTS, text)  # type: ignore[arg-type]

        assert SENTINEL not in str(caught.value)

    def test_the_message_never_reproduces_the_text(self) -> None:
        with pytest.raises(ValueError) as caught:
            TaskCommand(CommandKind.TESTS, f" {SENTINEL} ")

        assert SENTINEL not in str(caught.value)

    def test_the_kind_must_be_a_command_kind(self) -> None:
        with pytest.raises(ValueError):
            TaskCommand("pruebas", "x")  # type: ignore[arg-type]

    def test_a_text_at_the_limit_is_valid(self) -> None:
        text = "x" * MAX_FIELD_CHARS

        assert TaskCommand(CommandKind.TESTS, text).command == text

    def test_it_is_immutable(self) -> None:
        command = TaskCommand(CommandKind.TESTS, "x")

        with pytest.raises(AttributeError):
            command.command = "y"  # type: ignore[misc]


# --- TaskDefinition ----------------------------------------------------------------------------


class TestTaskDefinition:
    def test_without_commands_it_is_the_task_of_hu_11_01(self) -> None:
        task = TaskDefinition(None, "o", "", "", (CriterionDefinition("c"),))

        assert task.commands == ()

    def test_it_keeps_one_command_of_each_kind_in_order(self) -> None:
        lint = TaskCommand(CommandKind.LINT, "ruff check .")
        tests = TaskCommand(CommandKind.TESTS, "pytest")

        task = TaskDefinition(None, "o", "", "", (CriterionDefinition("c"),), (lint, tests))

        assert task.commands == (lint, tests)

    def test_two_commands_of_the_same_kind_are_rejected(self) -> None:
        first = TaskCommand(CommandKind.TESTS, "pytest")
        second = TaskCommand(CommandKind.TESTS, "pytest -q")

        with pytest.raises(ValueError):
            TaskDefinition(None, "o", "", "", (CriterionDefinition("c"),), (first, second))

    @pytest.mark.parametrize("commands", [["x"], ("x",), [TaskCommand(CommandKind.TESTS, "x")]])
    def test_the_commands_must_be_a_tuple_of_task_commands(self, commands: object) -> None:
        with pytest.raises(ValueError):
            TaskDefinition(None, "o", "", "", (CriterionDefinition("c"),), commands)  # type: ignore[arg-type]

    def test_with_title_keeps_the_commands(self) -> None:
        command = TaskCommand(CommandKind.TESTS, "pytest")
        task = TaskDefinition(None, "o", "", "", (CriterionDefinition("c"),), (command,))

        assert task.with_title("T").commands == (command,)


# --- parse_task: the section --------------------------------------------------------------------


class TestTheSection:
    def test_a_task_without_the_section_has_no_commands(self) -> None:
        assert parse_task(BASE).commands == ()

    def test_both_commands_with_and_without_time_limit(self) -> None:
        task = parse_task(
            with_commands(
                "- pruebas: python -m pytest -q\n  - tiempo: 120\n- lint: python -m ruff check .\n"
            )
        )

        assert task.commands == (
            TaskCommand(CommandKind.TESTS, "python -m pytest -q", 120),
            TaskCommand(CommandKind.LINT, "python -m ruff check .", 300),
        )

    def test_the_order_of_the_file_is_kept(self) -> None:
        task = parse_task(with_commands("- lint: ruff check .\n- pruebas: pytest\n"))

        assert [command.kind for command in task.commands] == [CommandKind.LINT, CommandKind.TESTS]

    def test_only_one_command_is_enough(self) -> None:
        task = parse_task(with_commands("- lint: ruff check .\n"))

        assert task.commands == (TaskCommand(CommandKind.LINT, "ruff check ."),)

    @pytest.mark.parametrize(
        "section",
        [
            "* pruebas:   pytest -q   \n",
            "- PRUEBAS: pytest -q\n",
            "- pruebas : pytest -q\n",
            "\n- pruebas: pytest -q\n\n",
            "- pruebas: pytest -q\n\ttiempo: 300\n",
            "- pruebas: pytest -q\n  * Tiempo :  300 \n",
            "- pruebas: pytest -q\n  - tiempo: 0300\n",
        ],
    )
    def test_the_accepted_forms(self, section: str) -> None:
        (command,) = parse_task(with_commands(section)).commands

        assert command == TaskCommand(CommandKind.TESTS, "pytest -q", 300)

    @pytest.mark.parametrize("name", ["## Comandos", "##   comandos  ", "## COMANDOS"])
    def test_the_name_of_the_section_ignores_case_and_spaces(self, name: str) -> None:
        task = parse_task(BASE + f"\n{name}\n- pruebas: pytest\n")

        assert len(task.commands) == 1

    def test_the_section_may_go_anywhere(self) -> None:
        text = "## Comandos\n- pruebas: pytest\n\n" + BASE

        assert parse_task(text).commands == (TaskCommand(CommandKind.TESTS, "pytest"),)

    def test_the_commands_inside_the_text_keep_inner_spaces_and_symbols(self) -> None:
        task = parse_task(with_commands('- pruebas: python -m pytest  -k "a and b" | x\n'))

        assert task.commands[0].command == 'python -m pytest  -k "a and b" | x'

    def test_the_criteria_commands_are_not_task_commands(self) -> None:
        assert parse_task(BASE).criteria[0].command == "python -m pytest"
        assert parse_task(BASE).commands == ()

    def test_a_repeated_section_is_rejected(self) -> None:
        text = with_commands("- pruebas: a\n") + "\n## Comandos\n- lint: b\n"

        assert code_of(text) == "seccion_repetida"

    def test_a_too_long_command_is_rejected_as_a_too_long_text(self) -> None:
        text = with_commands("- pruebas: " + "x" * (MAX_FIELD_CHARS + 1) + "\n")

        assert code_of(text) == "texto_demasiado_largo"


class TestTheRejectedSections:
    @pytest.mark.parametrize(
        "section",
        [
            "",
            "\n\n",
            f"- otro: {SENTINEL}\n",
            f"- pruebas:\n- lint: {SENTINEL}\n",
            "- pruebas:    \n",
            f"- pruebas: {SENTINEL}\n- pruebas: b\n",
            f"pruebas: {SENTINEL}\n",
            f"texto suelto {SENTINEL}\n",
            "  - tiempo: 300\n- pruebas: a\n",
            "- pruebas: a\n  - tiempo: 300\n  - tiempo: 200\n",
            "- pruebas: a\n  - tiempo:\n",
            f"- pruebas: a\n  - tiempo: {SENTINEL}\n",
            "- pruebas: a\n  - tiempo: 0\n",
            "- pruebas: a\n  - tiempo: 601\n",
            "- pruebas: a\n  - tiempo: -5\n",
            "- pruebas: a\n  - tiempo: +5\n",
            "- pruebas: a\n  - tiempo: 1.5\n",
            "- pruebas: a\n  - tiempo: 5 s\n",
            "- pruebas: a\n  - tiempo: ٣٠٠\n",
            "- pruebas: a\n  - tiempo: " + "0" * 5000 + "1\n",
            f"- pruebas: a\n  - espera: {SENTINEL}\n",
            "- pruebas: a\n  - comando: b\n",
            "-pruebas: a\n",
        ],
    )
    def test_it_is_rejected_with_a_fixed_message(self, section: str) -> None:
        assert code_of(with_commands(section)) == "comando_no_valido"

    def test_the_message_says_how_to_write_the_section(self) -> None:
        with pytest.raises(TaskFormatError) as caught:
            parse_task(with_commands("- otro: x\n"))

        message = str(caught.value)
        assert "Comandos" in message and "pruebas" in message and "lint" in message
        assert "600" in message

    def test_the_unknown_section_message_names_the_new_section(self) -> None:
        with pytest.raises(TaskFormatError) as caught:
            parse_task(BASE + "\n## Extras\nx\n")

        assert caught.value.code == "seccion_desconocida"
        assert "Comandos" in str(caught.value)


# --- commands_notice -----------------------------------------------------------------------------


class TestCommandsNotice:
    def test_without_commands_there_is_no_notice(self) -> None:
        assert commands_notice(()) is None

    def test_it_lists_each_exact_command_with_its_time_limit(self) -> None:
        notice = commands_notice(
            (
                TaskCommand(CommandKind.TESTS, "python -m pytest -q", 120),
                TaskCommand(CommandKind.LINT, "ruff check ."),
            )
        )

        assert notice is not None
        assert "- pruebas: `python -m pytest -q` (tiempo máximo: 120 s)" in notice
        assert "- lint: `ruff check .` (tiempo máximo: 300 s)" in notice
        assert "exact" in notice
        assert "aprobación" in notice

    def test_the_notice_is_the_same_for_the_same_commands(self) -> None:
        commands = (TaskCommand(CommandKind.TESTS, "pytest"),)

        assert commands_notice(commands) == commands_notice(list(commands))


# --- Public API ----------------------------------------------------------------------------------


def test_the_new_names_are_exported_by_the_core() -> None:
    for name in (
        "CommandKind",
        "TaskCommand",
        "commands_notice",
        "DEFAULT_COMMAND_TIMEOUT_SECONDS",
        "MAX_COMMAND_TIMEOUT_SECONDS",
    ):
        assert name in core.__all__, name
        assert hasattr(core, name), name
