"""The fixed text format of the progress file and the name derived from the ticket (HU-11-08.1).

Every free text (ticket, objective, descriptions, the note of the agent) is cut to one clean line:
no control, format, surrogate or private-use characters, credentials of URLs hidden, bounded. So
no text can open a section of the file or smuggle a line that looks like one.
"""

from __future__ import annotations

import re
import unicodedata

from harness_agent.core.progress.snapshot import (
    CheckpointKind,
    CriterionState,
    ProgressSnapshot,
)
from harness_agent.core.redaction import hide_url_credentials

FORMAT_MARK = "<!-- harness-progreso v1 -->"
FILE_PREFIX = "progreso-"
FILE_SUFFIX = ".md"
MAX_LINE_CHARS = 500
MAX_TICKET_CHARS = 200
MAX_NAME_CHARS = 40
_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_DASHES = re.compile(r"-{2,}")
_EDGE_CHARS = "-._"


def one_line(text: str, limit: int = MAX_LINE_CHARS) -> str:
    """``text`` as a single clean line of at most ``limit`` characters (``…`` marks a cut)."""
    visible = "".join(
        " " if unicodedata.category(char).startswith("C") else char
        for char in hide_url_credentials(text)
    )
    line = " ".join(visible.split())
    if len(line) <= limit:
        return line
    return line[: limit - 1].rstrip() + "…"


def _slug(text: str) -> str:
    cleaned = _DASHES.sub("-", _UNSAFE_NAME.sub("-", text)).strip(_EDGE_CHARS)
    return cleaned[:MAX_NAME_CHARS].strip(_EDGE_CHARS)


def progress_file_name(ticket: str | None, session_id: str) -> str:
    """Name of the progress file: ``progreso-<ticket>.md``, always safe inside a folder.

    The ticket is the text of the title before its first ``:`` (``TAREA-14: Validar`` gives
    ``TAREA-14``) reduced to letters, digits, ``.``, ``_`` and ``-``. With no usable ticket the
    session identifier gives the name, so the same ticket always maps to the same file.
    """
    slug = _slug((ticket or "").split(":", 1)[0])
    if not slug:
        slug = _slug(session_id) or "sesion"
    return f"{FILE_PREFIX}{slug}{FILE_SUFFIX}"


def _turns(count: int) -> str:
    return f"{count} turno" if count == 1 else f"{count} turnos"


def render_progress(snapshot: ProgressSnapshot) -> str:
    """The progress file for ``snapshot``: header, done, pending, every criterion, and a note."""
    if snapshot.kind is CheckpointKind.FINAL:
        status = f"{snapshot.kind.value} tras {_turns(snapshot.turn)}"
    else:
        status = f"{snapshot.kind.value} tras el turno {snapshot.turn}"
    done = [line for line in snapshot.criteria if line.state is CriterionState.DONE]
    pending = [line for line in snapshot.criteria if line.state is not CriterionState.DONE]

    def item(position: int, description: str, state: CriterionState) -> str:
        return f"- Criterio {position}: {one_line(description)} ({state.value})"

    lines = [
        f"# Progreso del ticket: {one_line(snapshot.ticket, MAX_TICKET_CHARS)}",
        FORMAT_MARK,
        f"- Sesión: {one_line(snapshot.session_id, MAX_TICKET_CHARS)}",
        f"- Estado: {status}",
        f"- Actualizado: {snapshot.updated_at.isoformat()}",
        f"- Objetivo: {one_line(snapshot.objective)}",
        "",
        "## Hecho",
        *(
            [item(line.position, line.description, line.state) for line in done]
            or ["- Todavía no hay criterios cumplidos."]
        ),
        "",
        "## Pendiente",
        *(
            [item(line.position, line.description, line.state) for line in pending]
            or ["- No queda nada pendiente."]
        ),
        "",
        "## Criterios",
        "- " + ", ".join(f"{line.position} {line.state.value}" for line in snapshot.criteria),
        "",
        "## Nota",
        one_line(snapshot.note) or "Sin nota.",
    ]
    return "\n".join(lines) + "\n"
