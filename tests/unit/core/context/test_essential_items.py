"""The essential elements: cleaning, caps per element and fixed errors (HU-02-06.1 / T002)."""

from __future__ import annotations

import pytest

from harness_agent.core import (
    KEY_CRITERIA_REF,
    KEY_INSTRUCTIONS,
    KEY_OBJECTIVE,
    KEY_RULES,
    KEY_TICKET,
    MARK,
    MAX_BLOCK_SHARE_PERCENT,
    MAX_ELEMENT_CHARS,
    EssentialContextError,
    EssentialContextTooLarge,
    EssentialContextUnavailable,
    EssentialItem,
    criteria_reference,
    make_items,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
HIDDEN = "<secreto oculto>"
INSTRUCTIONS = [("entorno", "Entorno: Linux y bash. "), ("git", "Reglas de git.\nSin empujar.")]


def items_of(**overrides: object) -> tuple[EssentialItem, ...]:
    fields: dict[str, object] = {
        "ticket": "TAREA-14: Validar el correo",
        "objective": "Rechazar correos sin dominio.",
        "rules": "No tocar el esquema.",
        "instructions": INSTRUCTIONS,
    }
    fields.update(overrides)
    return make_items(**fields)  # type: ignore[arg-type]


def by_key(items: tuple[EssentialItem, ...], key: str) -> list[EssentialItem]:
    return [item for item in items if item.key == key]


# --- constants ------------------------------------------------------------------------------------


def test_the_constants_of_the_contract() -> None:
    assert MARK == "[contexto esencial de la tarea]" and len(MARK) == 31
    assert (MAX_ELEMENT_CHARS, MAX_BLOCK_SHARE_PERCENT) == (8_000, 20)
    assert [KEY_OBJECTIVE, KEY_RULES, KEY_TICKET, KEY_CRITERIA_REF, KEY_INSTRUCTIONS] == [
        "objetivo",
        "reglas",
        "ticket",
        "criterios_ref",
        "instrucciones",
    ]


# --- EssentialItem --------------------------------------------------------------------------------


def test_a_valid_item_keeps_its_fields() -> None:
    item = EssentialItem(KEY_OBJECTIVE, 1, "texto", "tarea (objetivo)")

    assert (item.key, item.order, item.value, item.origin) == (
        "objetivo",
        1,
        "texto",
        "tarea (objetivo)",
    )


@pytest.mark.parametrize(
    "fields",
    [
        ("desconocida", 1, "valor", "origen"),
        (KEY_OBJECTIVE, 0, "valor", "origen"),
        (KEY_OBJECTIVE, -1, "valor", "origen"),
        (KEY_OBJECTIVE, True, "valor", "origen"),
        (KEY_OBJECTIVE, 1, "", "origen"),
        (KEY_OBJECTIVE, 1, "   ", "origen"),
        (KEY_OBJECTIVE, 1, "valor", ""),
        (KEY_OBJECTIVE, 1, "valor", "  "),
    ],
)
def test_an_invalid_item_is_refused_without_repeating_it(fields: tuple[object, ...]) -> None:
    with pytest.raises(EssentialContextError) as raised:
        EssentialItem(*fields)  # type: ignore[arg-type]

    assert str(raised.value).endswith(".") and "valor" not in str(raised.value)


# --- make_items -----------------------------------------------------------------------------------


def test_the_elements_come_in_a_fixed_order_with_their_origin() -> None:
    items = items_of()

    assert [(i.key, i.order) for i in items] == [
        ("ticket", 1),
        ("objetivo", 1),
        ("reglas", 1),
        ("instrucciones", 1),
        ("instrucciones", 2),
    ]
    assert by_key(items, KEY_TICKET)[0].origin == "tarea (título)"
    assert by_key(items, KEY_OBJECTIVE)[0].origin == "tarea (objetivo)"
    assert by_key(items, KEY_RULES)[0].origin == "tarea (reglas)"
    assert [i.origin for i in by_key(items, KEY_INSTRUCTIONS)] == ["entorno", "git"]


def test_the_ticket_is_one_line() -> None:
    items = items_of(ticket="  TAREA-14:" + chr(10) + "  Validar   el" + chr(9) + "correo ")

    assert by_key(items, KEY_TICKET)[0].value == "TAREA-14: Validar el correo"


def test_hidden_characters_are_removed_from_the_objective_and_the_rules() -> None:
    dirty = "uno" + chr(0x200B) + "dos" + chr(0x202E) + "tres" + chr(27) + "cuatro"

    items = items_of(objective=dirty, rules=dirty + chr(10) + "fin")

    assert by_key(items, KEY_OBJECTIVE)[0].value == "unodostrescuatro"
    assert by_key(items, KEY_RULES)[0].value == "unodostrescuatro" + chr(10) + "fin"


def test_a_credential_of_a_url_is_hidden_before_it_is_stored() -> None:
    url = "https://" + "usuario" + ":" + SENTINEL + "@servidor.example/r.git"

    items = items_of(objective="Clonar " + url, rules="Usar " + url)

    assert (
        by_key(items, KEY_OBJECTIVE)[0].value
        == "Clonar https://" + HIDDEN + "@servidor.example/r.git"
    )
    assert SENTINEL not in repr(items) and "usuario" not in repr(items)


@pytest.mark.parametrize("empty", [None, "", "   ", chr(10) + chr(9)])
def test_an_absent_ticket_or_rules_leave_no_row(empty: str | None) -> None:
    items = items_of(ticket=empty, rules=empty)

    assert by_key(items, KEY_TICKET) == [] and by_key(items, KEY_RULES) == []
    assert len(by_key(items, KEY_OBJECTIVE)) == 1


def test_the_instructions_are_stored_exactly_as_they_were_sent() -> None:
    items = items_of(
        instructions=[("entorno", " con espacios  "), ("git", "a" + chr(0x200B) + "b")]
    )

    assert [(i.order, i.value, i.origin) for i in by_key(items, KEY_INSTRUCTIONS)] == [
        (1, " con espacios  ", "entorno"),
        (2, "a" + chr(0x200B) + "b", "git"),
    ]


def test_the_instructions_have_no_cap() -> None:
    items = items_of(instructions=[("entorno", "x" * (MAX_ELEMENT_CHARS * 3))])

    assert len(by_key(items, KEY_INSTRUCTIONS)[0].value) == MAX_ELEMENT_CHARS * 3


@pytest.mark.parametrize("objective", ["", "   ", chr(0x200B) + chr(0x202E)])
def test_an_objective_that_is_empty_once_cleaned_is_refused(objective: str) -> None:
    with pytest.raises(EssentialContextError):
        items_of(objective=objective)


def test_without_instructions_it_is_refused() -> None:
    with pytest.raises(EssentialContextError):
        items_of(instructions=[])


def test_criteria_reference() -> None:
    item = criteria_reference("s1")

    assert (item.key, item.order, item.value) == ("criterios_ref", 1, "s1")
    assert item.origin == "criterios protegidos (HU-11-01)"
    with pytest.raises(EssentialContextError):
        criteria_reference("  ")


# --- caps per element -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "name"), [("objective", "objetivo"), ("rules", "reglas"), ("ticket", "ticket")]
)
def test_exactly_the_cap_is_accepted_and_one_more_is_refused(field: str, name: str) -> None:
    items_of(**{field: "a" * MAX_ELEMENT_CHARS})

    with pytest.raises(EssentialContextTooLarge) as raised:
        items_of(**{field: "a" * (MAX_ELEMENT_CHARS + 1)})

    assert raised.value.element == name
    assert (raised.value.limit, raised.value.unit) == (8_000, "caracteres")
    assert (
        str(raised.value)
        == f"El elemento «{name}» del contexto esencial supera el tope de 8000 caracteres."
    )


