"""SQLite schema of the session store: DDL, version and the open-time check.

The version lives in ``PRAGMA user_version``. A new database gets the current schema; a database
at the current version is accepted as is; anything else (a newer version, or a database that has
tables but no version) is refused without being modified.
"""

from __future__ import annotations

import sqlite3

from harness_agent.adapters.storage.errors import SchemaVersionError

SCHEMA_VERSION = 1

_DDL = f"""
BEGIN;
CREATE TABLE sessions (
    id          TEXT PRIMARY KEY,
    parent_id   TEXT REFERENCES sessions(id),
    created_at  TEXT NOT NULL,
    model       TEXT,
    goal        TEXT,
    status      TEXT NOT NULL CHECK (status IN ('active', 'completed', 'interrupted'))
);
CREATE TABLE events (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    seq           INTEGER NOT NULL,
    type          TEXT NOT NULL,
    content       TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    compacted_by  TEXT,
    UNIQUE (session_id, seq)
);
PRAGMA user_version = {SCHEMA_VERSION};
COMMIT;
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Enable foreign keys and create or validate the schema on ``conn``.

    Raises:
        SchemaVersionError: The database is not at the version this build knows.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version == SCHEMA_VERSION:
        return
    has_tables = conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is not None
    if version != 0 or has_tables:
        raise SchemaVersionError("La base de datos tiene una versión de esquema desconocida.")
    try:
        conn.executescript(_DDL)
    except sqlite3.Error:
        conn.rollback()
        raise
