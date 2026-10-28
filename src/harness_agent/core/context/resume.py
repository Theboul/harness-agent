"""Resuming a session: the identifier, what is read back and the rebuilt context (HU-03-04).

Everything here is pure: the stored conversation arrives as plain data (``StoredConversation``)
from a ``ResumeSource`` and the result is a list of messages. The contract is
``specs/032-resume-session-by-id/contracts/rebuild_rules.md``. Every failure is a ``ResumeError``
with a fixed message in Spanish that never repeats the identifier, the history or the tasks.
"""

from __future__ import annotations

import string
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Protocol

from harness_agent.core.context.conversation import StoredMessage
from harness_agent.core.context.errors import (
    AlreadyCurrentSession,
    ConversationInconsistent,
    InvalidSessionId,
    SessionDetailMissing,
    TaskSessionNotResumable,
    UnknownSession,
)
from harness_agent.core.context.summary import frame_summary
from harness_agent.core.entities import Message, Role, ToolResult

MAX_ID_CHARS = 128
_ID_CHARS = frozenset(string.ascii_letters + string.digits + "._-")


def check_session_id(text: object) -> str:
    """The identifier written by the person, without the spaces around it.

    Raises:
        InvalidSessionId: It is empty (the usage line), not a text, longer than ``MAX_ID_CHARS``
            or has a character other than letters, digits, ``.``, ``_`` and ``-`` (line breaks,
            control and hidden characters included). The message never repeats the text.
    """
    if not isinstance(text, str):
        raise InvalidSessionId()
    value = text.strip(" ")
    if not value:
        raise InvalidSessionId(usage=True)
    if len(value) > MAX_ID_CHARS or any(char not in _ID_CHARS for char in value):
        raise InvalidSessionId()
    return value


@dataclass(frozen=True)
class StoredConversation:
    """What a session left in the store, as plain data.

    Attributes:
        session_id: The session.
        model: The model recorded when the session was created, or ``None``.
        is_task: Whether the session has a task (criteria or essential context stored).
        messages: The stored messages in order, each with whether a summary covers its event.
        summary: The text of the newest summary, or ``None`` if the session was never compacted.
        events_without_row: Message events of the session that no stored message points at.
        last_event_type: The type of the last event of the session, ignoring compactions.
    """

    session_id: str
    model: str | None
    is_task: bool
    messages: tuple[StoredMessage, ...]
    summary: str | None
    events_without_row: int
    last_event_type: str | None


class ResumeSource(Protocol):
    """Where the conversation of a session is read from (implemented by the SQLite adapter)."""

    def load_conversation(self, session_id: str) -> StoredConversation | None:
        """The stored conversation of the session, or ``None`` if there is no such session."""
        ...


def check_structure(messages: Sequence[Message]) -> str | None:
    """Why ``messages`` would not be accepted by the loop, or ``None`` if they would.

    It mirrors the structural rules the loop applies to the history it receives (it cannot import
    the loop): ``SYSTEM`` only as a contiguous prefix, non-empty and unique tool call ids, every
    group of calls answered before anything else follows, and no result without its call. The
    reason is a short code and never repeats any content.
    """
    pending: set[str] = set()
    seen: set[str] = set()
    for position, message in enumerate(messages):
        role = message.role
        if role is Role.SYSTEM and position > 0 and messages[position - 1].role is not Role.SYSTEM:
            return "system_not_in_prefix"
        if pending and role is not Role.TOOL:
            return "calls_without_result"
        if message.tool_calls and role is not Role.ASSISTANT:
            return "calls_outside_assistant"
        if message.tool_result is not None and role is not Role.TOOL:
            return "result_outside_tool"
        if role is Role.TOOL:
            if message.tool_result is None:
                return "tool_without_result"
            if message.tool_result.call_id not in pending:
                return "result_without_call"
            pending.discard(message.tool_result.call_id)
        for call in message.tool_calls:
            if not call.id or call.id in seen:
                return "call_id_empty_or_repeated"
            seen.add(call.id)
            pending.add(call.id)
    return "calls_without_result" if pending else None


SYNTHETIC_RESULT_TEXT = (
    "[tool_interrupted] La ejecución se interrumpió antes de obtener el resultado; "
    "verifique el estado antes de repetirla."
)


@dataclass(frozen=True)
class Resumed:
    """The context of a resumed session and what the composition needs to continue it.

    Attributes:
        history: The prefix and the rebuilt messages (the synthetic results included).
        saved_count: How many messages at the start of ``history`` are saved; the rest are the
            synthetic results, which are published as real ones on the first request.
        closed_calls: ``(call_id, tool name)`` of each call that got a synthetic result, in order.
        message_count: Messages of ``history`` without the prefix.
        has_summary: Whether the context starts from a summary.
        empty: Whether the session had no messages.
        cut_off: Whether the session ended in the middle of a turn or was interrupted.
        model_changed: Whether the model recorded for the session differs from the current one.
        next_position: Position of the next message to be saved.
        notice: The one line of status for the person.
    """

    history: tuple[Message, ...]
    saved_count: int
    closed_calls: tuple[tuple[str, str], ...]
    message_count: int
    has_summary: bool
    empty: bool
    cut_off: bool
    model_changed: bool
    next_position: int
    notice: str


