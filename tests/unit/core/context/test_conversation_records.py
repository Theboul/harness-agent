"""Record of a message, redaction and the rejection text (HU-03-04 / T002)."""

from __future__ import annotations

import dataclasses

import pytest

from harness_agent.core import (
    ConversationSaveError,
    Message,
    MessageRecord,
    Role,
    StoredMessage,
    TokenUsage,
    ToolCall,
    ToolResult,
    clean_message,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
SECRET = "CLAVE-SENT-" + "01"
URL = "https://" + "usuario" + ":" + SECRET + "@servidor.example/repo.git"
HIDDEN = "<secreto oculto>"
HIDDEN_URL = f"https://{HIDDEN}@servidor.example/repo.git"
STANDARD = "[approval_rejected] Tool 'shell' was rejected by the user."


def test_records_are_immutable() -> None:
    record = MessageRecord(1, Message(Role.USER, "hola"), "e1")
    stored = StoredMessage(record, True)

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.position = 2  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        stored.covered = False  # type: ignore[misc]
    assert MessageRecord(1, Message(Role.USER, "x")).event_id is None
    assert StoredMessage(record).covered is None


def test_a_credential_in_the_content_the_result_and_a_nested_argument_is_hidden() -> None:
    call = ToolCall("c1", "shell", {"command": f"git clone {URL}", "lista": [URL, 3, True], "n": 7})
    assistant = Message(Role.ASSISTANT, f"clono {URL}", (call,), usage=TokenUsage(3, 4))
    tool = Message(
        Role.TOOL,
        f"salida {URL}",
        tool_result=ToolResult("c1", f"salida {URL}", True),
        is_external=True,
    )

    cleaned_assistant = clean_message(assistant)
    cleaned_tool = clean_message(tool)

    assert cleaned_assistant.content == f"clono {HIDDEN_URL}"
    arguments = cleaned_assistant.tool_calls[0].arguments
    assert arguments["command"] == f"git clone {HIDDEN_URL}"
    assert arguments["lista"] == [HIDDEN_URL, 3, True]
    assert arguments["n"] == 7 and cleaned_assistant.usage == TokenUsage(3, 4)
    assert cleaned_tool.tool_result is not None
    assert SECRET not in cleaned_tool.content and SECRET not in cleaned_tool.tool_result.content
    assert cleaned_tool.tool_result.is_error is True and cleaned_tool.is_external is True
    assert SECRET not in repr(cleaned_assistant) + repr(cleaned_tool)


def test_the_original_is_not_mutated_and_the_keys_are_untouched() -> None:
    call = ToolCall("c1", "shell", {URL: URL})
    message = Message(Role.ASSISTANT, "", (call,))

    cleaned = clean_message(message)

    assert message.tool_calls[0].arguments == {URL: URL}
    assert list(cleaned.tool_calls[0].arguments) == [URL]
    assert cleaned.tool_calls[0].arguments[URL] == HIDDEN_URL
    assert cleaned.tool_calls[0] is not call


def test_a_message_without_credentials_comes_back_equal() -> None:
    message = Message(Role.USER, "hola", is_external=False)

    assert clean_message(message) == message


def test_a_rejection_keeps_only_the_standard_text() -> None:
    reason = f"[approval_rejected] Tool 'shell' was rejected by the user. Reason: '{SENTINEL}'"
    message = Message(
        Role.TOOL, reason, tool_result=ToolResult("c1", reason, True), is_external=False
    )

    cleaned = clean_message(message, replacement=STANDARD)

    assert cleaned.content == STANDARD
    assert cleaned.tool_result == ToolResult("c1", STANDARD, True)
    assert SENTINEL not in repr(cleaned)
    assert cleaned.is_external is False


def test_without_a_replacement_a_text_that_looks_like_a_rejection_is_not_touched() -> None:
    text = "[approval_rejected] Tool 'x' was rejected by the user. (cita de un archivo)"
    message = Message(Role.TOOL, text, tool_result=ToolResult("c1", text, False))

    assert clean_message(message) == message


def test_the_save_error_has_the_fixed_message_and_no_cause() -> None:
    error = ConversationSaveError()

    assert str(error) == (
        "No se pudo guardar un mensaje de la conversación; la sesión no podrá reanudarse."
    )
    assert error.__cause__ is None and isinstance(error, Exception)
