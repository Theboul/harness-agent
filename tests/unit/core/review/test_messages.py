"""The commit message and the notices that go back to the agent (HU-11-05)."""

from __future__ import annotations

from harness_agent.core import (
    MAX_REJECTION_CHARS,
    commit_message,
    criterion_rejection_notice,
    rejection_notice,
)

CREDENTIAL = (
    "https://" + "usuario-de-prueba" + ":" + "secreto-de-prueba" + "@servidor.example/r.git"
)


def test_commit_message_uses_ticket_and_objective_in_one_line() -> None:
    assert commit_message("TAREA-14", "Validar el\ncorreo") == "TAREA-14: Validar el correo"


def test_commit_message_without_ticket_is_the_objective() -> None:
    assert commit_message(None, "Validar el correo") == "Validar el correo"


def test_commit_message_is_bounded() -> None:
    assert len(commit_message("T", "x" * 1000)) <= 200


def test_rejection_notice_carries_the_cleaned_reason() -> None:
    notice = rejection_notice('falta el caso "vacío"\nde nuevo')

    assert notice.startswith("[review_rejected] ")
    assert "Reason: 'falta el caso ’vacío’ de nuevo'" in notice


def test_rejection_notice_without_reason_has_no_reason_part() -> None:
    assert "Reason" not in rejection_notice(None)
    assert "Reason" not in rejection_notice("   \x1b  ")


def test_credentials_in_the_reason_are_hidden_and_the_notice_is_bounded() -> None:
    notice = rejection_notice(f"mira {CREDENTIAL} " + "y" * 5000)

    assert "secreto-de-prueba" not in notice and len(notice) <= MAX_REJECTION_CHARS


def test_criterion_rejection_names_the_criterion() -> None:
    notice = criterion_rejection_notice(3, "El mensaje es claro", "no lo es")

    assert notice.startswith("[criterion_rejected] Criterion 3")
    assert "El mensaje es claro" in notice and "Reason: 'no lo es'" in notice
