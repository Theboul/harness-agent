"""The terminal shows the criteria after a verification and on request (HU-11-04.1 / AC-04)."""

from __future__ import annotations

import io
from typing import Any

from harness_agent.cli import attach_criteria_status, run_cli
from harness_agent.cli.app import HELP_TEXT
from harness_agent.core import Event, EventType, InMemoryEventBus

NOT_YET = "Todavía no se ha verificado ningún criterio."


def verified(n: int, status: str, total: int = 3, **fields: Any) -> Event:
    payload = {
        "criterion": n,
        "total": total,
        "description": f"Criterio {n}",
        "status": status,
        "met": status == "cumplido",
        "exit_code": 0 if status == "cumplido" else None,
        "program": "pytest" if status == "cumplido" else None,
        **fields,
    }
    return Event.create("sesion-1", EventType.CRITERION_VERIFIED, payload)


class SubscriptionSpy(InMemoryEventBus):
    def __init__(self) -> None:
        super().__init__()
        self.subscribed: list[EventType] = []

    def subscribe(self, event_type: EventType, handler: Any) -> None:
        self.subscribed.append(event_type)
        super().subscribe(event_type, handler)


def test_it_subscribes_only_to_the_verification_event() -> None:
    bus = SubscriptionSpy()

    attach_criteria_status(bus, io.StringIO())

    assert bus.subscribed == [EventType.CRITERION_VERIFIED]


def test_a_line_per_criterion_and_the_final_line_only_after_the_last() -> None:
    bus, output = InMemoryEventBus(), io.StringIO()
    attach_criteria_status(bus, output)

    bus.emit(verified(1, "cumplido"))
    bus.emit(verified(2, "no_cumplido", exit_code=1, program="pytest"))
    assert (
        output.getvalue()
        == "[x] 1 Criterio 1 (pytest: salida 0)\n[ ] 2 Criterio 2 (pytest: salida 1)\n"
    )
    bus.emit(verified(3, "pendiente_humano"))

    assert output.getvalue().splitlines()[-2:] == [
        "[?] 3 Criterio 3 (pendiente de validación humana)",
        "Tarea: no terminada (1 de 2 criterios objetivos cumplidos)",
    ]


def test_other_events_write_nothing() -> None:
    bus, output = InMemoryEventBus(), io.StringIO()
    attach_criteria_status(bus, output)

    for event_type in EventType:
        if event_type is not EventType.CRITERION_VERIFIED:
            bus.emit(Event.create("sesion-1", event_type, {"criterion": 1, "status": "cumplido"}))

    assert output.getvalue() == ""


async def drive(
    typed: str, commands: Any = None, bus: InMemoryEventBus | None = None
) -> tuple[int, str]:
    output = io.StringIO()

    async def turn(task: str) -> object:
        return None

    code = await run_cli(
        bus or InMemoryEventBus(),
        turn,
        input_stream=io.StringIO(typed),
        output=output,
        commands=commands,
    )
    return code, output.getvalue()


async def test_the_command_before_any_verification_says_so() -> None:
    bus = InMemoryEventBus()
    board = attach_criteria_status(bus, io.StringIO())
    commands = {"/criterios": ("Muestra el estado de los criterios.", board.report)}

    code, shown = await drive("/criterios\n/salir\n", commands, bus)

    assert code == 0 and NOT_YET in shown


async def test_the_command_repeats_the_last_state_without_running_anything() -> None:
    bus, silent = InMemoryEventBus(), io.StringIO()
    board = attach_criteria_status(bus, silent)
    for n, status in ((1, "cumplido"), (2, "pendiente_humano")):
        bus.emit(verified(n, status, total=2))
    commands = {"/criterios": ("Muestra el estado de los criterios.", board.report)}

    _, shown = await drive("/criterios\n/salir\n", commands, bus)

    assert "[x] 1 Criterio 1 (pytest: salida 0)" in shown
    assert "[?] 2 Criterio 2 (pendiente de validación humana)" in shown
    assert "Tarea: pendiente de validación humana (1 de 1 criterios objetivos cumplidos)" in shown


async def test_help_lists_the_extra_command_only_when_it_is_given() -> None:
    commands = {"/criterios": ("Muestra el estado de los criterios.", lambda: "x")}

    _, with_extra = await drive("/ayuda\n/salir\n", commands)
    _, without = await drive("/ayuda\n/salir\n")

    assert "  /criterios  Muestra el estado de los criterios.\n" in with_extra
    assert with_extra.index("/criterios") < with_extra.index("Cualquier otra línea")
    assert HELP_TEXT in without and "/criterios" not in without


async def test_without_the_extra_command_it_is_unknown_as_before() -> None:
    _, shown = await drive("/criterios\n/salir\n")

    assert "Comando desconocido: '/criterios'." in shown
