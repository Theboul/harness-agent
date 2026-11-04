"""SQLite store of the persistent memory (HU-04-01).

Implements the ``MemoryStore`` port of the core and the small ``MemoryLog`` protocol of
``core/context/`` on the connection of the session store (never one of its own). The ``memorias``
table has no foreign key to sessions or events, so deleting or compacting a session cannot touch it.

The text arrives already clean and within its cap (the core does that); this adapter holds no rule
beyond the number of entries, which has to be checked inside the same transaction as the insert.
Messages of the engine never carry a key or a text.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone

from harness_agent.adapters.storage.errors import SessionStoreError
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore
from harness_agent.core import (
    DEFAULT_MAX_ENTRIES,
    MemoryFull,
    MemoryItem,
    MemoryStore,
    estimate_text,
)

_ENGINE_ERROR = "Error del almacén de la memoria."
_DAMAGED = "Una entrada guardada de la memoria está dañada y no se puede leer."


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SqliteMemoryStore(MemoryStore):
    """Keeps the entries of the persistent memory, one per key, most recently updated first.

    Args:
        store: The session store whose connection and tables are used.
        max_entries: Entries the table holds; a new key over it raises ``MemoryFull``.
        clock: Returns the current time; naive values are taken as UTC.
    """

    def __init__(
        self,
        store: SqliteSessionStore,
        *,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._store = store
        self._max_entries = max_entries
        self._clock = clock

    def remember(self, key: str, content: str) -> None:
        """Save the entry, or replace the one of the same key (it becomes the most recent).

        Raises:
            MemoryFull: The key is new and the table already holds ``max_entries``.
            SessionStoreError: The store is closed or the engine failed; nothing was written.
        """
        conn = self._store.connection()
        stamp = _to_utc(self._clock()).isoformat()
        full = False
        try:
            conn.execute("BEGIN IMMEDIATE")
            exists = conn.execute("SELECT 1 FROM memorias WHERE clave = ?", (key,)).fetchone()
            if exists is not None:
                conn.execute(
                    "UPDATE memorias SET contenido = ?, actualizada = ? WHERE clave = ?",
                    (content, stamp, key),
                )
                conn.commit()
            elif conn.execute("SELECT COUNT(*) FROM memorias").fetchone()[0] >= self._max_entries:
                conn.rollback()
                full = True
            else:
                conn.execute(
                    "INSERT INTO memorias (clave, contenido, creada, actualizada) "
                    "VALUES (?, ?, ?, ?)",
                    (key, content, stamp, stamp),
                )
                conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise SessionStoreError(_ENGINE_ERROR) from None
        except BaseException:
            conn.rollback()
            raise
        if full:
            raise MemoryFull()

    def forget(self, key: str) -> bool:
        """Delete the entry of ``key``; whether there was one."""
        conn = self._store.connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            deleted = conn.execute("DELETE FROM memorias WHERE clave = ?", (key,)).rowcount
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise SessionStoreError(_ENGINE_ERROR) from None
        except BaseException:
            conn.rollback()
            raise
        return deleted > 0

    def recent(self) -> list[MemoryItem]:
        """Every entry, the most recently updated first (ties: the newest row first)."""
        conn = self._store.connection()
        try:
            rows = conn.execute(
                "SELECT clave, contenido, creada, actualizada FROM memorias "
                "ORDER BY actualizada DESC, id DESC"
            ).fetchall()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        damaged = False
        found: list[MemoryItem] = []
        for key, content, created, updated in rows:
            try:
                found.append(
                    MemoryItem(
                        key,
                        content,
                        datetime.fromisoformat(created),
                        datetime.fromisoformat(updated),
                    )
                )
            except ValueError:
                damaged = True
        if damaged:
            raise SessionStoreError(_DAMAGED)
        return found

    # The ``MemoryStore`` port of the core (HU-00-01): the same operations under its names.

    def save(self, key: str, content: str) -> None:
        """Port name of ``remember``."""
        self.remember(key, content)

    def search(self, token_budget: int) -> list[MemoryItem]:
        """The most recent entries whose texts add up to at most ``token_budget`` tokens."""
        chosen: list[MemoryItem] = []
        used = 0
        for item in self.recent():
            used += estimate_text(item.content)
            if used > token_budget:
                break
            chosen.append(item)
        return chosen

    def delete(self, key: str) -> bool:
        """Port name of ``forget``."""
        return self.forget(key)
