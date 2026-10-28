"""The messages of a conversation, kept so that a session can be resumed (HU-03-04).

The events the loop publishes do not carry what is needed to rebuild the history (tool arguments,
tool results, the external mark, the usage, messages with no event). ``ConversationCapture`` is
subscribed by the composition root: when the bus publishes the event of a message it reads that
message from the history in memory and hands it, already clean, to a ``MessageLog``. The contract is
``specs/032-resume-session-by-id/contracts/capture_rules.md``.

Nothing here reads a file, the environment or the terminal, and the loop is not touched: the
collaborators come by constructor.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from harness_agent.core.context.cut import is_real
from harness_agent.core.context.errors import ConversationSaveError
from harness_agent.core.entities import Message, Role, ToolCall, ToolResult
from harness_agent.core.events import Event, EventType
from harness_agent.core.redaction import hide_url_credentials


@dataclass(frozen=True)
class MessageRecord:
    """One message ready to be stored: already clean, with its place in the session.

    Attributes:
        position: Place of the message in its session, from 1.
        message: The message, with the credentials of URLs hidden and no rejection reason.
        event_id: Identifier of the event that triggered the saving of this message, or ``None``
            for a message with no event of its own (an answer that only asks for tools, an empty
            answer).
    """

    position: int
    message: Message
    event_id: str | None = None


@dataclass(frozen=True)
class StoredMessage:
    """A stored message as it is read back.

    Attributes:
        record: The message and its place.
        covered: Whether a summary covers the event of the message; ``None`` when the message has
            no event stored (it never had one, or the process stopped before saving it).
    """

    record: MessageRecord
    covered: bool | None = None


class MessageLog(Protocol):
    """Where the messages of a session are written (implemented by the SQLite adapter)."""

    def append(self, session_id: str, records: Sequence[MessageRecord]) -> None:
        """Save the records, all or none. A record already saved with the same position and the
        same values is ignored; the same position with other values fails."""
        ...

    def last_position(self, session_id: str) -> int:
        """The highest position saved for the session, or 0 when there is none."""
        ...


def _hide(value: Any) -> Any:
    """``value`` with the credentials of URLs hidden in every text, at any depth."""
    if isinstance(value, str):
        return hide_url_credentials(value)
    if isinstance(value, list):
        return [_hide(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_hide(item) for item in value)
    if isinstance(value, Mapping):
        return {key: _hide(item) for key, item in value.items()}
    return value


def clean_message(message: Message, *, replacement: str | None = None) -> Message:
    """A copy of ``message`` that is safe to store.

    The credentials of URLs are hidden in the content, in the content of the tool result and in
    every text of the arguments (the keys and any value that is not a text stay as they are).
    With ``replacement`` the content of the message and of its tool result become that text: it is
    how a rejection is stored without the reason the person gave.
    """
    content = hide_url_credentials(message.content) if replacement is None else replacement
    calls = tuple(
        ToolCall(call.id, call.name, _hide(call.arguments)) for call in message.tool_calls
    )
    result = message.tool_result
    if result is not None:
        result_content = (
            hide_url_credentials(result.content) if replacement is None else replacement
        )
        result = ToolResult(result.call_id, result_content, result.is_error)
    return dataclasses.replace(message, content=content, tool_calls=calls, tool_result=result)


_EXPECTED_ROLE = {
    EventType.USER_MESSAGE: Role.USER,
    EventType.ASSISTANT_MESSAGE: Role.ASSISTANT,
}
_TRIGGERS = frozenset(
    {
        EventType.USER_MESSAGE,
        EventType.ASSISTANT_MESSAGE,
        EventType.TOOL_REQUESTED,
        EventType.TOOL_FINISHED,
    }
)
_REJECTED = "approval_rejected"


class ConversationCapture:
    """Saves each real message of the conversation when the bus publishes its event.

    The composition root subscribes ``on_event`` to the four event types that follow a message
    being added to the history, **before** the event recorder, so a cut leaves a message with no
    event and never an event with no message. The messages are followed by identity (``is``), not
    by position or equality, so a compaction that replaces the view in place does not confuse it.
    Until ``bind`` hands it the history it ignores every event.

    Args:
        log: Where the records are written.
        warn: Writes one line of warning for the person.
        rejected_text: The standard text of a rejection for a tool name (no reason): the one the
            loop writes when the person gave none.
    """

    def __init__(
        self,
        log: MessageLog,
        *,
        warn: Callable[[str], None],
        rejected_text: Callable[[str], str],
    ) -> None:
        self._log = log
        self._warn = warn
        self._rejected_text = rejected_text
        self._session_id: str | None = None
        self._history: list[Message] | None = None
        self._last: Message | None = None
        self._next = 1
        self._failed = False
        self._held: list[Message] = []
        self._incomplete: frozenset[str] = frozenset()

    @property
    def session_id(self) -> str | None:
        """The session the capture writes to, or ``None`` while it is not bound."""
        return self._session_id

    @property
    def incomplete_sessions(self) -> frozenset[str]:
        """The sessions whose saving failed in this run: they cannot be resumed."""
        return self._incomplete

    def bind(
        self, session_id: str, history: list[Message], next_position: int, saved_count: int
    ) -> None:
        """Start following ``history`` for ``session_id``.

        Args:
            session_id: The session the records belong to.
            history: The list the session keeps in memory; the capture reads it, never changes it.
            next_position: Position of the next record.
            saved_count: How many messages at the start of ``history`` are already saved (or are
                not conversation): the last real one among them is the last one saved. The real
                ones after them (the results that close the calls a cut left open) are held: only
                their own event saves them, never the end of a turn.
        """
        self._session_id = session_id
        self._history = history
        self._next = next_position
        self._failed = session_id in self._incomplete  # a lost message is never made up for
        saved = [message for message in history[:saved_count] if is_real(message)]
        self._last = saved[-1] if saved else None
        self._held = [message for message in history[saved_count:] if is_real(message)]

    def on_event(self, event: Event) -> None:
        """Save what is pending when ``event`` is the event of a message (or of a tool request).

        Raises:
            ConversationSaveError: The saving failed or the state is not coherent. The failure is
                sticky: from then on nothing more is written for this session (so a later message
                can never be saved after a lost one), and the person is told once.
        """
        if event.type not in _TRIGGERS or self._history is None:
            return
        if event.session_id != self._session_id:
            return
        self._guarded(lambda: self._on_event(event))

    def flush(self) -> None:
        """Save what is still pending, with no event (an empty answer, the end of a turn)."""
        if self._history is None:
            return
        self._guarded(self._flush)

    def _on_event(self, event: Event) -> None:
        pending = self._pending()
        if not pending:
            return
        link = self._link_index(event, pending)
        stop = link + 1 if event.type is EventType.TOOL_FINISHED else len(pending)
        rejected = event.type is EventType.TOOL_FINISHED and (
            event.payload.get("category") == _REJECTED
        )
        self._save(pending[:stop], event.id if link >= 0 else None, link, rejected, event)

    def _flush(self) -> None:
        pending = self._pending()
        for index, message in enumerate(pending):
            if any(message is held for held in self._held):
                pending = pending[:index]  # a held result waits for its own event
                break
        if pending:
            self._save(pending, None, -1, False, None)

    def _guarded(self, action: Callable[[], None]) -> None:
        """Run ``action``; any failure becomes the fixed error, outside the handler (no cause)."""
        if self._failed:
            raise ConversationSaveError()
        failed = False
        try:
            action()
        except Exception:
            failed = True
        if not failed:
            return
        self._failed = True
        assert self._session_id is not None
        self._incomplete = self._incomplete | {self._session_id}
        notice = str(ConversationSaveError())
        try:
            self._warn(notice)
        except Exception:
            pass  # the error below still reaches the caller; the notice is only a courtesy
        raise ConversationSaveError()

    def _pending(self) -> list[Message]:
        """The real messages after the last one saved."""
        history = self._history
        assert history is not None
        start = 0
        if self._last is not None:
            for index in range(len(history) - 1, -1, -1):
                if history[index] is self._last:
                    start = index + 1
                    break
            else:
                raise ConversationSaveError()
        return [message for message in history[start:] if is_real(message)]

    @staticmethod
    def _link_index(event: Event, pending: list[Message]) -> int:
        """Index in ``pending`` of the message this event stands for, or -1 if it has none."""
        if event.type is EventType.TOOL_REQUESTED:
            return -1
        if event.type is EventType.TOOL_FINISHED:
            call_id = event.payload.get("call_id")
            for index, message in enumerate(pending):
                result = message.tool_result
                if message.role is Role.TOOL and result is not None and result.call_id == call_id:
                    return index
            raise ConversationSaveError()
        if pending[-1].role is not _EXPECTED_ROLE[event.type]:
            raise ConversationSaveError()
        return len(pending) - 1

    def _save(
        self,
        batch: list[Message],
        event_id: str | None,
        link: int,
        rejected: bool,
        event: Event | None,
    ) -> None:
        assert self._session_id is not None
        records: list[MessageRecord] = []
        for index, message in enumerate(batch):
            result = message.tool_result
            if result is not None and result.content != message.content:
                raise ConversationSaveError()
            replacement = None
            if rejected and index == link:
                name = event.payload.get("name") if event is not None else None
                if not isinstance(name, str):
                    raise ConversationSaveError()
                replacement = self._rejected_text(name)
            records.append(
                MessageRecord(
                    self._next + index,
                    clean_message(message, replacement=replacement),
                    event_id if index == link else None,
                )
            )
        self._log.append(self._session_id, records)
        self._next += len(records)
        self._last = batch[-1]
        self._held = [held for held in self._held if all(held is not m for m in batch)]
