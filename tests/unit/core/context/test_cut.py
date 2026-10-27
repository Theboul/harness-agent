"""Split of the history, recent window and safe cut (HU-02-03, contracts/context_order.md)."""

from __future__ import annotations

import pytest

from harness_agent.core import (
    HistoryParts,
    Message,
    Role,
    ToolCall,
    ToolResult,
    choose_cut,
    estimate_messages,
    frame_summary,
    is_real,
    rebuild_history,
    split_history,
)

CALL = "leer_archivo"


def system(text: str = "entorno") -> Message:
    return Message(Role.SYSTEM, text)


def user(text: str = "usuario") -> Message:
    return Message(Role.USER, text)


def assistant(*call_ids: str, text: str = "asistente") -> Message:
    calls = tuple(ToolCall(call_id, CALL, {"path": "a.txt"}) for call_id in call_ids)
    return Message(Role.ASSISTANT, text, calls)


def tool(call_id: str) -> Message:
    return Message(
        Role.TOOL, "resultado", tool_result=ToolResult(call_id, "resultado"), is_external=True
    )


def example_history() -> list[Message]:
    """``H`` of the contract: 0 SYSTEM, 1 USER, 2 A(c1), 3 T(c1), 4 A(c2, c3), 5 T, 6 T, 7..11."""
    return [
        system(),
        user("petición"),
        assistant("c1"),
        tool("c1"),
        assistant("c2", "c3"),
        tool("c2"),
        tool("c3"),
        assistant(),
        user(),
        assistant(),
        user(),
        assistant(),
    ]


# --- is_real --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (system(), False),
        (user(), True),
        (Message(Role.USER, "salida del verificador", is_external=True), False),
        (frame_summary("resumen"), False),
        (assistant(), True),
        (assistant("c1"), True),
        (tool("c1"), True),
    ],
)
def test_is_real(message: Message, expected: bool) -> None:
    assert is_real(message) is expected


# --- split_history --------------------------------------------------------------------------------


def test_the_head_is_the_system_prefix_and_the_first_request() -> None:
    history = example_history()

    assert split_history(history) == HistoryParts(head_end=2, summary_index=None, region_start=2)


def test_several_system_messages_belong_to_the_head() -> None:
    history = [system("uno"), system("dos"), system("tres"), user("petición"), assistant()]

    assert split_history(history) == HistoryParts(head_end=4, summary_index=None, region_start=4)


def test_a_previous_summary_right_after_the_request_is_recognised() -> None:
    history = [system(), user("petición"), frame_summary("antes"), user(), assistant()]

    assert split_history(history) == HistoryParts(head_end=2, summary_index=2, region_start=3)


def test_an_external_message_that_is_not_the_summary_is_not_the_previous_summary() -> None:
    verifier = Message(Role.USER, "salida del verificador", is_external=True)
    history = [system(), user("petición"), verifier, assistant()]

    assert split_history(history) == HistoryParts(head_end=2, summary_index=None, region_start=2)


@pytest.mark.parametrize(
    "history",
    [
        [],
        [system()],
        [system(), system("otro")],
        [Message(Role.USER, "externo", is_external=True), assistant()],
        [system(), Message(Role.USER, "externo", is_external=True), user("petición")],
        [system(), frame_summary("solo un resumen"), user()],
        [system(), assistant(), user("petición")],
    ],
)
def test_without_an_initial_request_there_is_nothing_to_split(history: list[Message]) -> None:
    assert split_history(history) is None


def test_the_request_may_be_the_first_message() -> None:
    assert split_history([user("petición"), assistant()]) == HistoryParts(1, None, 1)


# --- choose_cut: the examples of the contract -----------------------------------------------------


def test_e1_four_recent_messages() -> None:
    history = example_history()

    cut = choose_cut(history, region_start=2, budget_tokens=0, min_messages=4)

    assert cut == 8
    assert history[cut].role is Role.USER
    assert len(history[2:cut]) == 6


def test_e2_the_cut_that_would_fall_on_a_result_retreats_to_its_call() -> None:
    history = example_history()
    budget = estimate_messages(history[6:])  # exactly the last six messages fit: desired cut 6

    cut = choose_cut(history, region_start=2, budget_tokens=budget, min_messages=4)

    assert history[6].role is Role.TOOL and history[5].role is Role.TOOL
    assert cut == 4
    assert history[cut].role is Role.ASSISTANT
    assert len(history[2:cut]) == 2


