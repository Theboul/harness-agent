"""AC-01 and AC-02 of HU-06-01 with the real agent loop of A (T008).

The loop (``core/loop.py``, not modified) is wired to the real ``InMemoryEventBus`` and a scripted
provider; the CLI is attached to the bus and writes in an in-memory stream. Nothing here touches
the network or the real console.
"""

from __future__ import annotations

import io

import pytest

from harness_agent.cli import attach_renderer, run_cli
from harness_agent.cli.app import EXIT_FAILURE, EXIT_OK, PROMPT
from harness_agent.core import EventDeliveryError, InMemoryEventBus
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.interfaces.security import PermissionDecision
from tests.core.support import SESSION, Rig, call, make_rig, response
from tests.doubles import FailingTool, InMemoryToolRegistry, RaisingTool, RecordingTool

SENTINEL = "VALOR-DE-PRUEBA-123"
SUGGESTION = " Sugerencia: "
FORBIDDEN_IN_OUTPUT = (
    "Traceback",
    'File "',
    "RecordingTool",
    "FailingTool",
    "RaisingTool",
    "ToolResult",
    "Event(",
    "payload",
    "call_id",
    SENTINEL,
)
FINAL = ProviderResponse(content="listo")


async def lines_of(rig: Rig, output: io.StringIO) -> list[str]:
    await rig.run("haz la tarea")
    return output.getvalue().splitlines()


def build(
    script: list[ProviderResponse | BaseException],
    tools: list[RecordingTool],
    **options: object,
) -> tuple[Rig, io.StringIO]:
    bus, output = InMemoryEventBus(), io.StringIO()
    attach_renderer(bus, output)
    return make_rig(script, tools, bus=bus, **options), output  # type: ignore[arg-type]


def one_call() -> list[ProviderResponse | BaseException]:
    return [response(call("c1", "step_1", ruta=SENTINEL)), FINAL]


def assert_clean(text: str) -> None:
    for fragment in FORBIDDEN_IN_OUTPUT:
        assert fragment not in text, fragment


class TestAC01EstadoEnVivo:
    async def test_a_correct_tool_is_shown_running_then_correct_then_the_final_answer(
        self,
    ) -> None:
        rig, output = build(one_call(), [RecordingTool("step_1")])

        lines = await lines_of(rig, output)

        assert lines == ["... ejecutando: step_1", "v step_1: correcto", "> listo"]
        assert_clean(output.getvalue())

    async def test_three_tools_are_shown_in_order(self) -> None:
        script: list[ProviderResponse | BaseException] = [
            response(call("c1", "step_1")),
            response(call("c2", "step_2")),
            response(call("c3", "step_3")),
            FINAL,
        ]
        tools = [RecordingTool(f"step_{i}") for i in (1, 2, 3)]
        rig, output = build(script, tools)

        lines = await lines_of(rig, output)

        assert lines == [
            "... ejecutando: step_1",
            "v step_1: correcto",
            "... ejecutando: step_2",
            "v step_2: correcto",
            "... ejecutando: step_3",
            "v step_3: correcto",
            "> listo",
        ]


