"""Rebuilding the context of a session from what is stored: examples E1 to E8 and E10 (T005)."""

from __future__ import annotations

import pytest

from harness_agent.core import (
    ConversationInconsistent,
    Message,
    MessageRecord,
    Role,
    StoredConversation,
    StoredMessage,
    ToolCall,
    ToolResult,
    check_structure,
    frame_summary,
    rebuild_conversation,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
P = Message(Role.SYSTEM, "prefijo")
SYNTHETIC = (
    "[tool_interrupted] La ejecución se interrumpió antes de obtener el resultado; "
    "verifique el estado antes de repetirla."
)
C1 = ToolCall("c1", "leer_archivo", {"path": "a.txt"})
C2 = ToolCall("c2", "buscar_texto", {"texto": "x"})


def row(
    position: int, message: Message, *, event: bool = True, covered: bool = False
) -> StoredMessage:
    event_id = f"e{position}" if event else None
    return StoredMessage(MessageRecord(position, message, event_id), covered if event else None)


def stored(
    rows: list[StoredMessage],
    *,
    summary: str | None = None,
    model: str | None = "m",
    last: str | None = "assistant_message",
) -> StoredConversation:
    return StoredConversation("s1", model, False, tuple(rows), summary, 0, last)


def user(text: str) -> Message:
    return Message(Role.USER, text)


def assistant(text: str, *calls: ToolCall) -> Message:
    return Message(Role.ASSISTANT, text, tuple(calls))


def tool(call: ToolCall, content: str = "ok", error: bool = False) -> Message:
    return Message(Role.TOOL, content, tool_result=ToolResult(call.id, content, error))


def e1_rows(**cover: bool) -> list[StoredMessage]:
    return [
        row(1, user("hola")),
        row(2, assistant("ok"), covered=cover.get("2", False)),
        row(3, user("lee a"), covered=cover.get("3", False)),
        row(4, assistant("", C1), event=False),
        row(5, tool(C1, "texto de a"), covered=cover.get("5", False)),
        row(6, assistant("fin")),
    ]


def messages(rows: list[StoredMessage]) -> list[Message]:
    return [r.record.message for r in rows]


def test_e1_a_session_never_compacted_comes_back_whole() -> None:
    rows = e1_rows()

    resumed = rebuild_conversation((P,), stored(rows), "m")

    assert list(resumed.history) == [P, *messages(rows)]
    assert len(resumed.history) == 7 and resumed.saved_count == 7
    assert resumed.closed_calls == () and not resumed.cut_off and not resumed.has_summary
    assert resumed.message_count == 6 and resumed.next_position == 7 and not resumed.empty
    assert resumed.notice == "Sesión reanudada: 6 mensajes."


def test_e2_one_compaction_gives_the_request_the_summary_and_the_uncovered_rows() -> None:
    rows = e1_rows(**{"2": True, "3": True})

    resumed = rebuild_conversation((P,), stored(rows, summary="S1"), "m")

    m = messages(rows)
    assert list(resumed.history) == [P, m[0], frame_summary("S1"), m[3], m[4], m[5]]
    assert resumed.message_count == 5 and resumed.has_summary and resumed.saved_count == 6
    assert resumed.notice == "Sesión reanudada: 5 mensajes en el contexto (con resumen)."
    assert resumed.history[2].is_external and resumed.history[2].role is Role.USER


def test_e3_two_compactions_use_the_newest_summary_and_a_row_with_no_event_follows_the_next() -> (
    None
):
    rows = [
        *e1_rows(**{"2": True, "3": True, "5": True}),
        row(7, user("otra")),
        row(8, assistant("listo")),
    ]

    resumed = rebuild_conversation((P,), stored(rows, summary="S2"), "m")

    m = messages(rows)
    assert list(resumed.history) == [P, m[0], frame_summary("S2"), m[5], m[6], m[7]]
    assert resumed.next_position == 9


def test_e4_a_cut_between_a_request_and_its_result_closes_the_missing_call() -> None:
    rows = [row(1, user("haz")), row(2, assistant("", C1, C2), event=False), row(3, tool(C1))]

    resumed = rebuild_conversation((P,), stored(rows, last="tool_finished"), "m")

    closing = Message(Role.TOOL, SYNTHETIC, tool_result=ToolResult("c2", SYNTHETIC, True))
    assert list(resumed.history) == [P, *messages(rows), closing]
    assert resumed.saved_count == 4 and resumed.closed_calls == (("c2", "buscar_texto"),)
    assert resumed.cut_off and not closing.is_external
    assert resumed.notice == (
        "Sesión reanudada: 4 mensajes. Terminó de forma abrupta; se cerró 1 llamada sin resultado."
    )


def test_e4_with_no_result_at_all_both_calls_are_closed_in_the_order_of_the_calls() -> None:
    rows = [row(1, user("haz")), row(2, assistant("", C1, C2), event=False)]

    resumed = rebuild_conversation((P,), stored(rows, last="user_message"), "m")

    ids = [m.tool_result.call_id for m in resumed.history if m.tool_result is not None]
    assert ids == ["c1", "c2"] and resumed.saved_count == 3
    assert resumed.closed_calls == (("c1", "leer_archivo"), ("c2", "buscar_texto"))
    assert resumed.notice.endswith("se cerraron 2 llamadas sin resultado.")


def test_e5_a_request_without_an_answer_is_kept_as_it_is() -> None:
    rows = [row(1, user("a")), row(2, assistant("b")), row(3, user("c"))]

    resumed = rebuild_conversation((P,), stored(rows, last="user_message"), "m")

    assert list(resumed.history) == [P, *messages(rows)]
    assert resumed.closed_calls == () and not resumed.cut_off


def test_e6_a_rejection_comes_back_with_the_standard_text_it_was_stored_with() -> None:
    standard = "[approval_rejected] Tool 'shell' was rejected by the user."
    call = ToolCall("c9", "shell", {})
    rows = [
        row(1, user("haz")),
        row(2, assistant("", call), event=False),
        row(3, tool(call, standard, error=True)),
    ]

    resumed = rebuild_conversation((P,), stored(rows), "m")

    assert resumed.history[-1].content == standard


def test_e7_an_empty_answer_at_the_cut_follows_the_next_row_the_declared_divergence() -> None:
    rows = [
        row(1, user("uno")),
        row(2, assistant("x"), covered=True),
        row(3, user("y"), covered=True),
        row(4, assistant(""), event=False),
        row(5, user("z")),
        row(6, assistant("w")),
    ]

    resumed = rebuild_conversation((P,), stored(rows, summary="S"), "m")

    m = messages(rows)
    assert list(resumed.history) == [P, m[0], frame_summary("S"), m[3], m[4], m[5]]


INCONSISTENT = {
    "the first row is not a request": (
        [row(1, assistant("x")), row(2, user("y"))],
        None,
    ),
    "the first row is external": (
        [row(1, Message(Role.USER, "x", is_external=True))],
        None,
    ),
    "the first row is covered": (
        [row(1, user("x"), covered=True), row(2, assistant("y"))],
        "S",
    ),
    "covered rows without a summary": (
        [row(1, user("x")), row(2, assistant("y"), covered=True), row(3, user("z"))],
        None,
    ),
    "a summary without covered rows": ([row(1, user("x")), row(2, assistant("y"))], "S"),
    "covered rows that are not contiguous": (
        [
            row(1, user("x")),
            row(2, assistant("y")),
            row(3, user("z"), covered=True),
            row(4, assistant("w")),
        ],
        "S",
    ),
    "a result without its call": ([row(1, user("x")), row(2, tool(C1))], None),
    "a call left unanswered in the middle": (
        [row(1, user("x")), row(2, assistant("", C1), event=False), row(3, user("y"))],
        None,
    ),
    "a repeated call identifier": (
        [
            row(1, user("x")),
            row(2, assistant("", C1), event=False),
            row(3, tool(C1)),
            row(4, assistant("", C1), event=False),
            row(5, tool(C1)),
        ],
        None,
    ),
    "a summary but no rows": ([], "S"),
}


@pytest.mark.parametrize("name", list(INCONSISTENT))
def test_e8_an_incoherent_conversation_is_never_rebuilt(name: str) -> None:
    rows, summary = INCONSISTENT[name]

    with pytest.raises(ConversationInconsistent) as caught:
        rebuild_conversation((P,), stored(rows, summary=summary), "m")

    assert SENTINEL not in str(caught.value)


def test_e10_a_session_with_no_messages_starts_again_from_the_prefix() -> None:
    resumed = rebuild_conversation((P,), stored([], last=None), "m")

    assert list(resumed.history) == [P] and resumed.saved_count == 1
    assert resumed.empty and resumed.message_count == 0 and resumed.next_position == 1
    assert not resumed.cut_off and not resumed.has_summary
    assert resumed.notice == "Sesión reanudada: no tenía mensajes; se empieza de nuevo."


def test_the_status_line_for_every_case_never_carries_content_or_names() -> None:
    rows = [row(1, user(SENTINEL)), row(2, assistant("", C1), event=False)]
    interrupted = stored(e1_rows(), last="interrupted")

    cut = rebuild_conversation((P,), stored(rows, last="user_message"), "otro")
    stop = rebuild_conversation((P,), interrupted, "m")
    changed = rebuild_conversation((P,), stored([], model="viejo", last=None), "nuevo")
    one = rebuild_conversation((P,), stored([row(1, user("a"))], last="user_message"), "m")

    assert cut.model_changed and cut.notice.endswith(
        "El modelo configurado difiere del de la sesión."
    )
    assert stop.cut_off and stop.notice == "Sesión reanudada: 6 mensajes. Se había interrumpido."
    assert changed.notice == (
        "Sesión reanudada: no tenía mensajes; se empieza de nuevo. "
        "El modelo configurado difiere del de la sesión."
    )
    assert one.notice == "Sesión reanudada: 1 mensaje."
    for resumed in (cut, stop, changed, one):
        text = resumed.notice
        assert "\n" not in text and SENTINEL not in text and "leer_archivo" not in text
        assert "s1" not in text


def test_a_stored_model_that_is_unknown_or_equal_is_not_a_change() -> None:
    same = rebuild_conversation((P,), stored(e1_rows(), model="m"), "m")
    unknown = rebuild_conversation((P,), stored(e1_rows(), model=None), "m")

    assert not same.model_changed and not unknown.model_changed


def test_it_is_deterministic_and_the_result_passes_the_structural_check() -> None:
    rows = [row(1, user("haz")), row(2, assistant("", C1, C2), event=False), row(3, tool(C1))]
    conversation = stored(rows, last="tool_finished")

    first = rebuild_conversation((P,), conversation, "m")
    second = rebuild_conversation((P,), conversation, "m")

    assert first == second and check_structure(first.history) is None
    assert conversation.messages == tuple(rows)
