"""SQLite store of the messages of a conversation, so a session can be resumed (HU-03-04).

Implements the ``MessageLog`` (write) and ``ResumeSource`` (read) protocols of ``core/context/`` on
the connection of the session store (never a connection of its own, so ``save_event`` and this
store share one database without locking each other out). The records arrive already clean (the
core hides the credentials and the rejection reason); this adapter holds no rule.

Writing is atomic (a batch is saved whole or not at all) and idempotent (a record already saved
with the same position and the same values is ignored; the same position with other values fails).
Reading joins each message with its event to know whether a summary covers it. Messages of the
engine never carry a value. The contract is ``specs/032-resume-session-by-id/contracts/
message_log_protocol.md``.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from harness_agent.adapters.storage.errors import SessionStoreError
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore
from harness_agent.core import (
    Message,
    MessageRecord,
    Role,
    StoredConversation,
    StoredMessage,
    TokenUsage,
    ToolCall,
    ToolResult,
)

_ENGINE_ERROR = "Error del almacén de mensajes."
_SERIALIZATION_ERROR = "Un mensaje de la conversación no se puede guardar."
_CONFLICT_ERROR = "Ya hay otro mensaje guardado en esa posición de la sesión."
_DAMAGED = "Un mensaje guardado está dañado y no se puede leer."
_MESSAGE_EVENTS = ("user_message", "assistant_message", "tool_finished")

_COLUMNS = "rol, contenido, llamadas, resultado_id, resultado_error, externo, uso, evento_id"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _values(record: MessageRecord) -> tuple[Any, ...]:
    """The columns of a record, in the order of ``_COLUMNS``. Raises on anything not JSON."""
    message = record.message
    calls = None
    if message.tool_calls:
        calls = json.dumps(
            [
                {"id": call.id, "name": call.name, "arguments": call.arguments}
                for call in message.tool_calls
            ],
            ensure_ascii=False,
        )
    result = message.tool_result
    usage = None
    if message.usage is not None:
        usage = json.dumps(
            {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            }
        )
    return (
        message.role.value,
        message.content,
        calls,
        None if result is None else result.call_id,
        None if result is None else int(result.is_error),
        int(message.is_external),
        usage,
        record.event_id,
    )


def _message(row: Sequence[Any]) -> Message:
    """The message of a row of ``_COLUMNS``; raises on anything damaged."""
    role, content, calls, result_id, result_error, external, usage, _ = row
    kind = Role(role)
    tool_calls: tuple[ToolCall, ...] = ()
    if calls is not None:
        tool_calls = tuple(
            ToolCall(str(item["id"]), str(item["name"]), dict(item["arguments"]))
            for item in json.loads(calls)
        )
    result = None
    if result_id is not None:
        result = ToolResult(str(result_id), content, bool(result_error))
    token_usage = None
    if usage is not None:
        data = json.loads(usage)
        token_usage = TokenUsage(int(data["input_tokens"]), int(data["output_tokens"]))
    return Message(
        kind,
        content,
        tool_calls,
        tool_result=result,
        usage=token_usage,
        is_external=bool(external),
    )


class SqliteMessageStore:
    """Writes the messages of a session and reads them back with what a resume needs.

    Args:
        store: The session store whose connection and tables are used.
        clock: Returns the current time; naive values are taken as UTC.
    """

    def __init__(
        self, store: SqliteSessionStore, *, clock: Callable[[], datetime] = _utc_now
    ) -> None:
        self._store = store
        self._clock = clock

    def append(self, session_id: str, records: Sequence[MessageRecord]) -> None:
        """Save the records of a session, all or none; a record already saved is ignored.

        Raises:
            SessionStoreError: The store is closed, a record cannot be represented, the session
                does not exist, a position is taken by a different message or the engine failed;
                nothing was written. The message is fixed and never carries content.
        """
        conn = self._store.connection()
        try:
            rows = [(record.position, _values(record)) for record in records]
        except (TypeError, ValueError, OverflowError):
            raise SessionStoreError(_SERIALIZATION_ERROR) from None
        stamp = _to_utc(self._clock()).isoformat()
        conflict = False
        try:
            conn.execute("BEGIN IMMEDIATE")
            for position, values in rows:
                saved = conn.execute(
                    f"SELECT {_COLUMNS} FROM mensajes WHERE sesion_id = ? AND posicion = ?",
                    (session_id, position),
                ).fetchone()
                if saved is None:
                    conn.execute(
                        "INSERT INTO mensajes (sesion_id, posicion, rol, contenido, llamadas, "
                        "resultado_id, resultado_error, externo, uso, evento_id, creado) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (session_id, position, *values, stamp),
                    )
                elif tuple(saved) != values:
                    conflict = True
                    break
            if conflict:
                conn.rollback()
            else:
                conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise SessionStoreError(_ENGINE_ERROR) from None
        except BaseException:
            conn.rollback()
            raise
        if conflict:
            raise SessionStoreError(_CONFLICT_ERROR)

    def last_position(self, session_id: str) -> int:
        """The highest position saved for the session, or 0 when there is none."""
        conn = self._store.connection()
        try:
            row = conn.execute(
                "SELECT COALESCE(MAX(posicion), 0) FROM mensajes WHERE sesion_id = ?",
                (session_id,),
            ).fetchone()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        return int(row[0])

    def load_conversation(self, session_id: str) -> StoredConversation | None:
        """Everything a resume needs to know about a session, or ``None`` if it does not exist.

        It only reads: it does not verify the seal of the criteria and it publishes nothing.

        Raises:
            SessionStoreError: The store is closed, the engine failed or a stored message is
                damaged.
        """
        conn = self._store.connection()
        snapshot = not conn.in_transaction
        try:
            if snapshot:
                conn.execute("BEGIN")
            return self._read(conn, session_id)
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        finally:
            if snapshot:
                conn.rollback()

    def _read(self, conn: sqlite3.Connection, session_id: str) -> StoredConversation | None:
        session = conn.execute("SELECT model FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if session is None:
            return None
        is_task = (
            conn.execute(
                "SELECT 1 FROM criterios WHERE sesion_id = ? LIMIT 1", (session_id,)
            ).fetchone()
            is not None
            or conn.execute(
                "SELECT 1 FROM contexto_esencial WHERE sesion_id = ? LIMIT 1", (session_id,)
            ).fetchone()
            is not None
        )
        rows = conn.execute(
            "SELECT m.posicion, m.rol, m.contenido, m.llamadas, m.resultado_id, "
            "m.resultado_error, m.externo, m.uso, m.evento_id, e.id, e.compacted_by "
            "FROM mensajes m LEFT JOIN events e "
            "ON e.id = m.evento_id AND e.session_id = m.sesion_id "
            "WHERE m.sesion_id = ? ORDER BY m.posicion",
            (session_id,),
        ).fetchall()
        messages: list[StoredMessage] = []
        for row in rows:
            try:
                message = _message(row[1:9])
            except (ValueError, TypeError, KeyError, AttributeError):
                raise SessionStoreError(_DAMAGED) from None
            covered = None if row[9] is None else row[10] is not None
            messages.append(StoredMessage(MessageRecord(row[0], message, row[8]), covered))
        summary = conn.execute(
            "SELECT texto FROM resumenes WHERE sesion_id = ? "
            "ORDER BY evento_hasta DESC, rowid DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        marks = ", ".join("?" for _ in _MESSAGE_EVENTS)
        without_row = conn.execute(
            f"SELECT count(*) FROM events e WHERE e.session_id = ? AND e.type IN ({marks}) "
            "AND NOT EXISTS (SELECT 1 FROM mensajes m "
            "WHERE m.sesion_id = e.session_id AND m.evento_id = e.id)",
            (session_id, *_MESSAGE_EVENTS),
        ).fetchone()
        last = conn.execute(
            "SELECT type FROM events WHERE session_id = ? AND type <> 'context_compacted' "
            "ORDER BY seq DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return StoredConversation(
            session_id,
            session[0],
            is_task,
            tuple(messages),
            None if summary is None else str(summary[0]),
            int(without_row[0]),
            None if last is None else str(last[0]),
        )
