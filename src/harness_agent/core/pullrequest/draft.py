"""The draft of the Pull Request: its title and description, from what was approved (HU-11-06).

Pure and total. The summary comes from the real change (rule 2 of HU-11-05), the criteria come from
the protected store and the evidence is the one the verifier kept, shortened to one line. The
verification commands are never part of it, and credentials in URLs are hidden everywhere.

Only the standard library and ``harness_agent.core`` are used here.
"""

from __future__ import annotations

from dataclasses import dataclass

from harness_agent.core.interfaces.system import TaskCriteriaItem
from harness_agent.core.redaction import hide_url_credentials
from harness_agent.core.review.approved import ApprovedChange
from harness_agent.core.review.changes import FileChange
from harness_agent.core.verification.feedback import one_line

MAX_TITLE_CHARS = 100
MAX_BODY_CHARS = 20_000
MAX_FILES = 50
MAX_CRITERIA = 50
MAX_EVIDENCE_CHARS = 160
MAX_DESCRIPTION_CHARS = 120
MAX_OBJECTIVE_CHARS = 300
DEFAULT_TITLE = "Cambios de la tarea"
BODY_CUT_MARK = "\n\n[descripción recortada]"
HUMAN_CONFIRMATION = "confirmado por la persona"


@dataclass(frozen=True)
class PullRequestDraft:
    """What would be sent to GitHub.

    Attributes:
        title: One line, at most ``MAX_TITLE_CHARS`` characters.
        body: Markdown, at most ``MAX_BODY_CHARS`` characters.
        branch: The branch the Pull Request comes from.
    """

    title: str
    body: str
    branch: str


def build_draft(approved: ApprovedChange, branch: str) -> PullRequestDraft:
    """The draft for ``approved``, coming from ``branch``."""
    title = (
        _text(approved.ticket or "", MAX_TITLE_CHARS)
        or _text(approved.objective, MAX_TITLE_CHARS)
        or DEFAULT_TITLE
    )
    sections = [
        "## Objetivo\n" + (_text(approved.objective, MAX_OBJECTIVE_CHARS) or title),
        _changes_section(approved),
        _criteria_section(approved.criteria),
    ]
    body = "\n\n".join(sections)
    if len(body) > MAX_BODY_CHARS:
        body = body[: MAX_BODY_CHARS - len(BODY_CUT_MARK)] + BODY_CUT_MARK
    return PullRequestDraft(title, body, branch)


def _text(value: str, limit: int) -> str:
    """``value`` in one line, with URL credentials hidden and no backticks."""
    return one_line(hide_url_credentials(value).replace("`", "'"), limit)


def _changes_section(approved: ApprovedChange) -> str:
    changes = approved.changes
    count = len(changes.files)
    noun = "archivo" if count == 1 else "archivos"
    lines = [
        "## Cambios",
        f"Commit `{_text(approved.commit_id, 40)}`: {count} {noun}, "
        f"+{changes.total_added} −{changes.total_removed}.",
        "",
    ]
    lines.extend(_file_line(change) for change in changes.files[:MAX_FILES])
    if count > MAX_FILES:
        lines.append(f"- … y {count - MAX_FILES} más")
    return "\n".join(lines)


def _file_line(change: FileChange) -> str:
    detail = change.status.value
    if change.added is not None and change.removed is not None:
        detail += f", +{change.added} −{change.removed}"
    return f"- `{_text(change.path, MAX_DESCRIPTION_CHARS)}` ({detail})"


def _criteria_section(criteria: tuple[TaskCriteriaItem, ...]) -> str:
    lines = ["## Criterios de aceptación"]
    lines.extend(_criterion_line(item) for item in criteria[:MAX_CRITERIA])
    if len(criteria) > MAX_CRITERIA:
        lines.append(f"- … y {len(criteria) - MAX_CRITERIA} más")
    if not criteria:
        lines.append("- (la tarea no declara criterios)")
    return "\n".join(lines)


def _criterion_line(item: TaskCriteriaItem) -> str:
    description = _text(item.description, MAX_DESCRIPTION_CHARS)
    if not item.passes:
        return f"- [ ] {description} — pendiente"
    if item.command is None:
        return f"- [x] {description} — {HUMAN_CONFIRMATION}"
    evidence = _text(item.evidence or "", MAX_EVIDENCE_CHARS)
    suffix = f". Evidencia: `{evidence}`" if evidence else ""
    return f"- [x] {description} — verificado{suffix}"