def _plural(count: int, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _coverage(messages: Sequence[StoredMessage]) -> list[bool]:
    """Whether a summary covers each message: its own event says so; a message with no event
    follows the next message that has one (none after it: not covered)."""
    covered = [False] * len(messages)
    following = False
    for index in range(len(messages) - 1, -1, -1):
        own = messages[index].covered
        if own is not None:
            following = own
        covered[index] = following
    return covered


def _close_calls(history: list[Message]) -> tuple[list[Message], tuple[tuple[str, str], ...]]:
    """The synthetic results for the calls that have none at the very end of ``history``."""
    start = len(history)
    while start > 0 and history[start - 1].role is Role.TOOL:
        start -= 1
    if start == 0 or not history[start - 1].tool_calls:
        return [], ()
    answered = {m.tool_result.call_id for m in history[start:] if m.tool_result is not None}
    missing = [call for call in history[start - 1].tool_calls if call.id not in answered]
    closing = [
        Message(
            Role.TOOL,
            SYNTHETIC_RESULT_TEXT,
            tool_result=ToolResult(call.id, SYNTHETIC_RESULT_TEXT, True),
        )
        for call in missing
    ]
    return closing, tuple((call.id, call.name) for call in missing)


def rebuild_conversation(
    prefix: Sequence[Message], stored: StoredConversation, current_model: str
) -> Resumed:
    """The context the session had when the process ended: prefix, request, summary and the rest.

    Raises:
        ConversationInconsistent: The stored messages do not form a coherent conversation.
    """
    rows = stored.messages
    changed = stored.model not in (None, current_model)
    note = " El modelo configurado difiere del de la sesión." if changed else ""
    if not rows:
        if stored.summary is not None:
            raise ConversationInconsistent()
        return Resumed(
            tuple(prefix), len(prefix), (), 0, False, True, False, changed, 1,
            "Sesión reanudada: no tenía mensajes; se empieza de nuevo." + note,
        )  # fmt: skip
    first = rows[0]
    if (
        first.record.message.role is not Role.USER
        or first.record.message.is_external
        or first.covered is True
    ):
        raise ConversationInconsistent()
    covered = [index for index, flag in enumerate(_coverage(rows)) if flag and index > 0]
    has_summary = stored.summary is not None
    if bool(covered) != has_summary or covered != list(range(1, len(covered) + 1)):
        raise ConversationInconsistent()
    history = [*prefix, first.record.message]
    if stored.summary is not None:
        history.append(frame_summary(stored.summary))
    history.extend(row.record.message for row in rows[len(covered) + 1 :])
    closing, closed = _close_calls(history)
    history.extend(closing)
    if check_structure(history) is not None:
        raise ConversationInconsistent()
    count = len(history) - len(prefix)
    cut_off = bool(closed) or stored.last_event_type == "interrupted"
    text = "Sesión reanudada: " + _plural(count, "mensaje", "mensajes")
    text += " en el contexto (con resumen)." if has_summary else "."
    if closed:
        calls = _plural(len(closed), "llamada", "llamadas")
        verb = "cerró" if len(closed) == 1 else "cerraron"
        text += f" Terminó de forma abrupta; se {verb} {calls} sin resultado."
    elif cut_off:
        text += " Se había interrumpido."
    return Resumed(
        tuple(history),
        len(history) - len(closing),
        closed,
        count,
        has_summary,
        False,
        cut_off,
        changed,
        rows[-1].record.position + 1,
        text + note,
    )


def resume_session(
    source: ResumeSource,
    text: object,
    *,
    prefix: Sequence[Message],
    current_model: str,
    current_session_id: str,
    known_incomplete: Collection[str] = frozenset(),
) -> Resumed:
    """Validate the identifier the person wrote, read that session and rebuild its context.

    The checks that do not need the store come first and never read it: the identifier, whether
    it is the current session and whether its saving failed in this run (``known_incomplete``).

    Raises:
        InvalidSessionId: The identifier is empty or not valid.
        AlreadyCurrentSession: It is the session that is already running.
        SessionDetailMissing: The saving of its messages failed or never happened.
        UnknownSession: No session has that identifier.
        TaskSessionNotResumable: The session has a task.
        ConversationInconsistent: The stored messages are not coherent.
    """
    session_id = check_session_id(text)
    if session_id == current_session_id:
        raise AlreadyCurrentSession()
    if session_id in known_incomplete:
        raise SessionDetailMissing()
    stored = source.load_conversation(session_id)
    if stored is None:
        raise UnknownSession()
    if stored.is_task:
        raise TaskSessionNotResumable()
    if stored.events_without_row > 0:
        raise SessionDetailMissing()
    return rebuild_conversation(prefix, stored, current_model)
