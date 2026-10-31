"""The text of the review of the diff: pure functions, no input or output (HU-11-05).

The block answers, from top to bottom: which task, what changed (files and counts, from the real
``git diff``), how the criteria stand, the diff itself and the options. Everything that comes from
the repository or the task (paths, descriptions, diff lines) is data to show: control characters
and escape sequences are removed, URL credentials are hidden, and every line is bounded, so a
file name or a line of the diff can never repaint or break the terminal. Color is only a help:
without it the text is the same. See ``specs/040-diff-review-approval/contracts/``.
"""

from __future__ import annotations

from harness_agent.core import (
    Blocker,
    ChangeStatus,
    FileChange,
    ReviewCriterionState,
    ReviewView,
    hide_url_credentials,
)

from .render import bounded, sanitize
from .style import PLAIN, Style

DIFF_PREVIEW_LINES = 200
MAX_LINE_CHARS = 300
MAX_PATH_CHARS = 120
MAX_TICKET_CHARS = 80
MAX_FILES_SHOWN = 100
STATUS_WIDTH = 10
OPTIONS = (
    " [1] aprobar y hacer commit   [2] ver diff completo   [3] rechazar con motivo",
    " [4 N] confirmar criterio N   [5 N] rechazar criterio N   (/salir: sin decidir)",
)
BLOCKER_TEXT = {
    Blocker.SEMANTIC_PENDING: "hay criterios semánticos sin confirmar (usa 4 N o 5 N)",
    Blocker.TRUNCATED: "el diff es demasiado grande para revisarlo",
    Blocker.NO_CHANGES: "no hay cambios",
}
_MARKS = {
    ReviewCriterionState.MET: "[x]",
    ReviewCriterionState.CONFIRMED_HUMAN: "[x]",
    ReviewCriterionState.PENDING: "[ ]",
    ReviewCriterionState.PENDING_HUMAN: "[?]",
}
_STATE_TEXT = {
    ReviewCriterionState.MET: "cumplido",
    ReviewCriterionState.CONFIRMED_HUMAN: "confirmado por la persona",
    ReviewCriterionState.PENDING: "pendiente",
    ReviewCriterionState.PENDING_HUMAN: "pendiente de validación humana",
}


def _text(value: str, limit: int) -> str:
    """One safe line: no controls (tabs and line breaks become spaces), credentials hidden."""
    flat = " ".join(sanitize(hide_url_credentials(value)).split())
    return bounded(flat, limit)


def _counts(change: FileChange) -> str:
    if change.added is None or change.removed is None:
        return "binario"
    return f"+{change.added} -{change.removed}"


def _file_line(change: FileChange) -> str:
    status = (change.status or ChangeStatus.OTHER).value.ljust(STATUS_WIDTH)
    return f"  {status} {_counts(change).ljust(10)} {_text(change.path, MAX_PATH_CHARS)}"


def summary_lines(view: ReviewView, style: Style = PLAIN) -> list[str]:
    """Title, files with counts, and the state of the criteria."""
    changes = view.changes
    ticket = _text(view.ticket, MAX_TICKET_CHARS)
    title = f"== REVISIÓN DE CAMBIOS{': ' + ticket if ticket else ''} =="
    count = len(changes.files)
    noun = "archivo" if count == 1 else "archivos"
    lines = [
        style.paint(title, "bold"),
        f"{count} {noun}, +{changes.total_added} -{changes.total_removed}",
    ]
    lines.extend(_file_line(change) for change in changes.files[:MAX_FILES_SHOWN])
    if count > MAX_FILES_SHOWN:
        lines.append(f"  ... y {count - MAX_FILES_SHOWN} archivos más")
    lines.append(f"Criterios objetivos: {view.objective_met} de {view.objective_total} cumplidos")
    for criterion in view.criteria:
        mark = _MARKS[criterion.state]
        text = _text(criterion.description, MAX_PATH_CHARS)
        detail = f"{mark} {criterion.index} {text} ({_STATE_TEXT[criterion.state]})"
        pending = criterion.state is ReviewCriterionState.PENDING_HUMAN
        lines.append(style.paint(detail, "yellow") if pending else detail)
    return lines


def diff_lines(patch: str, style: Style = PLAIN, limit: int | None = None) -> list[str]:
    """The lines of ``patch``, safe to print and painted; at most ``limit`` of them."""
    lines = patch.splitlines()
    shown = lines if limit is None else lines[:limit]
    return [_paint_diff(_text(line, MAX_LINE_CHARS), style) for line in shown]


def _paint_diff(line: str, style: Style) -> str:
    if line.startswith(("+++", "---", "diff ", "index ")):
        return style.paint(line, "bold")
    if line.startswith("@@"):
        return style.paint(line, "cyan")
    if line.startswith("+"):
        return style.paint(line, "green")
    if line.startswith("-"):
        return style.paint(line, "red")
    return line


def blocker_lines(view: ReviewView) -> list[str]:
    """Why approval is not possible yet, one line, or nothing."""
    if view.can_approve:
        return []
    reasons = "; ".join(BLOCKER_TEXT[blocker] for blocker in view.blockers)
    return [f"No se puede aprobar todavía: {reasons}."]


def review_block(view: ReviewView, style: Style = PLAIN, *, with_diff: bool = True) -> list[str]:
    """The whole screen: summary, diff preview (first ``DIFF_PREVIEW_LINES`` lines), options."""
    lines = summary_lines(view, style)
    if with_diff:
        patch = view.changes.patch.splitlines()
        lines.append(style.paint("-- diff --", "dim"))
        lines.extend(diff_lines(view.changes.patch, style, DIFF_PREVIEW_LINES))
        if len(patch) > DIFF_PREVIEW_LINES:
            more = len(patch) - DIFF_PREVIEW_LINES
            lines.append(f"... {more} líneas más: elige 2 para verlo completo")
        if view.changes.truncated:
            lines.append("[el diff supera el límite de la revisión y se recortó]")
    lines.extend(blocker_lines(view))
    lines.extend(OPTIONS)
    return lines
