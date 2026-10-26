"""Tests of the text utilities and the category tables of the CLI (HU-06-01 / T002).

``sanitize`` and ``bounded`` treat everything that comes from the model, from a tool or from the
user as text to show, never as something to interpret. The tables hold the cause and the suggested
action of every error category that the agent loop publishes today; their texts are those of
``specs/009-basic-cli-events/contracts/cli_contract.md`` (section 3), character by character.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from harness_agent.cli.render import (
    ELLIPSIS,
    GENERIC_SUGGESTION,
    LIMIT_GUIDE,
    MAX_COMMAND_CHARS,
    MAX_NAME_CHARS,
    MAX_PROVIDER_MESSAGE_CHARS,
    PERMISSION_GUIDE,
    PROVIDER_GUIDE,
    TOOL_ERROR_GUIDE,
    UNKNOWN_NAME,
    UNKNOWN_PERMISSION_GUIDE,
    UNKNOWN_PROVIDER_GUIDE,
    UNKNOWN_TOOL_ERROR_GUIDE,
    ErrorGuide,
    bounded,
    sanitize,
)

LOOP_SOURCE = Path(__file__).resolve().parents[3] / "src" / "harness_agent" / "core" / "loop.py"
BIDI_CONTROLS = [*range(0x202A, 0x202F), *range(0x2066, 0x206A)]
CONTROL_CODES = [
    code for code in [*range(0x20), 0x7F, *range(0x80, 0xA0)] if code not in (ord("\n"), ord("\t"))
]
FINAL_STATE_ONLY = frozenset(
    {
        "permission_denied",
        "approval_required_unavailable",
        "approval_rejected",
        "approval_failed",
    }
)
# The categories that the loop publishes in TOOL_FINISHED besides the ones in square brackets.
OTHER_LOOP_CATEGORIES = {"ok", "tool_error", "invalid_tool_result"}


class TestSanitize:
    @pytest.mark.parametrize("code", CONTROL_CODES + BIDI_CONTROLS, ids=hex)
    def test_every_control_character_is_removed(self, code: int) -> None:
        assert sanitize(f"a{chr(code)}b") == "ab"

    def test_the_line_break_and_the_tab_are_kept(self) -> None:
        assert sanitize("uno\n\tdos") == "uno\n\tdos"

    def test_a_carriage_return_is_removed_but_the_line_break_stays(self) -> None:
        assert sanitize("uno\r\ndos") == "uno\ndos"

    def test_an_escape_sequence_loses_its_escape_character(self) -> None:
        assert sanitize("a\x1b[31mrojo\x1b[0m") == "a[31mrojo[0m"

    def test_accents_enye_and_emoji_are_kept(self) -> None:
        text = "Leí el archivo pagos.py ñ 🙂"

        assert sanitize(text) == text

    def test_it_is_idempotent(self) -> None:
        once = sanitize("a\x00b\x1b‮c\n")

        assert sanitize(once) == once

    def test_an_empty_text_stays_empty(self) -> None:
        assert sanitize("") == ""


class TestBounded:
    def test_a_short_text_is_not_changed(self) -> None:
        assert bounded("corto", 10) == "corto"

    def test_a_text_of_exactly_the_limit_is_not_changed(self) -> None:
        assert bounded("x" * 10, 10) == "x" * 10

    def test_a_longer_text_is_cut_to_the_limit_with_an_ellipsis(self) -> None:
        result = bounded("x" * 100, 10)

        assert len(result) == 10
        assert result == "x" * 7 + ELLIPSIS


class TestConstantes:
    def test_the_documented_values(self) -> None:
        assert MAX_NAME_CHARS == 64
        assert MAX_PROVIDER_MESSAGE_CHARS == 200
        assert MAX_COMMAND_CHARS == 40
        assert ELLIPSIS == "..."
        assert UNKNOWN_NAME == "(sin nombre)"
        assert GENERIC_SUGGESTION == "Revisa el registro de eventos."


EXPECTED_TOOL_ERRORS = {
    "unknown_tool": (
        "La herramienta '{name}' no está registrada.",
        "Revisa el nombre de la herramienta o regístrala antes de volver a intentarlo.",
    ),
    "invalid_arguments": (
        "Los argumentos de la herramienta '{name}' no son válidos.",
        "Corrige los argumentos según el esquema de la herramienta y vuelve a intentarlo.",
    ),
    "tool_exception": (
        "La herramienta '{name}' falló al ejecutarse.",
        "Vuelve a intentarlo y, si se repite, revisa el registro de eventos.",
    ),
    "invalid_tool_result": (
        "La herramienta '{name}' devolvió un resultado no válido.",
        "Revisa la implementación de la herramienta y el registro de eventos.",
    ),
    "tool_error": (
        "La herramienta '{name}' terminó con un error.",
        "Revisa los datos de la llamada y vuelve a intentarlo; el detalle está en el historial "
        "de la sesión.",
    ),
}
EXPECTED_PERMISSION = {
    "deny": (
        "La herramienta '{name}' fue denegada por la política de permisos.",
        "Si debe permitirse, ajusta la política de permisos; mientras esté denegada el agente "
        "no la ejecutará.",
    ),
    "policy_error": (
        "No se pudo evaluar la política de permisos para '{name}'; se denegó por seguridad.",
        "Revisa la política de permisos configurada.",
    ),
    "ask": (
        "La herramienta '{name}' requiere aprobación, que no está disponible en esta sesión; "
        "se resolvió como denegada.",
        "Pide una acción que no requiera aprobación o espera a que esté disponible la "
        "aprobación interactiva.",
    ),
}
EXPECTED_PROVIDER = {
    "provider_exception": (
        "El proveedor del modelo falló ({error_type}): {message}",
        "Comprueba la conexión y la clave del proveedor y vuelve a intentarlo.",
    ),
    "invalid_response": (
        "El proveedor del modelo devolvió una respuesta no válida ({error_type}).",
        "Vuelve a intentarlo y, si se repite, revisa el registro de eventos.",
    ),
}


def pair(guide: ErrorGuide) -> tuple[str, str]:
    return guide.cause, guide.suggestion


class TestTablas:
    def test_the_tool_error_table_has_exactly_the_documented_categories(self) -> None:
        assert set(TOOL_ERROR_GUIDE) == set(EXPECTED_TOOL_ERRORS)

    @pytest.mark.parametrize("category", sorted(EXPECTED_TOOL_ERRORS))
    def test_each_tool_error_text_is_the_one_of_the_contract(self, category: str) -> None:
        assert pair(TOOL_ERROR_GUIDE[category]) == EXPECTED_TOOL_ERRORS[category]

    def test_the_unknown_tool_error_is_generic_and_suggests_the_event_log(self) -> None:
        assert pair(UNKNOWN_TOOL_ERROR_GUIDE) == (
            "Ocurrió un error de categoría desconocida en la herramienta '{name}'.",
            GENERIC_SUGGESTION,
        )

    def test_the_permission_table_has_the_documented_cases(self) -> None:
        assert set(PERMISSION_GUIDE) == set(EXPECTED_PERMISSION)
        for case, expected in EXPECTED_PERMISSION.items():
            assert pair(PERMISSION_GUIDE[case]) == expected

    def test_an_unknown_permission_decision_is_generic(self) -> None:
        assert pair(UNKNOWN_PERMISSION_GUIDE) == (
            "Se recibió una decisión de permiso desconocida para '{name}'.",
            GENERIC_SUGGESTION,
        )

    def test_the_provider_table_has_the_documented_reasons(self) -> None:
        assert set(PROVIDER_GUIDE) == set(EXPECTED_PROVIDER)
        for reason, expected in EXPECTED_PROVIDER.items():
            assert pair(PROVIDER_GUIDE[reason]) == expected

    def test_an_unknown_provider_reason_is_generic(self) -> None:
        assert pair(UNKNOWN_PROVIDER_GUIDE) == (
            "El proveedor del modelo falló ({error_type}).",
            GENERIC_SUGGESTION,
        )

    def test_the_limit_text_is_fixed(self) -> None:
        assert pair(LIMIT_GUIDE) == (
            "Se alcanzó un límite de la sesión.",
            "Revisa los límites en la configuración y empieza una tarea nueva.",
        )

    def test_every_text_is_a_complete_sentence(self) -> None:
        guides = [
            *TOOL_ERROR_GUIDE.values(),
            *PERMISSION_GUIDE.values(),
            *PROVIDER_GUIDE.values(),
            UNKNOWN_TOOL_ERROR_GUIDE,
            UNKNOWN_PERMISSION_GUIDE,
            UNKNOWN_PROVIDER_GUIDE,
            LIMIT_GUIDE,
        ]
        for guide in guides:
            assert guide.cause.endswith(".") or guide.cause.endswith("{message}"), guide.cause
            assert guide.suggestion.endswith("."), guide.suggestion
            assert "Traceback" not in guide.cause + guide.suggestion

    def test_the_tables_and_their_entries_are_immutable(self) -> None:
        for table in (TOOL_ERROR_GUIDE, PERMISSION_GUIDE, PROVIDER_GUIDE):
            with pytest.raises(TypeError):
                table["otra"] = LIMIT_GUIDE  # type: ignore[index]
        with pytest.raises(dataclasses.FrozenInstanceError):
            LIMIT_GUIDE.cause = "otra"  # type: ignore[misc]


class TestCoberturaDeCategorias:
    def test_every_category_that_the_loop_publishes_has_an_entry_or_a_final_state(self) -> None:
        source = LOOP_SOURCE.read_text(encoding="utf-8")
        in_brackets = set(re.findall(r'"\[([a-z_]+)\] ', source))
        categories = in_brackets | OTHER_LOOP_CATEGORIES

        assert {"unknown_tool", "invalid_arguments", "permission_denied"} <= in_brackets
        for category in sorted(categories):
            covered = (
                category == "ok" or category in TOOL_ERROR_GUIDE or category in FINAL_STATE_ONLY
            )
            assert covered, f"La categoría '{category}' del bucle no está en la tabla de la CLI."
