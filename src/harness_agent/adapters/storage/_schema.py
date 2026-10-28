"""SQLite schema of the session store: DDL, versions, migration and the open-time check.

The version lives in ``PRAGMA user_version``. A new database gets the current schema; a database
at version 1 (sessions and events, HU-03-01) is migrated to the current one without touching its
data. Version 2 adds the ``criterios`` tables (HU-11-01), version 3 the ``resumenes`` table of the
automatic compaction (HU-02-03), version 4 the ``contexto_esencial`` table (HU-02-06.1) and
version 5 the ``mensajes`` table of the resumable conversation (HU-03-04). A
database at the current version is accepted as is; anything else (a newer version, or a database
that has tables but no version) is refused without being modified. Every change runs in one
transaction.
"""

from __future__ import annotations

import sqlite3

from harness_agent.adapters.storage.errors import SchemaVersionError

SCHEMA_VERSION = 5

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

# Summaries of the automatic compaction (HU-02-03). The events a summary covers carry its id in
# ``events.compacted_by`` (a column since version 1); nothing else changes.
_V3 = """
CREATE TABLE resumenes (
    id            TEXT PRIMARY KEY,
    sesion_id     TEXT NOT NULL REFERENCES sessions(id),
    evento_desde  INTEGER NOT NULL CHECK (evento_desde >= 1),
    evento_hasta  INTEGER NOT NULL CHECK (evento_hasta >= evento_desde),
    texto         TEXT NOT NULL CHECK (length(trim(texto)) > 0),
    creado        TEXT NOT NULL
);
CREATE INDEX idx_resumenes_sesion ON resumenes (sesion_id, evento_hasta);
"""

# Essential context of a task (HU-02-06.1): the elements are written once, when the session of the
# task is created, and only read afterwards. ``clave`` is not restricted here on purpose (the
# decisions of HU-02-06.2 will need no new schema); the core validates the keys.
_V4 = """
CREATE TABLE contexto_esencial (
    sesion_id  TEXT NOT NULL REFERENCES sessions(id),
    clave      TEXT NOT NULL CHECK (length(trim(clave)) > 0),
    orden      INTEGER NOT NULL CHECK (orden >= 1),
    valor      TEXT NOT NULL CHECK (length(trim(valor)) > 0),
    origen     TEXT NOT NULL CHECK (length(trim(origen)) > 0),
    creado     TEXT NOT NULL,
    PRIMARY KEY (sesion_id, clave, orden)
);
"""

# The messages of the conversation (HU-03-04): one row per real message of a session without a task,
# in order, so that the session can be resumed. ``evento_id`` is the identifier of the event that
# triggered the saving of the message (it has no foreign key: after a cut the event may never have
# been stored); the messages that have no event of their own leave it empty.
_V5 = """
CREATE TABLE mensajes (
    sesion_id        TEXT NOT NULL REFERENCES sessions(id),
    posicion         INTEGER NOT NULL CHECK (posicion >= 1),
    rol              TEXT NOT NULL CHECK (rol IN ('user', 'assistant', 'tool')),
    contenido        TEXT NOT NULL,
    llamadas         TEXT,
    resultado_id     TEXT,
    resultado_error  INTEGER CHECK (resultado_error IN (0, 1)),
    externo          INTEGER NOT NULL DEFAULT 0 CHECK (externo IN (0, 1)),
    uso              TEXT,
    evento_id        TEXT,
    creado           TEXT NOT NULL,
    PRIMARY KEY (sesion_id, posicion),
    CHECK ((rol = 'tool' AND resultado_id IS NOT NULL AND resultado_error IS NOT NULL)
        OR (rol <> 'tool' AND resultado_id IS NULL AND resultado_error IS NULL)),
    CHECK (rol = 'assistant' OR llamadas IS NULL)
);
CREATE INDEX idx_mensajes_evento ON mensajes (evento_id);
"""

# What each version adds on top of the one before it.
_STEPS = {1: _V1, 2: _V2, 3: _V3, 4: _V4, 5: _V5}


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
