"""SQLite archive of the automatic compaction: summaries and the events they cover (HU-02-03).

Implements the ``CompactionStore`` protocol of ``core/context/`` on the connection of the session
store (never a connection of its own, so ``save_event`` and a compaction share one database
without locking each other out). ``commit_compaction`` runs in one transaction: it saves the
summary, marks the events it covers and stores the ``context_compacted`` event, or does nothing.

Marking only writes ``events.compacted_by``; the content, type, order and date of an event never
change and no event is deleted. Messages of the engine never carry the text of the summary. The
rules are in ``specs/030-automatic-context-compaction/contracts/store_protocol.md``.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone

from harness_agent.adapters.storage.errors import DuplicateEvent, SessionStoreError
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore
from harness_agent.core import (
    CompactionCommit,
    CompactionReceipt,
    Event,
    EventType,
    MessageEvent,
)

_ENGINE_ERROR = "Error del archivo de compactación."
_DUPLICATE_ERROR = "Ya existe un evento con ese identificador."
_MESSAGE_KINDS = {
    EventType.USER_MESSAGE.value: "user",
    EventType.ASSISTANT_MESSAGE.value: "assistant",
    EventType.TOOL_FINISHED.value: "tool",
}
_COVERABLE = "session_id = ? AND seq > ? AND seq <= ? AND compacted_by IS NULL AND type != ?"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SqliteCompactionArchive:
    """Reads the message events of a session and covers a range of them with a summary.

    Args:
        store: The session store whose connection and tables are used.
        clock: Returns the current time; naive values are taken as UTC.
        redact: Cleans the summary text before it is stored (HU-10-02); none by default.
    """

    def __init__(
        self,
        store: SqliteSessionStore,
        *,
        clock: Callable[[], datetime] = _utc_now,
        redact: Callable[[str], str] | None = None,
    ) -> None:
        self._redact = redact
        self._store = store
        self._clock = clock

    def message_events(self, session_id: str) -> list[MessageEvent]:
        """The user, assistant and tool events of the session, in order, and if each is covered.

        Raises:
            SessionStoreError: The store is closed or the engine failed.
        """
        conn = self._store.connection()
        kinds = tuple(_MESSAGE_KINDS)
        try:
            rows = conn.execute(
                "SELECT seq, type, compacted_by FROM events "
                f"WHERE session_id = ? AND type IN ({', '.join('?' for _ in kinds)}) ORDER BY seq",
                (session_id, *kinds),
            ).fetchall()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        return [MessageEvent(seq, _MESSAGE_KINDS[kind], by is not None) for seq, kind, by in rows]

    def commit_compaction(self, commit: CompactionCommit) -> CompactionReceipt | None:
        """Save the summary, cover the events and store ``context_compacted``, all or nothing.

        Covers the events of the session after ``protected_seq`` and up to ``through_seq`` that
        no earlier summary covers, whatever their type except ``context_compacted``. Returns
        ``None``, having written nothing, if there is none.

        Raises:
            DuplicateEvent: The identifier of the new event is already an event.
            SessionStoreError: The store is closed or the engine failed; nothing was written.
        """
        conn = self._store.connection()
        covered = EventType.CONTEXT_COMPACTED.value
        bounds = (commit.session_id, commit.protected_seq, commit.through_seq, covered)
        now = _to_utc(self._clock())
        try:
            conn.execute("BEGIN IMMEDIATE")
            if (
                conn.execute("SELECT 1 FROM events WHERE id = ?", (commit.event_id,)).fetchone()
                is not None
            ):
                raise DuplicateEvent(_DUPLICATE_ERROR)
            rows = conn.execute(
                f"SELECT seq FROM events WHERE {_COVERABLE} ORDER BY seq", bounds
            ).fetchall()
            if not rows:
                conn.rollback()
                return None
            desde, hasta, count = rows[0][0], rows[-1][0], len(rows)
            conn.execute(
                "INSERT INTO resumenes (id, sesion_id, evento_desde, evento_hasta, texto, creado) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    commit.summary_id,
                    commit.session_id,
                    desde,
                    hasta,
                    commit.summary if self._redact is None else self._redact(commit.summary),
                    now.isoformat(),
                ),
            )
            conn.execute(
                f"UPDATE events SET compacted_by = ? WHERE {_COVERABLE}",
                (commit.summary_id, *bounds),
            )
            payload = {"desde": desde, "hasta": hasta, "eventos": count}
            seq = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id = ?",
                (commit.session_id,),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO events (id, session_id, seq, type, content, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    commit.event_id,
                    commit.session_id,
                    seq,
                    covered,
                    json.dumps(payload),
                    now.isoformat(),
                ),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise SessionStoreError(_ENGINE_ERROR) from None
        except BaseException:
            conn.rollback()
            raise
        event = Event(commit.event_id, commit.session_id, EventType.CONTEXT_COMPACTED, now, payload)
        return CompactionReceipt(commit.summary_id, desde, hasta, count, event)
