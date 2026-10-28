"""The identifier, the fixed errors of resuming and the structural check (HU-03-04 / T004)."""

from __future__ import annotations

import pytest

from harness_agent.core import (
    AlreadyCurrentSession,
    ConversationInconsistent,
    ConversationSaveError,
    InvalidSessionId,
    Message,
    ResumeError,
    Role,
    SessionDetailMissing,
    TaskSessionNotResumable,
    ToolCall,
    ToolResult,
    UnknownSession,
    check_session_id,
    check_structure,
)
from harness_agent.core.loop import AgentLoop

SENTINEL = "VALOR-DE-PRUEBA-123"
USAGE = "Uso: /reanudar <identificador de la sesión>."
INVALID = "El identificador de sesión no es válido."


def test_an_empty_identifier_gets_the_usage_line() -> None:
    for text in ("", "   "):
        with pytest.raises(InvalidSessionId) as caught:
            check_session_id(text)
        assert str(caught.value) == USAGE


@pytest.mark.parametrize(
    "text",
    [
        "../x",
        "a" * 129,
        "con\nsalto",
        "\n",
        "tab\tulador",
        "con espacio",
        "ctrl" + chr(27),
        "cero" + chr(0x200B) + "ancho",
        "inv" + chr(0x202E) + "ertido",
        "ñandú",
        SENTINEL + "/otra",
    ],
)
def test_an_invalid_identifier_gets_the_not_valid_line_without_the_text(text: str) -> None:
    with pytest.raises(InvalidSessionId) as caught:
        check_session_id(text)

    assert str(caught.value) == INVALID and SENTINEL not in str(caught.value)


def test_a_value_that_is_not_a_text_is_not_valid() -> None:
    with pytest.raises(InvalidSessionId) as caught:
        check_session_id(7)

    assert str(caught.value) == INVALID


def test_a_good_identifier_comes_back_without_outer_spaces() -> None:
    assert check_session_id("a-B_9.x") == "a-B_9.x"
    assert check_session_id("  7f3a91  ") == "7f3a91"
    assert check_session_id("a" * 128) == "a" * 128
    assert check_session_id("0b2c7c1e-5d4a-4f3b-9a60-1e2f3a4b5c6d")


def test_the_messages_are_exactly_the_ones_of_the_contract() -> None:
    assert str(AlreadyCurrentSession()) == "Esa ya es la sesión actual."
    assert str(UnknownSession()) == "No existe una sesión con ese identificador."
    assert str(TaskSessionNotResumable()) == "Las sesiones de tarea no se pueden reanudar todavía."
    assert str(SessionDetailMissing()) == (
        "Esa sesión se guardó sin el detalle de sus mensajes y no se puede reanudar."
    )
    assert str(ConversationInconsistent()) == (
        "Los mensajes guardados de la sesión no son coherentes y no se puede reanudar."
    )
    assert str(ConversationSaveError()) == (
        "No se pudo guardar un mensaje de la conversación; la sesión no podrá reanudarse."
    )


def test_every_error_of_resuming_is_a_resume_error_and_none_carries_a_value() -> None:
    errors = [
        InvalidSessionId(),
        InvalidSessionId(usage=True),
        AlreadyCurrentSession(),
        UnknownSession(),
        TaskSessionNotResumable(),
        SessionDetailMissing(),
        ConversationInconsistent(),
    ]
    for error in errors:
        assert isinstance(error, ResumeError) and SENTINEL not in repr(error) + str(error)
        assert error.__cause__ is None and error.args == (str(error),)
    assert not isinstance(ConversationSaveError(), ResumeError)


# --- the structural check ---------------------------------------------------------------------


def calls(*ids: str) -> tuple[ToolCall, ...]:
    return tuple(ToolCall(i, "leer_archivo", {}) for i in ids)


def result(call_id: str) -> Message:
    return Message(Role.TOOL, "ok", tool_result=ToolResult(call_id, "ok"))


VALID = [
    [Message(Role.SYSTEM, "p"), Message(Role.USER, "a"), Message(Role.ASSISTANT, "b")],
    [
        Message(Role.SYSTEM, "p"),
        Message(Role.SYSTEM, "q"),
        Message(Role.USER, "a"),
        Message(Role.ASSISTANT, "", calls("c1", "c2")),
        result("c2"),
        result("c1"),
        Message(Role.ASSISTANT, "fin"),
    ],
    [Message(Role.USER, "a"), Message(Role.USER, "b")],
    [],
]
INVALID_HISTORIES = [
    [Message(Role.USER, "a"), Message(Role.SYSTEM, "tarde")],
    [Message(Role.USER, "a"), Message(Role.ASSISTANT, "", calls("c1")), Message(Role.USER, "b")],
    [Message(Role.USER, "a"), Message(Role.ASSISTANT, "", calls("c1"))],
    [Message(Role.USER, "a"), result("c9")],
    [
        Message(Role.ASSISTANT, "", calls("c1")),
        result("c1"),
        Message(Role.ASSISTANT, "", calls("c1")),
        result("c1"),
    ],
    [Message(Role.ASSISTANT, "", calls("")), result("")],
    [Message(Role.TOOL, "sin resultado")],
    [Message(Role.USER, "a", tool_calls=calls("c1"))],
    [Message(Role.USER, "a", tool_result=ToolResult("c1", "x"))],
    [
        Message(Role.ASSISTANT, "", calls("c1")),
        result("c1"),
        result("c1"),
    ],
]


@pytest.mark.parametrize("history", VALID)
def test_a_valid_history_has_no_problem(history: list[Message]) -> None:
    assert check_structure(history) is None


@pytest.mark.parametrize("history", INVALID_HISTORIES)
def test_an_invalid_history_is_named_without_any_content(history: list[Message]) -> None:
    problem = check_structure(history)

    assert isinstance(problem, str) and problem
    assert "ok" not in problem and "sin resultado" not in problem


@pytest.mark.parametrize("history", [*VALID, *INVALID_HISTORIES])
def test_it_agrees_with_the_validation_of_the_loop(history: list[Message]) -> None:
    verdict = check_structure(history)
    try:
        AgentLoop._check_history(history)  # noqa: SLF001 - the rules we mirror
        loop_accepts = True
    except Exception:
        loop_accepts = False

    assert (verdict is None) is loop_accepts