def test_e3_nothing_old_to_summarise() -> None:
    history = example_history()[:6]

    assert choose_cut(history, region_start=2, budget_tokens=0, min_messages=4) is None


def test_e4_second_compaction_with_the_previous_summary() -> None:
    previous = frame_summary("anterior")
    history = [system(), user("petición"), previous]
    history += [user(), assistant(), user(), assistant(), user(), assistant(), user(), assistant()]
    parts = split_history(history)

    assert parts == HistoryParts(head_end=2, summary_index=2, region_start=3)
    assert len(history) == 11
    cut = choose_cut(history, parts.region_start, budget_tokens=0, min_messages=4)

    assert cut == 7
    assert history[cut].role is Role.USER
    fresh = frame_summary("nuevo")
    rebuilt = rebuild_history(history, parts.region_start, cut, fresh)
    assert rebuilt == [history[0], history[1], fresh, *history[7:]]
    assert len(rebuilt) == 7 and previous not in rebuilt


# --- choose_cut: the window ----------------------------------------------------------------------


def test_a_large_budget_lengthens_the_recent_window_and_can_leave_nothing_to_summarise() -> None:
    history = example_history()

    assert choose_cut(history, 2, estimate_messages(history[8:]), 1) == 8
    assert choose_cut(history, 2, estimate_messages(history[2:]) * 2, 1) is None


def test_the_minimum_wins_over_a_budget_that_is_too_small() -> None:
    history = example_history()

    assert choose_cut(history, 2, 0, 1) == 11
    assert choose_cut(history, 2, 0, 6) == 4  # 6 would fall on a result: it retreats to the call


def test_the_cut_is_never_inside_the_head_or_before_the_previous_summary() -> None:
    previous = frame_summary("anterior")
    history = [system(), user("petición"), previous, user(), assistant(), user(), assistant()]

    for minimum in range(1, 9):
        cut = choose_cut(history, 3, 0, minimum)
        assert cut is None or cut > 3


def test_a_cut_at_the_very_end_is_possible_without_a_minimum() -> None:
    history = [system(), user("petición"), user(), assistant()]

    assert choose_cut(history, 2, 0, 0) == 4


def test_the_group_of_a_call_is_never_split_even_if_it_reaches_the_region_start() -> None:
    history = [system(), user("petición"), tool("c1"), tool("c2"), assistant()]

    assert choose_cut(history, 2, 0, 2) is None


@pytest.mark.parametrize("region_start", [-3, 0, 99])
def test_choose_cut_is_total_for_odd_arguments(region_start: int) -> None:
    history = example_history()

    result = choose_cut(history, region_start, 0, 4)

    assert result is None or isinstance(result, int)


def test_choose_cut_of_an_empty_history_is_none() -> None:
    assert choose_cut([], 0, 100, 4) is None


# --- rebuild_history -----------------------------------------------------------------------------


def test_the_rebuilt_history_keeps_the_head_and_the_recent_messages_as_the_same_objects() -> None:
    history = example_history()
    summary = frame_summary("resumen")

    rebuilt = rebuild_history(history, 2, 8, summary)

    assert rebuilt == [history[0], history[1], summary, *history[8:]]
    assert all(
        a is b for a, b in zip(rebuilt[:2] + rebuilt[3:], history[:2] + history[8:], strict=True)
    )
    assert sum(1 for message in rebuilt if message.content.startswith("[resumen")) == 1


def test_the_previous_summary_is_replaced_not_accumulated() -> None:
    old = frame_summary("anterior")
    history = [system(), user("petición"), old, user(), assistant(), user(), assistant()]
    new = frame_summary("nuevo")

    rebuilt = rebuild_history(history, 3, 5, new)

    assert rebuilt == [history[0], history[1], new, history[5], history[6]]


def test_rebuilding_does_not_touch_the_input() -> None:
    history = example_history()
    before = list(history)

    rebuild_history(history, 2, 8, frame_summary("resumen"))

    assert history == before
