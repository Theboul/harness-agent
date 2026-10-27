"""The state of each criterion in the terminal: lines, board and final line (HU-11-04.1 / AC-04)."""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.cli import CriteriaBoard, criterion_line

ESC = chr(27)
RLO = chr(0x202E)
ZWSP = chr(0x200B)


def payload(
    n: int,
    status: str,
    description: str = "Algo",
    *,
    exit_code: int | None = None,
    program: str | None = None,
    total: int = 3,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "criterion": n,
        "total": total,
        "description": description,
        "status": status,
        "met": status == "cumplido",
        "exit_code": exit_code,
        "program": program,
        **extra,
    }


EMAIL = payload(1, "cumplido", "El email es obligatorio", exit_code=0, program="pytest")
PASSWORD = payload(
    2, "no_cumplido", "La contraseña tiene 8 caracteres", exit_code=1, program="pytest"
)
SEMANTIC = payload(3, "pendiente_humano", "El mensaje de error es claro")
FIXED = payload(2, "cumplido", "La contraseña tiene 8 caracteres", exit_code=0, program="pytest")


@pytest.mark.parametrize(
    ("event", "line"),
    [
        (EMAIL, "[x] 1 El email es obligatorio (pytest: salida 0)"),
        (PASSWORD, "[ ] 2 La contraseña tiene 8 caracteres (pytest: salida 1)"),
        (SEMANTIC, "[?] 3 El mensaje de error es claro (pendiente de validación humana)"),
        (
            payload(4, "regresion", "El correo se normaliza", exit_code=2, program="pytest"),
            "[ ] 4 El correo se normaliza (regresión; pytest: salida 2)",
        ),
        (
            payload(2, "tiempo_agotado", "Compila", program="pytest"),
            "[ ] 2 Compila (pytest: tiempo agotado)",
        ),
        (
            payload(5, "no_ejecutado", "Compila sin avisos"),
            "[ ] 5 Compila sin avisos (no ejecutado)",
        ),
        (
            payload(5, "alterado", "Compila sin avisos"),
            "[ ] 5 Compila sin avisos (criterio alterado: no se ejecutó)",
        ),
        (payload(1, "cumplido", "Algo", exit_code=0), "[x] 1 Algo (salida 0)"),
    ],
)
def test_the_lines_of_the_contract(event: dict[str, Any], line: str) -> None:
    assert criterion_line(event) == line


@pytest.mark.parametrize(
    "event",
    [
        {},
        {"criterion": "uno", "status": 5, "description": None},
        {"status": "algo desconocido"},
        {"criterion": True, "status": "cumplido", "exit_code": "0"},
    ],
)
def test_a_payload_with_missing_or_odd_fields_gives_the_neutral_line(event: dict[str, Any]) -> None:
    assert criterion_line(event) == "[ ] ? (no ejecutado)"


def test_a_met_criterion_without_an_exit_code_is_not_shown_as_met() -> None:
    assert criterion_line({"criterion": 1, "status": "cumplido"}) == "[ ] 1 (no ejecutado)"


def test_the_description_loses_control_and_format_characters_and_is_bounded() -> None:
    event = payload(1, "no_cumplido", "uno" + ESC + "[31m" + RLO + ZWSP + "\ndos", exit_code=1)
    assert criterion_line(event) == "[ ] 1 uno[31m dos (salida 1)"
    long = payload(1, "no_cumplido", "y" * 200, exit_code=1)
    shown = criterion_line(long)
    assert shown == "[ ] 1 " + "y" * 77 + "... (salida 1)"


def test_the_arguments_of_the_command_are_never_shown() -> None:
    event = payload(
        1,
        "no_cumplido",
        "Algo",
        exit_code=1,
        program="pytest --token VALOR-DE-PRUEBA-123",
        command="pytest --token VALOR-DE-PRUEBA-123",
        output="VALOR-DE-PRUEBA-123",
    )
    shown = criterion_line(event)
    assert "VALOR-DE-PRUEBA-123" not in shown
    assert shown == "[ ] 1 Algo (salida 1)"


class TestBoard:
    def test_an_empty_board_has_nothing_to_report(self) -> None:
        board = CriteriaBoard()
        assert board.lines() == []
        assert board.report() == "Todavía no se ha verificado ningún criterio."

    def test_the_prototype_of_the_sheet(self) -> None:
        board = CriteriaBoard()
        for event in (EMAIL, PASSWORD, SEMANTIC):
            board.update(event)

        assert board.lines() == [
            "[x] 1 El email es obligatorio (pytest: salida 0)",
            "[ ] 2 La contraseña tiene 8 caracteres (pytest: salida 1)",
            "[?] 3 El mensaje de error es claro (pendiente de validación humana)",
        ]
        assert board.summary_line() == "Tarea: no terminada (1 de 2 criterios objetivos cumplidos)"
        assert board.report() == "\n".join(board.lines() + [board.summary_line()])

    def test_the_last_state_of_each_criterion_wins(self) -> None:
        board = CriteriaBoard()
        for event in (EMAIL, PASSWORD, SEMANTIC, EMAIL, FIXED, SEMANTIC):
            board.update(event)

        assert board.lines()[1] == "[x] 2 La contraseña tiene 8 caracteres (pytest: salida 0)"
        assert board.summary_line() == (
            "Tarea: pendiente de validación humana (2 de 2 criterios objetivos cumplidos)"
        )

    def test_without_semantic_criteria_and_all_met_the_task_is_verified(self) -> None:
        board = CriteriaBoard()
        board.update(payload(1, "cumplido", exit_code=0, total=2))
        board.update(payload(2, "cumplido", exit_code=0, total=2))

        assert board.summary_line() == "Tarea: verificada (2 de 2 criterios objetivos cumplidos)"

    @pytest.mark.parametrize("status", ["regresion", "no_ejecutado", "alterado", "tiempo_agotado"])
    def test_anything_that_is_not_met_leaves_the_task_unfinished(self, status: str) -> None:
        board = CriteriaBoard()
        board.update(payload(1, status, exit_code=1, total=1))

        assert board.summary_line().startswith("Tarea: no terminada (0 de 1 ")

    def test_a_payload_without_an_index_is_ignored_by_the_board(self) -> None:
        board = CriteriaBoard()
        board.update({"status": "cumplido"})
        board.update({"criterion": 0, "status": "cumplido"})
        board.update({"criterion": 10_000_000, "status": "cumplido"})

        assert board.lines() == []
