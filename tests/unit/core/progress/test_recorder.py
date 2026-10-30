"""The recorder: what a checkpoint collects and how it fails (HU-11-08.1)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harness_agent.core import (
    Message,
    ProgressRecorder,
    Role,
    TaskCriteria,
    TaskCriteriaItem,
)

MOMENT = datetime(2026, 10, 30, 9, 30, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"
NAME = "progreso-TAREA-14.md"
WARNING = "No se pudo escribir el archivo de progreso; se conserva el último punto de control."


class Sink:
    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.fail: BaseException | None = None

    def write(self, name: str, text: str) -> None:
        if self.fail is not None:
            raise self.fail
        self.files[name] = text

    def read(self, name: str) -> str | None:
        return self.files.get(name)


class Criteria(TaskCriteria):
    def __init__(self, items: list[TaskCriteriaItem]) -> None:
        self.items = items
        self.fail: BaseException | None = None

    def load_criteria(self, session_id: str) -> list[TaskCriteriaItem]:
        if self.fail is not None:
            raise self.fail
        return list(self.items)

    def get_pending(self, session_id: str) -> list[TaskCriteriaItem]:
        return [item for item in self.items if not item.passes]

    def mark_passes(self, criteria_id: str, evidence: str) -> None:
        raise AssertionError("the recorder never marks passes")

    def export_readonly_copy(self, session_id: str, destination: Path) -> None:
        raise AssertionError("the recorder never exports")


ITEMS = [
    TaskCriteriaItem("c1", "El correo se valida", True, f"salida {SENTINEL}", f"pytest {SENTINEL}"),
    TaskCriteriaItem("c2", "La clave mide 8", False, None, "pytest -k clave"),
    TaskCriteriaItem("c3", "El mensaje es claro", False, None, None),
]


def build(
    sink: Sink | None = None, criteria: Criteria | None = None
) -> tuple[ProgressRecorder, Sink, list[str]]:
    sink = sink or Sink()
    warnings: list[str] = []
    recorder = ProgressRecorder(
        sink,
        criteria or Criteria(list(ITEMS)),
        ticket="TAREA-14: Validar",
        objective="Validar el correo",
        session_id="s1",
        clock=lambda: MOMENT,
        warn=warnings.append,
    )
    return recorder, sink, warnings


def history(*texts: str) -> list[Message]:
    return [Message(Role.SYSTEM, "prefijo")] + [Message(Role.ASSISTANT, text) for text in texts]


class TestCheckpoint:
    def test_each_checkpoint_counts_one_more_turn_and_rewrites_the_whole_file(self) -> None:
        recorder, sink, _ = build()
        recorder.checkpoint(history("hecho"))
        assert "tras el turno 1" in sink.files[NAME]
        recorder.checkpoint(history("hecho"))
        assert "tras el turno 2" in sink.files[NAME]

    def test_it_lists_the_state_of_every_criterion_and_the_last_answer(self) -> None:
        recorder, sink, _ = build()
        recorder.checkpoint(history("primero", "", "último"))
        text = sink.files[NAME]
        assert "- Criterio 1: El correo se valida (cumplido)" in text
        assert "- Criterio 2: La clave mide 8 (pendiente)" in text
        assert "- Criterio 3: El mensaje es claro (pendiente de validación humana)" in text
        assert text.endswith("## Nota\núltimo\n")

    def test_commands_and_evidence_never_reach_the_file(self) -> None:
        recorder, sink, _ = build()
        recorder.checkpoint(history("x"))
        assert SENTINEL not in sink.files[NAME]
        assert "pytest" not in sink.files[NAME]

    def test_external_and_user_messages_are_not_taken_as_the_note(self) -> None:
        recorder, sink, _ = build()
        messages = [
            Message(Role.ASSISTANT, "del agente"),
            Message(Role.USER, "de la persona"),
            Message(Role.TOOL, "de una herramienta"),
            Message(Role.ASSISTANT, "externo", is_external=True),
        ]
        recorder.checkpoint(messages)
        assert sink.files[NAME].endswith("## Nota\ndel agente\n")

    def test_without_an_answer_there_is_no_note(self) -> None:
        recorder, sink, _ = build()
        recorder.checkpoint([Message(Role.SYSTEM, "prefijo")])
        assert sink.files[NAME].endswith("## Nota\nSin nota.\n")


class TestFinish:
    def test_the_final_write_creates_the_file_even_with_no_turns(self) -> None:
        recorder, sink, _ = build()
        recorder.finish(history())
        assert "final de la sesión tras 0 turnos" in sink.files[NAME]

    def test_the_final_write_keeps_the_turn_count(self) -> None:
        recorder, sink, _ = build()
        recorder.checkpoint(history("a"))
        recorder.checkpoint(history("a"))
        recorder.finish(history("a"))
        assert "final de la sesión tras 2 turnos" in sink.files[NAME]


class TestFailures:
    def test_a_failing_destination_is_one_fixed_warning_and_no_exception(self) -> None:
        sink = Sink()
        sink.fail = OSError(f"disco lleno {SENTINEL}")
        recorder, _, warnings = build(sink)
        recorder.checkpoint(history("a"))
        assert warnings == [WARNING]

    def test_a_failing_criteria_source_writes_nothing_and_warns(self) -> None:
        criteria = Criteria(list(ITEMS))
        criteria.fail = RuntimeError(SENTINEL)
        recorder, sink, warnings = build(criteria=criteria)
        recorder.checkpoint(history("a"))
        assert sink.files == {}
        assert warnings == [WARNING]

    def test_the_turn_still_counts_after_a_failure(self) -> None:
        sink = Sink()
        recorder, _, _ = build(sink)
        sink.fail = OSError("x")
        recorder.checkpoint(history("a"))
        sink.fail = None
        recorder.checkpoint(history("a"))
        assert "tras el turno 2" in sink.files[NAME]

    @pytest.mark.parametrize("error", [asyncio.CancelledError(), KeyboardInterrupt()])
    def test_cancellation_and_interrupts_are_never_swallowed(self, error: BaseException) -> None:
        sink = Sink()
        sink.fail = error
        recorder, _, _ = build(sink)
        with pytest.raises(type(error)):
            recorder.checkpoint(history("a"))
