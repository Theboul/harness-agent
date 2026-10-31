"""The text of the review: summary, diff, safety of the shown data and color (HU-11-05)."""

from __future__ import annotations

from harness_agent.cli import review_block
from harness_agent.cli.review_view import DIFF_PREVIEW_LINES, diff_lines
from harness_agent.cli.style import ESCAPE, Style
from harness_agent.core import (
    ChangeSet,
    ChangeStatus,
    FileChange,
    TaskCriteriaItem,
    build_view,
)

CREDENTIAL = (
    "https://" + "usuario-de-prueba" + ":" + "secreto-de-prueba" + "@servidor.example/r.git"
)
PATCH = "diff --git a/x b/x\n@@ -1 +1 @@\n-viejo\n+nuevo\n contexto\n"


def view(patch: str = PATCH, *, files: tuple[FileChange, ...] | None = None, truncated=False):  # type: ignore[no-untyped-def]
    changes = ChangeSet(
        files
        if files is not None
        else (
            FileChange("src/auth.py", ChangeStatus.NEW, 12, 0),
            FileChange("tests/test_auth.py", ChangeStatus.MODIFIED, 6, 3),
        ),
        patch,
        truncated,
    )
    items = [
        TaskCriteriaItem("c1", "El email es obligatorio", True, None, "pytest"),
        TaskCriteriaItem("c2", "El mensaje de error es claro", False, None, None),
    ]
    return build_view("TAREA-14", changes, items)


def test_the_block_has_summary_criteria_diff_and_options() -> None:
    text = "\n".join(review_block(view()))

    assert "== REVISIÓN DE CAMBIOS: TAREA-14 ==" in text
    assert "2 archivos, +18 -3" in text
    assert "nuevo" in text and "src/auth.py" in text and "+12 -0" in text
    assert "Criterios objetivos: 1 de 1 cumplidos" in text
    assert "[x] 1 El email es obligatorio (cumplido)" in text
    assert "[?] 2 El mensaje de error es claro (pendiente de validación humana)" in text
    assert "-- diff --" in text and "+nuevo" in text
    assert "[1] aprobar y hacer commit" in text and "[4 N] confirmar criterio N" in text
    assert "No se puede aprobar todavía: hay criterios semánticos sin confirmar" in text


def test_a_single_file_is_singular_and_a_binary_has_no_counts() -> None:
    files = (FileChange("logo.png", ChangeStatus.MODIFIED, None, None),)

    text = "\n".join(review_block(view(files=files)))

    assert "1 archivo, +0 -0" in text and "binario" in text and "logo.png" in text


def test_without_the_diff_the_preview_is_left_out() -> None:
    text = "\n".join(review_block(view(), with_diff=False))

    assert "-- diff --" not in text and "[1] aprobar" in text


def test_a_long_diff_shows_a_preview_and_how_much_is_missing() -> None:
    patch = "\n".join(f"+linea {i}" for i in range(DIFF_PREVIEW_LINES + 5))

    lines = review_block(view(patch))

    assert "+linea 199" in lines and "+linea 200" not in lines
    assert "... 5 líneas más: elige 2 para verlo completo" in lines
    assert len(diff_lines(patch)) == DIFF_PREVIEW_LINES + 5


def test_a_truncated_patch_says_so_and_blocks() -> None:
    text = "\n".join(review_block(view("+x", truncated=True)))

    assert "[el diff supera el límite de la revisión y se recortó]" in text
    assert "el diff es demasiado grande para revisarlo" in text


def test_nothing_from_the_repository_can_repaint_the_terminal() -> None:
    evil = f"{ESCAPE}[2J{ESCAPE}]0;titulo\x07"
    files = (FileChange(f"a{evil}\nb.py", ChangeStatus.NEW, 1, 0),)
    patch = f"+{evil} dentro\n+{CREDENTIAL}\n+\x00nulo\x1b"

    text = "\n".join(review_block(view(patch, files=files)))

    assert ESCAPE not in text and "\x07" not in text and "\x00" not in text
    assert "secreto-de-prueba" not in text
    assert "a[2J" in text  # the visible remains are harmless text


def test_long_lines_and_paths_are_bounded() -> None:
    files = (FileChange("p" * 500, ChangeStatus.NEW, 1, 0),)

    lines = review_block(view("+" + "y" * 5000, files=files))

    assert max(len(line) for line in lines) < 400


def test_color_only_wraps_the_plain_text() -> None:
    painted = review_block(view(), Style(enabled=True))
    plain = review_block(view())

    assert any(ESCAPE in line for line in painted)
    assert len(painted) == len(plain)


def test_diff_colors_follow_the_prefix() -> None:
    green, red = diff_lines("+a\n-b", Style(enabled=True))

    assert "32m" in green and "31m" in red
