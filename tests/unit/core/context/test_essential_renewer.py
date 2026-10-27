"""The renewer: find, insert and replace the block in place (HU-02-06.1 / T004, block_marker.md)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from harness_agent.core import (
    MARK,
    ContextSettings,
    EssentialItem,
    EssentialRenewer,
    Message,
    RenewalOutcome,
    Role,
    TaskCriteriaItem,
    ToolCall,
    ToolResult,
    block_message,
    check_block,
    criteria_reference,
    find_blocks,
    make_items,
)

SETTINGS = ContextSettings(window_tokens=4_000, threshold_percent=50)  # the block may weigh 400
SYSTEM = [Message(Role.SYSTEM, "entorno"), Message(Role.SYSTEM, "git")]


class FakeSource:
    def __init__(self, items: Sequence[EssentialItem]) -> None:
        self.items_found = tuple(items)
        self.asked: list[str] = []

    def items(self, session_id: str) -> Sequence[EssentialItem]:
        self.asked.append(session_id)
        return self.items_found


class FakeCriteria:
    def __init__(self, criteria: Sequence[TaskCriteriaItem]) -> None:
        self.criteria = list(criteria)
        self.asked: list[str] = []

    def load_criteria(self, session_id: str) -> Sequence[TaskCriteriaItem]:
        self.asked.append(session_id)
        return list(self.criteria)


def stored_items(reference: str = "referencia-1") -> tuple[EssentialItem, ...]:
    items = make_items(
        ticket="TAREA-14: Validar",
        objective="Rechazar correos sin dominio.",
        rules="No tocar el esquema.",
        instructions=[("entorno", "entorno"), ("git", "git")],
    )
    return (*items, criteria_reference(reference))


def pending() -> list[TaskCriteriaItem]:
    return [
        TaskCriteriaItem("1", "El validador rechaza a@"),
        TaskCriteriaItem("2", "Pasan las pruebas"),
    ]


def renewer(
    source: FakeSource | None = None, criteria: FakeCriteria | None = None
) -> tuple[EssentialRenewer, FakeSource, FakeCriteria]:
    chosen = source if source is not None else FakeSource(stored_items())
    reader = criteria if criteria is not None else FakeCriteria(pending())
    return (
        EssentialRenewer(chosen, reader, SETTINGS, session_id="s1", model=lambda: "fake/test"),
        chosen,
        reader,
    )


def expected_text(criteria: Sequence[TaskCriteriaItem] | None = None) -> str:
    return check_block(
        stored_items(), pending() if criteria is None else criteria, SETTINGS, "fake/test"
    )


def block_in(history: list[Message]) -> Message:
    (index,) = find_blocks(history)
    return history[index]


# --- find_blocks: who is the block ------------------------------------------------------------


def test_the_block_is_only_a_system_message_of_the_leading_run_that_starts_with_the_mark() -> None:
    real = block_message(MARK + "\ncuerpo")
    history = [
        Message(Role.SYSTEM, "entorno"),
        real,
        Message(Role.USER, MARK + "\nfalso"),
        Message(Role.USER, MARK + "\nexterno", is_external=True),
        Message(Role.ASSISTANT, MARK + "\nfalso"),
        Message(Role.TOOL, MARK + "\nfalso", tool_result=ToolResult("c", "x"), is_external=True),
        Message(Role.SYSTEM, MARK + "\ntras un mensaje que no es de sistema"),
    ]

    assert find_blocks(history) == [1]


@pytest.mark.parametrize(
    "content",
    ["texto " + MARK + "\nmedio", MARK + " seguido de un espacio", "[contexto esencial]", ""],
)
def test_a_system_message_that_does_not_start_with_the_mark_and_a_line_break_is_not_the_block(
    content: str,
) -> None:
    assert find_blocks([Message(Role.SYSTEM, content)]) == []


def test_the_mark_alone_is_a_block_and_a_second_one_is_found_too() -> None:
    history = [
        Message(Role.SYSTEM, MARK),
        Message(Role.SYSTEM, MARK + "\nb"),
        Message(Role.USER, "x"),
    ]

    assert find_blocks(history) == [0, 1]
    assert find_blocks([]) == []


def test_block_message_is_a_system_message() -> None:
    message = block_message("texto")

    assert message == Message(Role.SYSTEM, "texto") and not message.is_external


# --- E1 and E2: insert ------------------------------------------------------------------------


def test_e1_the_first_insertion_goes_after_the_two_provisional_messages() -> None:
    history = list(SYSTEM)
    keeper, _, _ = renewer()

    outcome = keeper.renew(history)

    assert outcome is RenewalOutcome.INSERTED
    assert history[:2] == SYSTEM and len(history) == 3
    assert history[2] == block_message(expected_text())


def test_e2_with_commands_it_goes_in_the_fourth_place_before_the_request() -> None:
    history = [*SYSTEM, Message(Role.SYSTEM, "comandos"), Message(Role.USER, "petición")]
    keeper, _, _ = renewer()

    keeper.renew(history)

    assert [m.content[:10] for m in history] == [
        "entorno",
        "git",
        "comandos",
        MARK[:10],
        "petición",
    ]
    assert find_blocks(history) == [3]


def test_with_an_empty_history_it_goes_first() -> None:
    history: list[Message] = []
    keeper, _, _ = renewer()

    assert keeper.renew(history) is RenewalOutcome.INSERTED
    assert find_blocks(history) == [0]


def test_with_no_system_prefix_it_goes_before_the_first_message() -> None:
    history = [Message(Role.USER, "petición")]
    keeper, _, _ = renewer()

    keeper.renew(history)

    assert find_blocks(history) == [0] and history[1].content == "petición"


# --- E3: replace ------------------------------------------------------------------------------


def test_e3_a_changed_criterion_replaces_the_block_in_the_same_place() -> None:
    criteria = FakeCriteria(pending())
    keeper, _, _ = renewer(criteria=criteria)
    history = [
        *SYSTEM,
        Message(Role.USER, "petición"),
        Message(Role.ASSISTANT, "", (ToolCall("c1", "leer", {}),)),
        Message(Role.TOOL, "datos", tool_result=ToolResult("c1", "datos"), is_external=True),
        Message(Role.ASSISTANT, "listo"),
    ]
    keeper.renew(history)
    before = list(history)
    criteria.criteria = [TaskCriteriaItem("1", "El validador rechaza a@", True), pending()[1]]

    outcome = keeper.renew(history)

    assert outcome is RenewalOutcome.REPLACED
    assert len(history) == len(before) == 7
    assert history[2].content == expected_text(criteria.criteria) != before[2].content
    assert "1. [cumplido]" in history[2].content
    for position in (0, 1, 3, 4, 5, 6):
        assert history[position] is before[position]


# --- E4: idempotent ---------------------------------------------------------------------------


def test_e4_two_renewals_without_a_change_leave_the_same_object() -> None:
    history = list(SYSTEM)
    keeper, _, _ = renewer()
    keeper.renew(history)
    block = history[2]

    assert keeper.renew(history) is RenewalOutcome.UNCHANGED
    assert keeper.renew(history) is RenewalOutcome.UNCHANGED
    assert history[2] is block and len(history) == 3


# --- E5: never two blocks ---------------------------------------------------------------------


def test_e5_a_duplicate_is_removed_and_the_first_one_is_brought_up_to_date() -> None:
    stale = block_message(MARK + "\nviejo")
    history = [*SYSTEM, stale, block_message(MARK + "\notro"), Message(Role.USER, "petición")]
    keeper, _, _ = renewer()

    outcome = keeper.renew(history)

    assert outcome is RenewalOutcome.REPLACED
    assert len(history) == 4 and find_blocks(history) == [2]
    assert history[2].content == expected_text() and history[3].content == "petición"


def test_e5_a_duplicate_of_an_up_to_date_block_is_removed_and_the_first_is_kept() -> None:
    current = block_message(expected_text())
    history = [*SYSTEM, current, block_message(expected_text()), Message(Role.USER, "petición")]
    keeper, _, _ = renewer()

    outcome = keeper.renew(history)

    assert outcome is RenewalOutcome.REPLACED  # the list did change
    assert history[2] is current and len(history) == 4 and find_blocks(history) == [2]


# --- E6: imitation ----------------------------------------------------------------------------


def test_e6_text_that_imitates_the_mark_in_the_other_roles_changes_nothing_but_the_real_block() -> (
    None
):
    fake_user = Message(Role.USER, MARK + "\nfalso")
    fake_external = Message(Role.USER, MARK + "\nfalso", is_external=True)
    fake_tool = Message(
        Role.TOOL, MARK + "\nfalso", tool_result=ToolResult("c1", "x"), is_external=True
    )
    fake_assistant = Message(Role.ASSISTANT, MARK + "\nfalso")
    real_old = block_message(MARK + "\nviejo")
    history = [*SYSTEM, real_old, fake_user, fake_assistant, fake_tool, fake_external]
    keeper, _, _ = renewer()

    keeper.renew(history)

    assert history[2].content == expected_text()
    for position, original in (
        (3, fake_user),
        (4, fake_assistant),
        (5, fake_tool),
        (6, fake_external),
    ):
        assert history[position] is original
    assert len(history) == 7 and find_blocks(history) == [2]


def test_an_objective_that_contains_the_mark_does_not_make_a_second_block() -> None:
    items = make_items(
        ticket=None,
        objective="Antes\n" + MARK + "\nDespués",
        rules=None,
        instructions=[("entorno", "entorno")],
    )
    keeper = EssentialRenewer(
        FakeSource((*items, criteria_reference("r"))),
        FakeCriteria(pending()),
        SETTINGS,
        session_id="s1",
        model=lambda: "fake/test",
    )
    history = list(SYSTEM)

    keeper.renew(history)
    keeper.renew(history)

    assert find_blocks(history) == [2] and len(history) == 3


# --- what it reads and how --------------------------------------------------------------------


def test_the_criteria_are_read_with_the_stored_reference_not_with_the_session() -> None:
    source = FakeSource(stored_items(reference="referencia-guardada"))
    criteria = FakeCriteria(pending())
    keeper, _, _ = renewer(source, criteria)

    keeper.renew(list(SYSTEM))

    assert source.asked == ["s1"]  # the elements of the session of the renewer
    assert criteria.asked == ["referencia-guardada"]  # the criteria of what the reference says


def test_the_history_is_modified_in_place_and_the_other_messages_are_not_touched() -> None:
    history = [*SYSTEM, Message(Role.USER, "petición"), Message(Role.ASSISTANT, "respuesta")]
    identity, originals = id(history), list(history)
    keeper, _, _ = renewer()

    keeper.renew(history)

    assert id(history) == identity
    assert [m for m in history if m is not block_in(history)] == originals
