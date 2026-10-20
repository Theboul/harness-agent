"""Tests of ``render_event``: one text per event, built by hand (HU-06-01 / T003 and T005).

``TestEstadoDeHerramienta`` (AC-01) covers the tool status and the assistant message;
``TestErrores`` (AC-02, T005) covers the errors. The events are built with ``Event.create`` and
carry only the fields that the agent loop publishes today.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from harness_agent.cli.render import SHOWN_TYPES, render_event
from harness_agent.core import Event, EventType

SENTINEL = "VALOR-DE-PRUEBA-123"
ET = EventType
NOT_SHOWN = [event_type for event_type in EventType if event_type not in SHOWN_TYPES]


def make(event_type: EventType, **payload: Any) -> Event:
    return Event.create("session-1", event_type, dict(payload))


class TestEstadoDeHerramienta:
    def test_a_requested_tool_is_shown_as_running(self) -> None:
        event = make(ET.TOOL_REQUESTED, call_id="c1", name="buscar")

        assert render_event(event) == "... ejecutando: buscar"

    def test_a_finished_tool_without_error_is_shown_as_correct(self) -> None:
        event = make(ET.TOOL_FINISHED, call_id="c1", name="buscar", is_error=False, category="ok")

        assert render_event(event) == "v buscar: correcto"

    def test_a_missing_name_is_shown_as_unknown(self) -> None:
        assert render_event(make(ET.TOOL_REQUESTED)) == "... ejecutando: (sin nombre)"
        assert render_event(make(ET.TOOL_REQUESTED, name=5)) == "... ejecutando: (sin nombre)"
        assert render_event(make(ET.TOOL_REQUESTED, name="\x1b")) == "... ejecutando: (sin nombre)"

    def test_a_name_with_control_characters_is_sanitized(self) -> None:
        event = make(ET.TOOL_REQUESTED, name="bus\x1b[31mcar\r\nmas")

        line = render_event(event)

        assert line == "... ejecutando: bus[31mcar\nmas"

    def test_a_long_name_is_bounded_to_64_characters(self) -> None:
        line = render_event(make(ET.TOOL_REQUESTED, name="x" * 100))

        assert line == "... ejecutando: " + "x" * 61 + "..."

    def test_the_arguments_of_the_call_never_appear(self) -> None:
        payload = {"name": "buscar", "arguments": {"ruta": SENTINEL}, "content": SENTINEL}

        assert SENTINEL not in (render_event(make(ET.TOOL_REQUESTED, **payload)) or "")
        finished = make(ET.TOOL_FINISHED, is_error=False, **payload)
        assert SENTINEL not in (render_event(finished) or "")

    def test_the_text_of_the_assistant_is_shown_with_a_marker_on_each_line(self) -> None:
        event = make(ET.ASSISTANT_MESSAGE, content="uno\ndos\ntres", tool_call_count=0, final=True)

        assert render_event(event) == "> uno\n> dos\n> tres"

    def test_the_line_breaks_at_the_ends_of_the_text_are_dropped(self) -> None:
        assert render_event(make(ET.ASSISTANT_MESSAGE, content="\nhola\n\n")) == "> hola"

    def test_the_text_of_the_assistant_loses_its_control_characters(self) -> None:
        event = make(ET.ASSISTANT_MESSAGE, content="Leí\x1b[2J el archivo\x07 pagos.py")

        assert render_event(event) == "> Leí[2J el archivo pagos.py"

    @pytest.mark.parametrize("content", ["", "   ", "\n\n", "\x1b", None, 5, ["x"]])
    def test_an_empty_or_invalid_assistant_text_shows_nothing(self, content: object) -> None:
        assert render_event(make(ET.ASSISTANT_MESSAGE, content=content)) is None

    def test_a_missing_assistant_text_shows_nothing(self) -> None:
        assert render_event(make(ET.ASSISTANT_MESSAGE)) is None

    def test_a_long_assistant_text_is_shown_complete(self) -> None:
        text = "palabra " * 500

        line = render_event(make(ET.ASSISTANT_MESSAGE, content=text))

        assert line == "> " + text  # nothing is cut: only the line breaks at the ends go


class TestTiposNoMostrados:
    def test_the_shown_types_are_the_six_of_the_story(self) -> None:
        assert set(SHOWN_TYPES) == {
            ET.TOOL_REQUESTED,
            ET.TOOL_FINISHED,
            ET.ASSISTANT_MESSAGE,
            ET.PERMISSION_DECIDED,
            ET.PROVIDER_ERROR,
            ET.LIMIT_REACHED,
        }
        assert len(SHOWN_TYPES) == 6

    @pytest.mark.parametrize("event_type", NOT_SHOWN, ids=lambda t: t.value)
    def test_the_other_types_are_ignored_without_error(self, event_type: EventType) -> None:
        assert len(NOT_SHOWN) == 11
        assert render_event(make(event_type, name="buscar", content=SENTINEL)) is None

    @pytest.mark.parametrize("event_type", [ET.TOOL_REQUESTED, ET.ASSISTANT_MESSAGE])
    def test_an_empty_payload_never_raises(self, event_type: EventType) -> None:
        render_event(make(event_type))


class TestSecuenciaYRendimiento:
    def test_a_turn_with_three_tools_is_shown_in_the_order_of_the_events(self) -> None:
        events = []
        for index in (1, 2, 3):
            events.append(make(ET.TOOL_REQUESTED, name=f"paso_{index}"))
            events.append(make(ET.TOOL_FINISHED, name=f"paso_{index}", is_error=False))

        lines = [render_event(event) for event in events]

        assert lines == [
            "... ejecutando: paso_1",
            "v paso_1: correcto",
            "... ejecutando: paso_2",
            "v paso_2: correcto",
            "... ejecutando: paso_3",
            "v paso_3: correcto",
        ]

    def test_smoke_rendering_an_event_costs_less_than_a_millisecond(self) -> None:
        event = make(ET.TOOL_REQUESTED, name="buscar")
        render_event(event)  # warm-up
        renders = 1000

        start = time.perf_counter()
        for _ in range(renders):
            render_event(event)
        average = (time.perf_counter() - start) / renders

        assert average < 0.001


# ------------------------------------------------------------------------------- T005 (AC-02)

ERROR_PREFIX = "x Error: "
SUGGESTION = " Sugerencia: "
UNKNOWN_TOOL_LINE = (
    "x Error: Ocurrió un error de categoría desconocida en la herramienta 'buscar'. "
    "Sugerencia: Revisa el registro de eventos."
)
PERMISSION_LINES = {
    "deny": (
        "x Permiso: La herramienta 'buscar' fue denegada por la política de permisos. "
        "Sugerencia: Si debe permitirse, ajusta la política de permisos; mientras esté "
        "denegada el agente no la ejecutará."
    ),
    "policy_error": (
        "x Permiso: No se pudo evaluar la política de permisos para 'buscar'; se denegó por "
        "seguridad. Sugerencia: Revisa la política de permisos configurada."
    ),
    "ask": (
        "x Permiso: La herramienta 'buscar' requiere aprobación, que no está disponible en "
        "esta sesión; se resolvió como denegada. Sugerencia: Pide una acción que no requiera "
        "aprobación o espera a que esté disponible la aprobación interactiva."
    ),
    "unknown": (
        "x Permiso: Se recibió una decisión de permiso desconocida para 'buscar'. "
        "Sugerencia: Revisa el registro de eventos."
    ),
}
PROVIDER_SUGGESTION = "Comprueba la conexión y la clave del proveedor y vuelve a intentarlo."
LIMIT_LINE = (
    "x Límite: Se alcanzó un límite de la sesión. "
    "Sugerencia: Revisa los límites en la configuración y empieza una tarea nueva."
)
TOOL_ERROR_CASES = {
    "unknown_tool": (
        "La herramienta 'buscar' no está registrada.",
        "Revisa el nombre de la herramienta o regístrala antes de volver a intentarlo.",
    ),
    "invalid_arguments": (
        "Los argumentos de la herramienta 'buscar' no son válidos.",
        "Corrige los argumentos según el esquema de la herramienta y vuelve a intentarlo.",
    ),
    "tool_exception": (
        "La herramienta 'buscar' falló al ejecutarse.",
        "Vuelve a intentarlo y, si se repite, revisa el registro de eventos.",
    ),
    "invalid_tool_result": (
        "La herramienta 'buscar' devolvió un resultado no válido.",
        "Revisa la implementación de la herramienta y el registro de eventos.",
    ),
    "tool_error": (
        "La herramienta 'buscar' terminó con un error.",
        "Revisa los datos de la llamada y vuelve a intentarlo; el detalle está en el historial "
        "de la sesión.",
    ),
}


def finished(**payload: Any) -> Event:
    return make(ET.TOOL_FINISHED, name="buscar", **payload)


def provider(**payload: Any) -> Event:
    return make(ET.PROVIDER_ERROR, **payload)


class TestErrores:
    @pytest.mark.parametrize("category", sorted(TOOL_ERROR_CASES))
    def test_a_tool_error_of_a_known_category_has_cause_and_suggestion(self, category: str) -> None:
        cause, suggestion = TOOL_ERROR_CASES[category]

        line = render_event(finished(is_error=True, category=category))

        assert line == f"{ERROR_PREFIX}{cause}{SUGGESTION}{suggestion}"

    @pytest.mark.parametrize(
        "payload",
        [
            {"is_error": True, "category": SENTINEL},
            {"is_error": True, "category": None},
            {"is_error": True},
            {"is_error": True, "category": ["unknown_tool"]},
            {"category": "ok"},
            {"is_error": "yes", "category": "tool_error"},
            {"is_error": None, "category": "tool_error"},
        ],
    )
    def test_an_unknown_category_or_an_unclear_status_gives_the_generic_line(
        self, payload: dict[str, Any]
    ) -> None:
        line = render_event(finished(**payload))

        assert line == UNKNOWN_TOOL_LINE
        assert SENTINEL not in (line or "")

    @pytest.mark.parametrize("category", ["permission_denied", "approval_required_unavailable"])
    def test_a_tool_stopped_by_permissions_only_says_it_did_not_run(self, category: str) -> None:
        line = render_event(finished(is_error=True, category=category))

        assert line == "x buscar: no se ejecutó."

    @pytest.mark.parametrize(
        ("payload", "case"),
        [
            ({"decision": "deny", "reason": None}, "deny"),
            ({"decision": "deny"}, "deny"),
            ({"decision": "deny", "reason": "otra"}, "deny"),
            ({"decision": "deny", "reason": "policy_error"}, "policy_error"),
            ({"decision": "ask", "resolved_as": "deny"}, "ask"),
            ({"decision": "quizas"}, "unknown"),
            ({"decision": None}, "unknown"),
            ({}, "unknown"),
            ({"decision": ["deny"]}, "unknown"),
        ],
    )
    def test_a_denial_or_a_question_shows_the_reason_and_a_suggestion(
        self, payload: dict[str, Any], case: str
    ) -> None:
        line = render_event(make(ET.PERMISSION_DECIDED, name="buscar", **payload))

        assert line == PERMISSION_LINES[case]

    def test_an_allowed_call_shows_nothing(self) -> None:
        event = make(ET.PERMISSION_DECIDED, name="buscar", decision="allow", resolved_as="allow")

        assert render_event(event) is None

    def test_a_denial_is_reported_only_once_with_its_suggestion(self) -> None:
        decided = make(ET.PERMISSION_DECIDED, name="buscar", decision="deny", reason=None)
        done = finished(is_error=True, category="permission_denied")

        lines = [render_event(event) or "" for event in (decided, done)]

        assert sum(SUGGESTION in line for line in lines) == 1
        assert lines[1] == "x buscar: no se ejecutó."

    def test_a_provider_exception_shows_the_type_and_the_message(self) -> None:
        line = render_event(
            provider(reason="provider_exception", error_type="RuntimeError", message="sin red")
        )

        assert line == (
            f"{ERROR_PREFIX}El proveedor del modelo falló (RuntimeError): sin red."
            f"{SUGGESTION}{PROVIDER_SUGGESTION}"
        )

    @pytest.mark.parametrize("ending", [".", "!", "?"])
    def test_a_message_that_already_ends_a_sentence_gets_no_extra_period(self, ending: str) -> None:
        line = render_event(
            provider(reason="provider_exception", error_type="E", message=f"fallo{ending}")
        )

        assert line is not None
        assert f"(E): fallo{ending}{SUGGESTION}" in line

    def test_a_long_provider_message_is_bounded_to_200_characters(self) -> None:
        line = render_event(
            provider(reason="provider_exception", error_type="E", message="y" * 500)
        )

        assert line == (
            f"{ERROR_PREFIX}El proveedor del modelo falló (E): {'y' * 197}..."
            f"{SUGGESTION}{PROVIDER_SUGGESTION}"
        )

    def test_a_provider_message_is_sanitized_and_kept_on_one_line(self) -> None:
        line = render_event(
            provider(
                reason="provider_exception",
                error_type="E",
                message="uno\x1b[0m\r\ndos\n\ttres",
            )
        )

        assert line is not None
        assert "(E): uno[0m dos tres." in line
        assert "\n" not in line and "\x1b" not in line

    @pytest.mark.parametrize("message", [None, "", "   ", 5])
    def test_a_missing_provider_message_shows_only_the_type(self, message: object) -> None:
        line = render_event(
            provider(reason="provider_exception", error_type="RuntimeError", message=message)
        )

        assert line == (
            f"{ERROR_PREFIX}El proveedor del modelo falló (RuntimeError)."
            f"{SUGGESTION}{PROVIDER_SUGGESTION}"
        )

    def test_an_invalid_provider_response(self) -> None:
        line = render_event(provider(reason="invalid_response", error_type="InvalidResponse"))

        assert line == (
            f"{ERROR_PREFIX}El proveedor del modelo devolvió una respuesta no válida "
            f"(InvalidResponse).{SUGGESTION}Vuelve a intentarlo y, si se repite, revisa el "
            "registro de eventos."
        )

    @pytest.mark.parametrize("reason", [None, "otra", SENTINEL, 3])
    def test_an_unknown_provider_reason_is_generic_and_not_reproduced(self, reason: Any) -> None:
        line = render_event(provider(reason=reason, error_type="RuntimeError", message="x"))

        assert line == (
            f"{ERROR_PREFIX}El proveedor del modelo falló (RuntimeError)."
            f"{SUGGESTION}Revisa el registro de eventos."
        )

    def test_the_error_type_defaults_and_is_bounded(self) -> None:
        missing = render_event(provider(reason="invalid_response"))
        long = render_event(provider(reason="invalid_response", error_type="T" * 100))

        assert missing is not None and "(Error)" in missing
        assert long is not None and f"({'T' * 61}...)" in long

    @pytest.mark.parametrize("payload", [{}, {"detail": SENTINEL}, {"limit": SENTINEL}])
    def test_a_reached_limit_has_a_fixed_text_and_reads_nothing(
        self, payload: dict[str, Any]
    ) -> None:
        assert render_event(make(ET.LIMIT_REACHED, **payload)) == LIMIT_LINE


class TestLineasDeError:
    def error_events(self) -> list[Event]:
        events = [finished(is_error=True, category=category) for category in TOOL_ERROR_CASES]
        events.append(finished(is_error=True, category=SENTINEL))
        events.extend(
            make(ET.PERMISSION_DECIDED, name="buscar", decision=d) for d in ("deny", "ask")
        )
        events.append(provider(reason="provider_exception", error_type="E", message=SENTINEL))
        events.append(provider(reason="invalid_response", error_type="E"))
        events.append(make(ET.LIMIT_REACHED, detail=SENTINEL))
        return events

    def test_every_error_line_has_a_cause_a_suggestion_and_no_internals(self) -> None:
        for event in self.error_events():
            line = render_event(event)

            assert line is not None
            assert line.startswith("x ")
            assert SUGGESTION in line
            assert line.endswith(".")
            assert "Traceback" not in line and 'File "' not in line
            assert "{" not in line and "}" not in line
            assert "Event(" not in line and "payload" not in line

    def test_the_raw_payload_never_reaches_the_screen(self) -> None:
        for event in self.error_events():
            if event.type is ET.PROVIDER_ERROR and event.payload.get("message") == SENTINEL:
                continue  # the bounded provider message is part of the cause by design
            assert SENTINEL not in (render_event(event) or "")

    @pytest.mark.parametrize("event_type", list(SHOWN_TYPES), ids=lambda t: t.value)
    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {
                "name": 5,
                "is_error": [],
                "category": None,
                "reason": 3,
                "error_type": 4,
                "message": ["x"],
                "decision": None,
                "content": 7,
            },
            {"name": None, "is_error": {}, "category": {}, "decision": {}, "content": {}},
        ],
    )
    def test_an_incomplete_or_unexpected_payload_never_raises(
        self, event_type: EventType, payload: dict[str, Any]
    ) -> None:
        line = render_event(make(event_type, **payload))

        assert line is None or isinstance(line, str)

    def test_smoke_rendering_an_error_costs_less_than_a_millisecond(self) -> None:
        event = provider(reason="provider_exception", error_type="E", message="y" * 500)
        render_event(event)  # warm-up
        renders = 1000

        start = time.perf_counter()
        for _ in range(renders):
            render_event(event)
        average = (time.perf_counter() - start) / renders

        assert average < 0.001
