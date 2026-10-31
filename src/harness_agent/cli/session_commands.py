"""Text of the session commands ``/sesiones``, ``/model``, ``/compactar`` and ``/nueva`` (HU-06-05).

Pure functions: they receive plain values (the composition root reads the stores and the
configuration) and return the text to print. Every value that comes from storage is cleaned to one
line and bounded, so a session saved with control characters cannot break the terminal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from harness_agent.core import CompactionResult

from .render import bounded, sanitize

MAX_SESSIONS_SHOWN = 10
MAX_GOAL_CHARS = 60
MAX_FIELD_CHARS = 40
NO_SESSIONS = "No hay sesiones guardadas."
NOTHING_COMPACTED = "No se compactó: no hay mensajes antiguos que resumir (o el resumen falló)."


@dataclass(frozen=True)
class SessionRow:
    """One saved session as ``/sesiones`` shows it."""

    id: str
    created_at: datetime
    status: str
    model: str | None
    goal: str | None
    current: bool


@dataclass(frozen=True)
class ModelView:
    """What ``/model`` shows: the model and the limits in force (no secrets)."""

    model: str
    window_tokens: int
    threshold_tokens: int
    max_turns: int
    max_seconds: int
    max_tokens: int
    max_output_tokens: int


def _one_line(text: str | None, limit: int) -> str:
    """``text`` on a single clean line of at most ``limit`` characters; ``-`` when empty."""
    cleaned = " ".join(sanitize(text or "").split())
    return bounded(cleaned, limit) if cleaned else "-"


def _number(value: int) -> str:
    """``1.234.567``: thousands separated with a dot, as in Spanish."""
    return f"{value:,}".replace(",", ".")


def _session_line(row: SessionRow) -> str:
    marker = "*" if row.current else " "
    stamp = row.created_at.strftime("%Y-%m-%d %H:%M")
    return (
        f"{marker} {_one_line(row.id, MAX_FIELD_CHARS)}  {stamp} UTC  "
        f"{_one_line(row.status, MAX_FIELD_CHARS)}  {_one_line(row.model, MAX_FIELD_CHARS)}  "
        f"{_one_line(row.goal, MAX_GOAL_CHARS)}"
    )


def format_sessions(rows: Sequence[SessionRow]) -> str:
    """The newest sessions first (at most ``MAX_SESSIONS_SHOWN``), the current one always listed."""
    if not rows:
        return NO_SESSIONS
    ordered = sorted(rows, key=lambda row: row.created_at, reverse=True)
    shown = ordered[:MAX_SESSIONS_SHOWN]
    current = [row for row in ordered[MAX_SESSIONS_SHOWN:] if row.current]
    shown = shown[: MAX_SESSIONS_SHOWN - len(current)] + current
    lines = ["Sesiones guardadas (la más reciente primero):"]
    lines.extend(_session_line(row) for row in shown)
    hidden = len(ordered) - len(shown)
    if hidden:
        lines.append(f"... y {hidden} más.")
    lines.append("Para continuar una: /reanudar <id>.")
    return "\n".join(lines)


def format_model(view: ModelView) -> str:
    """The model, the context window, the compaction threshold and the session limits."""
    return "\n".join(
        [
            f"Modelo: {_one_line(view.model, MAX_GOAL_CHARS)}",
            f"Ventana de contexto: {_number(view.window_tokens)} tokens",
            f"Compactación automática desde: {_number(view.threshold_tokens)} tokens",
            f"Límites de la sesión: {_number(view.max_turns)} turnos, "
            f"{_number(view.max_seconds)} s, {_number(view.max_tokens)} tokens",
            f"Máximo por respuesta del modelo: {_number(view.max_output_tokens)} tokens",
        ]
    )


def format_compaction(result: CompactionResult | None) -> str:
    """The estimates around a manual compaction, or the fixed line when nothing was compacted."""
    if result is None:
        return NOTHING_COMPACTED
    return (
        f"Contexto compactado: ~{_number(result.estimated_before)} → "
        f"~{_number(result.estimated_after)} tokens (historial original conservado)."
    )


def format_new_session(session_id: str) -> str:
    """The line printed after ``/nueva``."""
    return (
        f"Sesión nueva: {_one_line(session_id, MAX_FIELD_CHARS)}. "
        "La anterior sigue guardada; reanúdala con /reanudar <id>."
    )