class TestAC02ErroresClaros:
    async def test_an_unknown_tool_has_cause_and_suggestion(self) -> None:
        script: list[ProviderResponse | BaseException] = [response(call("c1", "fantasma")), FINAL]
        rig, output = build(script, [])

        lines = await lines_of(rig, output)

        assert lines == [
            "... ejecutando: fantasma",
            "x Error: La herramienta 'fantasma' no está registrada."
            f"{SUGGESTION}Revisa el nombre de la herramienta o regístrala antes de volver a "
            "intentarlo.",
            "> listo",
        ]
        assert_clean(output.getvalue())

    async def test_invalid_arguments_have_cause_and_suggestion(self) -> None:
        tool = RecordingTool("step_1")
        registry = InMemoryToolRegistry([tool], validate_error=ValueError(f"malo {SENTINEL}"))
        rig, output = build(one_call(), [tool], registry=registry)

        lines = await lines_of(rig, output)

        assert lines[1] == (
            "x Error: Los argumentos de la herramienta 'step_1' no son válidos."
            f"{SUGGESTION}Corrige los argumentos según el esquema de la herramienta y vuelve "
            "a intentarlo."
        )
        assert tool.executions == []
        assert_clean(output.getvalue())

    async def test_a_denial_is_reported_once_and_then_the_tool_did_not_run(self) -> None:
        tool = RecordingTool("step_1")
        rig, output = build(one_call(), [tool], decisions={"step_1": PermissionDecision.DENY})

        lines = await lines_of(rig, output)

        assert lines == [
            "... ejecutando: step_1",
            "x Permiso: La herramienta 'step_1' fue denegada por la política de permisos."
            f"{SUGGESTION}Si debe permitirse, ajusta la política de permisos; mientras esté "
            "denegada el agente no la ejecutará.",
            "x step_1: no se ejecutó.",
            "> listo",
        ]
        assert tool.executions == []
        assert output.getvalue().count("Sugerencia") == 1
        assert_clean(output.getvalue())

    async def test_a_question_without_approver_says_that_approval_is_not_available(self) -> None:
        rig, output = build(
            one_call(), [RecordingTool("step_1")], decisions={"step_1": PermissionDecision.ASK}
        )

        lines = await lines_of(rig, output)

        assert lines[1].startswith(
            "x Permiso: La herramienta 'step_1' requiere aprobación, que no está disponible"
        )
        assert lines[2] == "x step_1: no se ejecutó."
        assert_clean(output.getvalue())

    async def test_a_policy_that_fails_is_reported_as_denied_for_safety(self) -> None:
        rig, output = build(
            one_call(), [RecordingTool("step_1")], decisions={"step_1": RuntimeError("falla")}
        )

        lines = await lines_of(rig, output)

        assert lines[1].startswith(
            "x Permiso: No se pudo evaluar la política de permisos para 'step_1'; se denegó por "
            "seguridad."
        )
        assert lines[2] == "x step_1: no se ejecutó."

    async def test_a_tool_that_raises_has_cause_and_suggestion_without_the_traceback(self) -> None:
        rig, output = build(one_call(), [RaisingTool("step_1", RuntimeError(f"boom {SENTINEL}"))])

        lines = await lines_of(rig, output)

        assert lines[1] == (
            "x Error: La herramienta 'step_1' falló al ejecutarse."
            f"{SUGGESTION}Vuelve a intentarlo y, si se repite, revisa el registro de eventos."
        )
        assert_clean(output.getvalue())

    async def test_a_tool_that_returns_an_error_has_cause_and_suggestion(self) -> None:
        rig, output = build(one_call(), [FailingTool("step_1", f"no existe {SENTINEL}")])

        lines = await lines_of(rig, output)

        assert lines[1].startswith("x Error: La herramienta 'step_1' terminó con un error.")
        assert SUGGESTION in lines[1]
        assert_clean(output.getvalue())

    async def test_a_tool_that_returns_an_invalid_result(self) -> None:
        invalid = RecordingTool("step_1", raw_result="no es un resultado")
        rig, output = build(one_call(), [invalid])

        lines = await lines_of(rig, output)

        assert lines[1].startswith("x Error: La herramienta 'step_1' devolvió un resultado no")
        assert_clean(output.getvalue())

    async def test_a_provider_failure_has_cause_and_suggestion(self) -> None:
        rig, output = build([RuntimeError("provider down")], [RecordingTool("t")])

        lines = await lines_of(rig, output)

        assert lines == [
            "x Error: El proveedor del modelo falló (RuntimeError): provider down."
            f"{SUGGESTION}Comprueba la conexión y la clave del proveedor y vuelve a intentarlo."
        ]
        assert_clean(output.getvalue())