def test_the_cap_is_measured_after_cleaning_and_nothing_is_truncated() -> None:
    padded = "a" * MAX_ELEMENT_CHARS + chr(0x200B) * 4

    items = items_of(objective=padded)

    assert by_key(items, KEY_OBJECTIVE)[0].value == "a" * MAX_ELEMENT_CHARS


def test_the_message_never_carries_the_value() -> None:
    with pytest.raises(EssentialContextTooLarge) as raised:
        items_of(objective=SENTINEL + "a" * MAX_ELEMENT_CHARS)

    assert SENTINEL not in str(raised.value) and SENTINEL not in repr(raised.value.args)


# --- the fixed messages ---------------------------------------------------------------------------


def test_the_three_fixed_messages() -> None:
    assert str(EssentialContextTooLarge("bloque completo", 5_120, "tokens")) == (
        "El elemento «bloque completo» del contexto esencial supera el tope de 5120 tokens."
    )
    assert str(EssentialContextUnavailable(missing=False)) == (
        "No se pudo leer el contexto esencial de la tarea; la petición no se envía."
    )
    assert str(EssentialContextUnavailable(missing=True)) == (
        "Faltan elementos del contexto esencial de la tarea; la petición no se envía."
    )
    assert EssentialContextUnavailable(missing=True).missing is True
    assert EssentialContextUnavailable().missing is False


def test_the_errors_are_domain_errors_of_one_family() -> None:
    assert issubclass(EssentialContextTooLarge, EssentialContextError)
    assert issubclass(EssentialContextUnavailable, EssentialContextError)
    assert issubclass(EssentialContextError, ValueError)
