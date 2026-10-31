"""Text of the session commands: /sesiones, /model, /compactar and /nueva (HU-06-05 / T008)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from harness_agent.cli.session_commands import (
    MAX_GOAL_CHARS,
    MAX_SESSIONS_SHOWN,
    ModelView,
    SessionRow,
    format_compaction,
    format_model,
    format_new_session,
    format_sessions,
)
from harness_agent.core import CompactionResult

BASE = datetime(2026, 10, 30, 9, 15, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"


def row(
    number: int,
    *,
    current: bool = False,
    status: str = "completed",
    model: str | None = "gemini/flash",
    goal: str | None = "arreglar el login",
) -> SessionRow:
    return SessionRow(
        id=f"s-{number}",
        created_at=BASE + timedelta(hours=number),
        status=status,
        model=model,
        goal=goal,
        current=current,
    )


class TestSessions:
    def test_no_sessions_says_so(self) -> None:
        assert format_sessions([]) == "No hay sesiones guardadas."

    def test_the_newest_goes_first_and_the_current_is_marked(self) -> None:
        text = format_sessions([row(1), row(3, current=True), row(2)])

        lines = text.splitlines()
        assert lines[0] == "Sesiones guardadas (la más reciente primero):"
        assert lines[1] == "* s-3  2026-10-30 12:15 UTC  completed  gemini/flash  arreglar el login"
        assert lines[2].startswith("  s-2  ")
        assert lines[3].startswith("  s-1  ")
        assert lines[-1] == "Para continuar una: /reanudar <id>."

    def test_only_the_newest_ten_are_listed_and_the_rest_is_counted(self) -> None:
        rows = [row(number) for number in range(MAX_SESSIONS_SHOWN + 3)]

        lines = format_sessions(rows).splitlines()

        assert sum(line.lstrip("* ").startswith("s-") for line in lines) == MAX_SESSIONS_SHOWN
        assert "... y 3 más." in lines
        assert lines[1].lstrip("* ").startswith(f"s-{MAX_SESSIONS_SHOWN + 2}")

    def test_the_current_session_is_always_shown_even_when_it_is_old(self) -> None:
        rows = [row(0, current=True)] + [row(number) for number in range(1, 15)]

        text = format_sessions(rows)

        assert "* s-0  " in text
        assert "... y 5 más." in text

    def test_missing_model_and_goal_are_shown_as_a_dash(self) -> None:
        text = format_sessions([row(1, model=None, goal=None)])

        assert "  completed  -  -" in text

    def test_the_goal_is_one_clean_bounded_line(self) -> None:
        goal = "linea uno\nlinea\x1b[31m dos " + "x" * 200

        text = format_sessions([row(1, goal=goal)])

        line = text.splitlines()[1]
        assert "\x1b" not in line
        assert "linea uno linea[31m dos" in line
        assert line.endswith("...")
        assert len(line.partition("gemini/flash  ")[2]) <= MAX_GOAL_CHARS

    def test_model_and_status_are_cleaned_too(self) -> None:
        text = format_sessions([row(1, status="act\nive", model="m\x07odel")])

        assert text.count("\n") == format_sessions([row(1)]).count("\n")
        assert "act ive  model" in text


class TestModel:
    def view(self) -> ModelView:
        return ModelView(
            model="gemini/flash",
            window_tokens=1_000_000,
            threshold_tokens=800_000,
            max_turns=25,
            max_seconds=900,
            max_tokens=200_000,
            max_output_tokens=4096,
        )

    def test_it_shows_model_window_threshold_and_limits(self) -> None:
        assert format_model(self.view()).splitlines() == [
            "Modelo: gemini/flash",
            "Ventana de contexto: 1.000.000 tokens",
            "Compactación automática desde: 800.000 tokens",
            "Límites de la sesión: 25 turnos, 900 s, 200.000 tokens",
            "Máximo por respuesta del modelo: 4.096 tokens",
        ]

    def test_the_model_name_is_cleaned(self) -> None:
        view = ModelView("a\nb\x1b[0m", 1, 1, 1, 1, 1, 1)

        assert format_model(view).splitlines()[0] == "Modelo: a b[0m"


class TestCompaction:
    def test_it_reports_the_estimates(self) -> None:
        result = CompactionResult(
            desde=1, hasta=9, eventos=8, estimated_before=12_000, estimated_after=3_400
        )

        assert format_compaction(result) == (
            "Contexto compactado: ~12.000 → ~3.400 tokens (historial original conservado)."
        )

    def test_nothing_to_summarize_or_a_failure_is_one_line(self) -> None:
        assert format_compaction(None) == (
            "No se compactó: no hay mensajes antiguos que resumir (o el resumen falló)."
        )


class TestNewSession:
    def test_it_names_the_new_session_and_how_to_go_back(self) -> None:
        assert format_new_session("s-9") == (
            "Sesión nueva: s-9. La anterior sigue guardada; reanúdala con /reanudar <id>."
        )

    def test_the_identifier_is_cleaned(self) -> None:
        assert "\x1b" not in format_new_session("s\x1b[1m-9")
