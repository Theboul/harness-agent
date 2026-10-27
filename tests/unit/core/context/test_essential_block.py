"""The text of the essential block and its size checks (HU-02-06.1, block_format.md)."""

from __future__ import annotations

import random

import pytest

from harness_agent.core import (
    ContextSettings,
    EssentialContextError,
    EssentialContextTooLarge,
    EssentialItem,
    Message,
    Role,
    TaskCriteriaItem,
    block_fits,
    check_block,
    check_creation,
    estimate_message,
    instruction_messages,
    make_items,
    render_block,
    threshold_tokens,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
HEADER = (
    "[contexto esencial de la tarea]\n"
    "Contexto fijo de la tarea: lo guarda el harness fuera del historial y se te entrega "
    "completo en cada llamada."
)
DEFAULT = ContextSettings()
SMALL = ContextSettings(window_tokens=1_000, threshold_percent=45)


def criterion(number: int, text: str, *, passes: bool = False, **more: object) -> TaskCriteriaItem:
    return TaskCriteriaItem(str(number), text, passes, **more)  # type: ignore[arg-type]


def e1_items() -> tuple[EssentialItem, ...]:
    return make_items(
        ticket="TAREA-14: Validar el correo",
        objective="Rechazar correos sin dominio en el formulario de alta.",
        rules="No tocar el esquema de la base.\nMantener la API pública.",
        instructions=[("entorno", "Entorno: Linux.")],
    )


E1_CRITERIA = [
    criterion(1, "El validador rechaza a@ y a@b"),
    criterion(2, "Las pruebas del formulario pasan", passes=True),
]
E1 = (
    HEADER + "\n\n"
    "Ticket: TAREA-14: Validar el correo\n\n"
    "Objetivo:\nRechazar correos sin dominio en el formulario de alta.\n\n"
    "Reglas:\nNo tocar el esquema de la base.\nMantener la API pública.\n\n"
    "Criterios de aceptación (estado actual):\n"
    "1. [pendiente] El validador rechaza a@ y a@b\n"
    "2. [cumplido] Las pruebas del formulario pasan"
)


def tokens(text: str) -> int:
    return estimate_message(Message(Role.SYSTEM, text))


# --- the examples of the contract -----------------------------------------------------------------


def test_e1_a_complete_task() -> None:
    text = render_block(e1_items(), E1_CRITERIA)

    assert text == E1
    assert (len(text), tokens(text)) == (444, 115)


def test_e2_a_criterion_passes() -> None:
    changed = [criterion(1, "El validador rechaza a@ y a@b", passes=True), E1_CRITERIA[1]]

    text = render_block(e1_items(), changed)

    assert text == E1.replace("1. [pendiente]", "1. [cumplido]")
    assert (len(text), tokens(text)) == (443, 115)


def test_e3_without_ticket_or_rules() -> None:
    items = make_items(
        ticket=None, objective="Documentar la API.", rules=None, instructions=[("entorno", "x")]
    )

    text = render_block(items, [criterion(1, "El README describe la API")])

    assert text == (
        HEADER + "\n\nObjetivo:\nDocumentar la API.\n\n"
        "Criterios de aceptación (estado actual):\n1. [pendiente] El README describe la API"
    )
    assert (len(text), tokens(text)) == (254, 68)
    assert "Ticket:" not in text and "Reglas:" not in text


def test_e4_without_criteria_or_with_only_a_ticket() -> None:
    items = make_items(
        ticket=None, objective="Documentar la API.", rules=None, instructions=[("entorno", "x")]
    )
    only_ticket = (EssentialItem("ticket", 1, "TAREA-1", "tarea (título)"),)

    assert render_block(items, []) == HEADER + "\n\nObjetivo:\nDocumentar la API."
    assert render_block(only_ticket, []) == HEADER + "\n\nTicket: TAREA-1"


def test_e5_a_description_with_line_breaks_and_hidden_characters_is_one_line() -> None:
    description = "Pasa la suite" + chr(10) + "completa" + chr(0x200B) + " (sin saltos)"

    text = render_block(e1_items(), [criterion(1, description)])

    assert text.endswith("1. [pendiente] Pasa la suite completa (sin saltos)")


def test_e6_a_credential_is_hidden_in_the_stored_value_and_in_the_block() -> None:
    url = "https://" + "usuario" + ":" + SENTINEL + "@servidor.example/r.git"
    items = make_items(
        ticket=None, objective="Clonar " + url, rules=None, instructions=[("entorno", "x")]
    )

    text = render_block(items, [criterion(1, "Usa " + url)])

    assert "https://<secreto oculto>@servidor.example/r.git" in text
    assert SENTINEL not in text and "usuario" not in text


# --- rules of the text ----------------------------------------------------------------------------


def test_the_order_is_fixed_whatever_the_order_of_the_items() -> None:
    items = list(e1_items())
    expected = render_block(items, E1_CRITERIA)
    shuffler = random.Random(20261031)

    for _ in range(20):
        shuffler.shuffle(items)
        assert render_block(items, E1_CRITERIA) == expected
    assert render_block(e1_items(), E1_CRITERIA) == expected  # the same text every time


def test_the_instructions_never_appear_in_the_block() -> None:
    items = make_items(
        ticket=None,
        objective="Objetivo.",
        rules=None,
        instructions=[("entorno", "INSTRUCCION-" + SENTINEL), ("git", "OTRA-" + SENTINEL)],
    )

    assert SENTINEL not in render_block(items, [])


def test_a_command_and_the_evidence_of_a_criterion_never_come_out() -> None:
    risky = criterion(
        1, "Algo", passes=True, evidence="EVIDENCIA-" + SENTINEL, command="CMD-" + SENTINEL
    )

    assert SENTINEL not in render_block(e1_items(), [risky])


def test_the_state_comes_from_passes_and_the_numbers_follow_the_source() -> None:
    criteria = [criterion(7, "a"), criterion(3, "b", passes=True), criterion(9, "c")]

    text = render_block(e1_items(), criteria)

    assert text.endswith("1. [pendiente] a\n2. [cumplido] b\n3. [pendiente] c")


def test_a_description_that_is_empty_once_cleaned_still_has_a_line() -> None:
    text = render_block(e1_items(), [criterion(1, chr(0x200B))])

    assert text.endswith("1. [pendiente] (sin descripción)")


def test_a_block_without_any_element_does_not_exist() -> None:
    only_instructions = (EssentialItem("instrucciones", 1, "texto", "entorno"),)

    with pytest.raises(EssentialContextError):
        render_block(only_instructions, [])
    with pytest.raises(EssentialContextError):
        render_block((), [])


# --- size (E7) ------------------------------------------------------------------------------------


def objective_item(length: int) -> tuple[EssentialItem, ...]:
    return (EssentialItem("objetivo", 1, "a" * length, "tarea (objetivo)"),)


def test_e7_the_default_share_is_5120_tokens_which_is_20464_characters() -> None:
    assert threshold_tokens(DEFAULT, "x/y") * 20 // 100 == 5_120
    fixed = len(HEADER) + 2 + len("Objetivo:\n")

    fits = render_block(objective_item(20_464 - fixed), [])
    over = render_block(objective_item(20_465 - fixed), [])

    assert (len(fits), len(over)) == (20_464, 20_465)
    assert block_fits(fits, DEFAULT, "x/y") and not block_fits(over, DEFAULT, "x/y")
    assert check_block(objective_item(20_464 - fixed), [], DEFAULT, "x/y") == fits
    with pytest.raises(EssentialContextTooLarge) as raised:
        check_block(objective_item(20_465 - fixed), [], DEFAULT, "x/y")
    assert str(raised.value) == (
        "El elemento «bloque completo» del contexto esencial supera el tope de 5120 tokens."
    )
    assert (raised.value.element, raised.value.limit, raised.value.unit) == (
        "bloque completo",
        5_120,
        "tokens",
    )


def test_e7_a_small_window_makes_the_example_not_fit() -> None:
    assert threshold_tokens(SMALL, "x/y") * 20 // 100 == 90

    with pytest.raises(EssentialContextTooLarge) as raised:
        check_block(e1_items(), E1_CRITERIA, SMALL, "x/y")

    assert str(raised.value) == (
        "El elemento «bloque completo» del contexto esencial supera el tope de 90 tokens."
    )


def test_the_threshold_of_the_model_in_use_is_the_one_that_counts() -> None:
    settings = ContextSettings(
        window_tokens=1_000, windows=(("grande/m", 1_000_000),), threshold_percent=45
    )

    assert check_block(e1_items(), E1_CRITERIA, settings, "grande/m") == E1
    with pytest.raises(EssentialContextTooLarge):
        check_block(e1_items(), E1_CRITERIA, settings, "otro/m")


def test_the_section_of_the_criteria_has_its_own_cap_of_8000_characters() -> None:
    prefix = len("1. [pendiente] ")
    exact = [criterion(1, "a" * (8_000 - prefix))]
    over = [criterion(1, "a" * (8_001 - prefix))]

    assert check_block(e1_items(), exact, DEFAULT, "x/y").endswith("a" * (8_000 - prefix))
    with pytest.raises(EssentialContextTooLarge) as raised:
        check_block(e1_items(), over, DEFAULT, "x/y")
    assert (
        str(raised.value)
        == "El elemento «criterios» del contexto esencial supera el tope de 8000 caracteres."
    )


def test_the_messages_of_size_do_not_carry_the_content() -> None:
    huge = [criterion(1, SENTINEL + "a" * 9_000)]

    with pytest.raises(EssentialContextTooLarge) as raised:
        check_block(e1_items(), huge, DEFAULT, "x/y")

    assert SENTINEL not in str(raised.value) and SENTINEL not in repr(raised.value.args)


def test_check_creation_arms_pending_criteria_from_the_descriptions() -> None:
    descriptions = ["El validador rechaza a@ y a@b", "Las pruebas del formulario pasan"]

    text = check_creation(e1_items(), descriptions, DEFAULT, "x/y")

    assert text == E1.replace("2. [cumplido]", "2. [pendiente]")
    pending = [criterion(1, descriptions[0]), criterion(2, descriptions[1])]
    assert text == check_block(e1_items(), pending, DEFAULT, "x/y")
    with pytest.raises(EssentialContextTooLarge):
        check_creation(e1_items(), descriptions, SMALL, "x/y")


# --- instruction_messages -------------------------------------------------------------------------


def test_the_instructions_are_rebuilt_in_order_with_their_exact_text() -> None:
    prefix = [Message(Role.SYSTEM, " entorno  "), Message(Role.SYSTEM, "git" + chr(10) + "reglas")]
    items = make_items(
        ticket="T",
        objective="O",
        rules=None,
        instructions=[("entorno", prefix[0].content), ("git", prefix[1].content)],
    )

    rebuilt = instruction_messages(tuple(reversed(items)))

    assert rebuilt == prefix
    assert all(message.role is Role.SYSTEM and not message.is_external for message in rebuilt)


def test_without_instructions_there_is_nothing_to_rebuild() -> None:
    assert instruction_messages((EssentialItem("objetivo", 1, "o", "tarea (objetivo)"),)) == []
