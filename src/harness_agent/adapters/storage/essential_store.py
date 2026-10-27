"""SQLite store of the essential context of a task (HU-02-06.1).

Implements the read-only ``EssentialSource`` protocol of ``core/context/`` on the connection of the
session store (never a connection of its own, so ``save_event`` and this store share one database
without locking each other out). The elements are written **once**, in one transaction, when the
session of the task is created, and only read afterwards: there is no way to update or delete them.

The values arrive already clean (the core does that); this adapter holds no rule. Messages of the
engine never carry a value. The contract is in ``specs/031-essential-context-block/contracts/
essential_store.md``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from harness_agent.adapters.storage.errors import SessionStoreError
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore
from harness_agent.core import EssentialContextError, EssentialItem

_ENGINE_ERROR = "Error del almacén del contexto esencial."
_ALREADY_SAVED = "Los elementos del contexto esencial de la sesión ya están guardados."
_DAMAGED = "Un elemento guardado del contexto esencial está dañado y no se puede leer."


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SqliteEssentialStore:
    """Writes the elements of a task once and reads them back.

    Args:
        store: The session store whose connection and tables are used.
        clock: Returns the current time; naive values are taken as UTC.
    """

    def __init__(
        self, store: SqliteSessionStore, *, clock: Callable[[], datetime] = _utc_now
    ) -> None:
        self._store = store
        self._clock = clock

    def save_items(self, session_id: str, items: Sequence[EssentialItem]) -> None:
        """Save every element of the session, or none, and never twice.

        Raises:
            SessionStoreError: The store is closed, the session does not exist, the elements of
                the session are already saved or the engine failed; nothing was written.
        """
        conn = self._store.connection()
        stamp = _to_utc(self._clock()).isoformat()
        already = False
        try:
            conn.execute("BEGIN IMMEDIATE")
            if (
                conn.execute(
                    "SELECT 1 FROM contexto_esencial WHERE sesion_id = ? LIMIT 1", (session_id,)
                ).fetchone()
                is not None
            ):
                conn.rollback()
                already = True
            else:
                conn.executemany(
                    "INSERT INTO contexto_esencial "
                    "(sesion_id, clave, orden, valor, origen, creado) VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (session_id, item.key, item.order, item.value, item.origin, stamp)
                        for item in items
                    ],
                )
                conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise SessionStoreError(_ENGINE_ERROR) from None
        except BaseException:
            conn.rollback()
            raise
        if already:
            raise SessionStoreError(_ALREADY_SAVED)

    def items(self, session_id: str) -> list[EssentialItem]:
        """The elements of the session, ordered by key and position (empty if there are none).

        Raises:
            SessionStoreError: The store is closed, the engine failed or a row is damaged.
        """
        conn = self._store.connection()
        try:
            rows = conn.execute(
                "SELECT clave, orden, valor, origen FROM contexto_esencial "
                "WHERE sesion_id = ? ORDER BY clave, orden",
                (session_id,),
            ).fetchall()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        damaged = False
        found: list[EssentialItem] = []
        for key, order, value, origin in rows:
            try:
                found.append(EssentialItem(key, order, value, origin))
            except EssentialContextError:
                damaged = True
        if damaged:
            raise SessionStoreError(_DAMAGED)
        return found
