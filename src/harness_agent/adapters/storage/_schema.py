"""SQLite schema of the session store: DDL, versions, migration and the open-time check.

The version lives in ``PRAGMA user_version``. A new database gets the current schema; a database
at version 1 (sessions and events, HU-03-01) is migrated to the current one without touching its
data (version 2 adds the ``criterios`` tables, HU-11-01); a database at the current version is
accepted as is; anything else (a newer version, or a database that has tables but no version) is
refused without being modified. Every change runs in one transaction.
"""

from __future__ import annotations

import sqlite3

from harness_agent.adapters.storage.errors import SchemaVersionError

SCHEMA_VERSION = 2

_V1 = """
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
"""

_V2 = """
CREATE TABLE criterios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id      TEXT NOT NULL REFERENCES sessions(id),
    orden          INTEGER NOT NULL CHECK (orden >= 1),
    descripcion    TEXT NOT NULL CHECK (length(trim(descripcion)) > 0),
    tipo           TEXT NOT NULL CHECK (tipo IN ('objetivo', 'semantico')),
    comando        TEXT,
    condicion      TEXT,
    passes         INTEGER NOT NULL DEFAULT 0 CHECK (passes IN (0, 1)),
    evidencia      TEXT,
    confirmado_por TEXT,
    UNIQUE (sesion_id, orden),
    CHECK ((tipo = 'objetivo' AND comando IS NOT NULL AND condicion IS NOT NULL)
        OR (tipo = 'semantico' AND comando IS NULL AND condicion IS NULL)),
    CHECK (passes = 0 OR (evidencia IS NOT NULL AND length(trim(evidencia)) > 0))
);
CREATE TABLE criterios_sello (
    sesion_id TEXT PRIMARY KEY REFERENCES sessions(id),
    huella    TEXT NOT NULL
);
"""

# What each version adds on top of the one before it.
_STEPS = {1: _V1, 2: _V2}


def _script(first: int) -> str:
    """One transaction that applies every step from ``first`` to the current version."""
    steps = "".join(_STEPS[version] for version in range(first, SCHEMA_VERSION + 1))
    return f"BEGIN;\n{steps}\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;\n"


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Enable foreign keys and create, migrate or validate the schema on ``conn``.

    Raises:
        SchemaVersionError: The database is at a version this build does not know.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version == SCHEMA_VERSION:
        return
    has_tables = conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is not None
    if version == 0 and not has_tables:
        script = _script(1)
    elif 1 <= version < SCHEMA_VERSION:
        script = _script(version + 1)
    else:
        raise SchemaVersionError("La base de datos tiene una versión de esquema desconocida.")
    try:
        conn.executescript(script)
    except sqlite3.Error:
        conn.rollback()
        raise