class TestCicloCompleto:
    async def test_the_input_cycle_runs_the_real_loop_and_ends_cleanly(self) -> None:
        bus, output = InMemoryEventBus(), io.StringIO()
        tool = RecordingTool("step_1")
        rig = make_rig(one_call(), [tool], bus=bus)

        async def turn(task: str) -> object:
            return await rig.loop.run_turn(session_id=SESSION, task=task, history=rig.history)

        code = await run_cli(
            bus,
            turn,
            input_stream=io.StringIO("haz la tarea\n\n/desconocido\n/ayuda\n/salir\n"),
            output=output,
        )

        text = output.getvalue()
        assert code == EXIT_OK
        assert len(tool.executions) == 1  # the task reached the loop once
        assert "... ejecutando: step_1\nv step_1: correcto\n> listo\n" in text
        assert "Comando desconocido: '/desconocido'." in text
        assert "Comandos disponibles:" in text
        assert text.endswith("Sesión terminada.\n")
        assert_clean(text)


class BrokenAfterThePrompt(io.StringIO):
    """Accepts the prompt and fails on everything else."""

    def write(self, text: str, /) -> int:
        if text == PROMPT:
            return super().write(text)
        raise OSError("salida rota")


class BrokenOnTheEvents(io.StringIO):
    """Fails only when an event line (a running tool) is written."""

    def write(self, text: str, /) -> int:
        if text.startswith("..."):
            raise OSError("salida rota")
        return super().write(text)


class TestFallosDeEscrituraConElBucleReal:
    async def test_a_broken_output_stops_the_turn_before_the_tool_runs(self) -> None:
        bus = InMemoryEventBus()
        attach_renderer(bus, BrokenAfterThePrompt())
        tool = RecordingTool("step_1")
        rig = make_rig(one_call(), [tool], bus=bus)

        with pytest.raises(EventDeliveryError) as raised:
            await rig.run("haz la tarea")

        assert isinstance(raised.value.exceptions[0], OSError)
        assert tool.executions == []  # Q4: the failing publication stops the tool

    async def test_the_cycle_shows_one_line_and_returns_a_failure_code_when_the_turn_fails(
        self,
    ) -> None:
        bus, output = InMemoryEventBus(), BrokenOnTheEvents()
        rig = make_rig(one_call(), [RecordingTool("step_1")], bus=bus)

        async def turn(task: str) -> object:
            return await rig.loop.run_turn(session_id=SESSION, task=task, history=rig.history)

        code = await run_cli(bus, turn, input_stream=io.StringIO("haz la tarea\n"), output=output)

        text = output.getvalue()
        assert code == EXIT_FAILURE
        assert text == (
            PROMPT
            + "x Error: el turno terminó con un fallo interno (EventDeliveryError). "
            + "Sugerencia: revisa el registro de eventos.\n"
        )
        assert_clean(text)

    async def test_a_turn_that_fails_with_a_secret_in_its_message_shows_only_the_type(self) -> None:
        bus, output = InMemoryEventBus(), io.StringIO()
        rig = make_rig(one_call(), [RecordingTool("step_1")], bus=bus)

        async def turn(task: str) -> object:
            await rig.loop.run_turn(session_id=SESSION, task=task, history=rig.history)
            raise RuntimeError(f"fallo con {SENTINEL}")

        code = await run_cli(bus, turn, input_stream=io.StringIO("haz la tarea\n"), output=output)

        text = output.getvalue()
        assert code == EXIT_FAILURE
        assert text.endswith(
            "x Error: el turno terminó con un fallo interno (RuntimeError). "
            "Sugerencia: revisa el registro de eventos.\n"
        )
        assert text.count("fallo interno") == 1
        assert_clean(text)

    async def test_if_the_failure_line_cannot_be_written_that_failure_goes_up(self) -> None:
        bus, output = InMemoryEventBus(), BrokenAfterThePrompt()
        rig = make_rig(one_call(), [RecordingTool("step_1")], bus=bus)

        async def turn(task: str) -> object:
            return await rig.loop.run_turn(session_id=SESSION, task=task, history=rig.history)

        with pytest.raises(OSError, match="salida rota") as raised:
            await run_cli(bus, turn, input_stream=io.StringIO("haz la tarea\n"), output=output)

        assert isinstance(raised.value.__context__, EventDeliveryError)
