"""Format of the progress file and the name derived from the ticket (HU-11-08.1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from harness_agent.core import (
    CheckpointKind,
    CriterionLine,
    CriterionState,
    ProgressSnapshot,
    progress_file_name,
    render_progress,
)

MOMENT = datetime(2026, 10, 30, 9, 30, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"
DONE = CriterionLine(1, "El correo se valida", CriterionState.DONE)
PENDING = CriterionLine(2, "La clave mide 8", CriterionState.PENDING)
HUMAN = CriterionLine(3, "El mensaje es claro", CriterionState.HUMAN)


def snapshot(
    *,
    turn: int = 6,
    kind: CheckpointKind = CheckpointKind.CHECKPOINT,
    objective: str = "Validar el correo",
    criteria: tuple[CriterionLine, ...] = (DONE, PENDING, HUMAN),
    note: str = "Terminé la validación.",
) -> ProgressSnapshot:
    return ProgressSnapshot(
        ticket="TAREA-14: Validar el correo",
        session_id="sesion-1",
        turn=turn,
        kind=kind,
        updated_at=MOMENT,
        objective=objective,
        criteria=criteria,
        note=note,
    )


class TestFormat:
    def test_the_fixed_format_of_a_checkpoint(self) -> None:
        assert render_progress(snapshot()) == (
            "# Progreso del ticket: TAREA-14: Validar el correo\n"
            "<!-- harness-progreso v1 -->\n"
            "- Sesión: sesion-1\n"
            "- Estado: punto de control tras el turno 6\n"
            "- Actualizado: 2026-10-30T09:30:00+00:00\n"
            "- Objetivo: Validar el correo\n"
            "\n"
            "## Hecho\n"
            "- Criterio 1: El correo se valida (cumplido)\n"
            "\n"
            "## Pendiente\n"
            "- Criterio 2: La clave mide 8 (pendiente)\n"
            "- Criterio 3: El mensaje es claro (pendiente de validación humana)\n"
            "\n"
            "## Criterios\n"
            "- 1 cumplido, 2 pendiente, 3 pendiente de validación humana\n"
            "\n"
            "## Nota\n"
            "Terminé la validación.\n"
        )

    def test_the_final_one_says_how_many_turns_it_had(self) -> None:
        text = render_progress(snapshot(kind=CheckpointKind.FINAL))
        assert "- Estado: final de la sesión tras 6 turnos\n" in text

    def test_empty_sections_say_so(self) -> None:
        text = render_progress(snapshot(criteria=(PENDING,), note=""))
        assert "## Hecho\n- Todavía no hay criterios cumplidos.\n" in text
        assert text.endswith("## Nota\nSin nota.\n")
        assert "## Pendiente\n- No queda nada pendiente.\n" in render_progress(
            snapshot(criteria=(DONE,))
        )

    def test_a_text_is_one_clean_bounded_line_with_hidden_url_credentials(self) -> None:
        dirty = f"uno\ndos\x00 ‮ https://usuario:{SENTINEL}@host/x " + "z" * 900
        text = render_progress(snapshot(note=dirty, objective=dirty))
        assert SENTINEL not in text
        assert "<secreto oculto>" in text
        note = text.split("## Nota\n")[1].rstrip("\n")
        assert "\n" not in note and "\x00" not in note and "‮" not in note
        assert len(note) <= 500 and note.endswith("…")
        assert "- Objetivo: uno dos" in text

    def test_a_hostile_description_cannot_open_a_section(self) -> None:
        hostile = CriterionLine(
            1, "x\n## Hecho\n- Criterio 9: falso (cumplido)", CriterionState.PENDING
        )
        text = render_progress(snapshot(criteria=(hostile,)))
        assert text.count("\n## Hecho\n") == 1
        assert "- Criterio 1: x ## Hecho - Criterio 9: falso (cumplido) (pendiente)" in text


class TestSnapshotValidation:
    def test_a_turn_below_zero_is_refused(self) -> None:
        with pytest.raises(ValueError):
            snapshot(turn=-1)

    def test_the_criteria_are_a_tuple_of_lines(self) -> None:
        with pytest.raises(ValueError):
            snapshot(criteria=[DONE])  # type: ignore[arg-type]


class TestFileName:
    @pytest.mark.parametrize(
        ("ticket", "expected"),
        [
            ("TAREA-14: Validar el correo", "progreso-TAREA-14.md"),
            ("TAREA-14", "progreso-TAREA-14.md"),
            ("  fix login  ", "progreso-fix-login.md"),
            ("../../etc/passwd", "progreso-etc-passwd.md"),
            ("CON: algo", "progreso-CON.md"),
            ("a" * 100, "progreso-" + "a" * 40 + ".md"),
        ],
    )
    def test_the_name_is_safe_and_comes_from_the_ticket(self, ticket: str, expected: str) -> None:
        assert progress_file_name(ticket, "sesion-1") == expected

    @pytest.mark.parametrize("ticket", [None, "", "   ", "***", ": solo descripción"])
    def test_without_a_usable_ticket_the_session_gives_the_name(self, ticket: str | None) -> None:
        assert progress_file_name(ticket, "ab/cd:1") == "progreso-ab-cd-1.md"
