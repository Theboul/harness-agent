"""build_draft: title and description of the Pull Request (HU-11-06)."""

from __future__ import annotations

from harness_agent.core import (
    ApprovedChange,
    ChangeSet,
    ChangeStatus,
    FileChange,
    TaskCriteriaItem,
)
from harness_agent.core.pullrequest import (
    MAX_BODY_CHARS,
    MAX_FILES,
    MAX_TITLE_CHARS,
    build_draft,
)

SENTINEL = "VALOR-DE-PRUEBA-123"


def approved(
    *,
    ticket: str | None = "TAREA-14: Validar el correo",
    objective: str = "Validar el correo",
    files: tuple[FileChange, ...] = (FileChange("auth.py", ChangeStatus.NEW, 5, 0),),
    criteria: tuple[TaskCriteriaItem, ...] = (),
) -> ApprovedChange:
    return ApprovedChange(ticket, objective, "abc1234", ChangeSet(files, "diff"), criteria)


def test_title_is_the_ticket_in_one_line() -> None:
    draft = build_draft(approved(ticket="TAREA-1:\n  Validar\tcorreo"), "feature/x")
    assert draft.title == "TAREA-1: Validar correo"
    assert draft.branch == "feature/x"


def test_title_falls_back_to_the_objective_and_then_to_a_fixed_text() -> None:
    assert build_draft(approved(ticket=None), "b").title == "Validar el correo"
    assert build_draft(approved(ticket=" ", objective=""), "b").title == "Cambios de la tarea"


def test_title_is_bounded() -> None:
    assert len(build_draft(approved(ticket="x" * 500), "b").title) == MAX_TITLE_CHARS


def test_body_has_summary_with_real_numbers() -> None:
    files = (
        FileChange("auth.py", ChangeStatus.NEW, 5, 0),
        FileChange("old.py", ChangeStatus.DELETED, 0, 7),
        FileChange("logo.png", ChangeStatus.MODIFIED, None, None),
    )
    body = build_draft(approved(files=files), "b").body
    assert "## Objetivo\nValidar el correo" in body
    assert "abc1234" in body
    assert "3 archivos" in body and "+5" in body and "−7" in body
    assert "- `auth.py` (nuevo, +5 −0)" in body
    assert "- `old.py` (eliminado, +0 −7)" in body
    assert "- `logo.png` (modificado)" in body


def test_long_file_list_is_summarised() -> None:
    files = tuple(FileChange(f"f{n}.py", ChangeStatus.NEW, 1, 0) for n in range(MAX_FILES + 3))
    body = build_draft(approved(files=files), "b").body
    assert f"f{MAX_FILES - 1}.py" in body and f"f{MAX_FILES}.py" not in body
    assert "y 3 más" in body


def test_criteria_list_states_and_evidence_without_commands() -> None:
    criteria = (
        TaskCriteriaItem(
            "c1", "La clave mide 8", True, "Código de salida: 0\n24 passed", "pytest -q"
        ),
        TaskCriteriaItem("c2", "El mensaje es claro", True, "confirmado por la persona", None),
        TaskCriteriaItem("c3", "Falta esto", False, None, "make x"),
    )
    body = build_draft(approved(criteria=criteria), "b").body
    assert "- [x] La clave mide 8 — verificado. Evidencia: `Código de salida: 0 24 passed`" in body
    assert "- [x] El mensaje es claro — confirmado por la persona" in body
    assert "- [ ] Falta esto — pendiente" in body
    assert "pytest" not in body and "make x" not in body


def test_evidence_is_bounded_and_cannot_break_the_markdown() -> None:
    criteria = (TaskCriteriaItem("c1", "ok", True, "a`b" + "z" * 400, "cmd"),)
    body = build_draft(approved(criteria=criteria), "b").body
    line = next(x for x in body.splitlines() if "Evidencia" in x)
    evidence = line.split("`", 1)[1].rsplit("`", 1)[0]
    assert "`" not in evidence and len(evidence) <= 160


def test_url_credentials_are_hidden_everywhere() -> None:
    url = f"https://user:{SENTINEL}@example.com/x"
    criteria = (TaskCriteriaItem("c1", f"Sube a {url}", True, f"clonado {url}", "cmd"),)
    draft = build_draft(approved(ticket=f"T {url}", objective=url, criteria=criteria), "b")
    assert SENTINEL not in draft.title + draft.body


def test_body_is_bounded() -> None:
    criteria = tuple(
        TaskCriteriaItem(f"c{n}", "d" * 120, True, "e" * 300, "cmd") for n in range(200)
    )
    assert len(build_draft(approved(criteria=criteria), "b").body) <= MAX_BODY_CHARS


def test_a_huge_body_is_cut_with_a_mark() -> None:
    files = tuple(FileChange("d/" * 55 + f"{n}.py", ChangeStatus.NEW, 1, 0) for n in range(50))
    criteria = tuple(
        TaskCriteriaItem(f"c{n}", "d" * 120, True, "e" * 300, "cmd") for n in range(50)
    )
    body = build_draft(approved(files=files, criteria=criteria), "b").body
    assert len(body) <= MAX_BODY_CHARS
