"""Schema version 5: the ``mensajes`` table and the migration from 1, 2, 3 and 4 (HU-03-04).

The databases are real files created with the SQL that versions 1 to 4 shipped, filled with data,
and opened by the store of this version. The old SQL is written out here on purpose: it must not
follow the schema module.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.adapters.storage._schema import SCHEMA_VERSION

V1_DDL = """
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

V2_DDL = """
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

V3_DDL = """
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

V4_DDL = """
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

DATA = """
INSERT INTO sessions (id, created_at, model, goal, status)
    VALUES ('s1', '2026-10-27T10:00:00+00:00', 'fake/test', 'meta', 'active');
INSERT INTO sessions (id, created_at, status)
    VALUES ('s2', '2026-10-27T11:00:00+00:00', 'completed');
INSERT INTO events (id, session_id, seq, type, content, created_at, compacted_by)
    VALUES ('e1', 's1', 1, 'user_message', '{"text": "hola"}', 't1', NULL);
INSERT INTO events (id, session_id, seq, type, content, created_at, compacted_by)
    VALUES ('e2', 's1', 2, 'assistant_message', '{"text": "ok"}', 't2', 'r1');
INSERT INTO events (id, session_id, seq, type, content, created_at, compacted_by)
    VALUES ('e3', 's2', 1, 'user_message', '{"text": "otra"}', 't3', NULL);
"""

CRITERIA = """
INSERT INTO criterios (sesion_id, orden, descripcion, tipo, comando, condicion, passes, evidencia)
    VALUES ('s1', 1, 'pasa la suite', 'objetivo', 'pytest', 'exit 0', 1, 'exit 0');
INSERT INTO criterios (sesion_id, orden, descripcion, tipo)
    VALUES ('s1', 2, 'se lee bien', 'semantico');
INSERT INTO criterios_sello (sesion_id, huella) VALUES ('s1', 'huella-de-prueba');
"""

SUMMARY = """
INSERT INTO resumenes (id, sesion_id, evento_desde, evento_hasta, texto, creado)
    VALUES ('r1', 's1', 2, 2, 'Se migró el módulo.', '2026-10-27T12:00:00+00:00');
"""

ESSENTIAL = """
INSERT INTO contexto_esencial (sesion_id, clave, orden, valor, origen, creado)
    VALUES ('s1', 'objetivo', 1, 'Rechazar correos sin dominio.', 'tarea',
            '2026-10-27T12:00:00+00:00');
"""

NEW_TABLES = {
    1: {"criterios", "criterios_sello", "resumenes", "contexto_esencial"},
    2: {"resumenes", "contexto_esencial"},
    3: {"contexto_esencial"},
    4: set(),
}


def make_database(path: Path, version: int) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(V1_DDL)
        connection.executescript(DATA)
        if version >= 2:
            connection.executescript(V2_DDL)
            connection.executescript(CRITERIA)
        if version >= 3:
            connection.executescript(V3_DDL)
            connection.executescript(SUMMARY)
        if version >= 4:
            connection.executescript(V4_DDL)
            connection.executescript(ESSENTIAL)
        connection.execute(f"PRAGMA user_version = {version}")
        connection.commit()
    finally:
        connection.close()


def dump(path: Path) -> dict[str, list[tuple[object, ...]]]:
    """Every row of every table of the file, read without the store."""
    connection = sqlite3.connect(path)
    try:
        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {
            name: connection.execute(f"SELECT * FROM {name} ORDER BY 1, 2").fetchall()
            for name in names
        }
    finally:
        connection.close()


def table_sql(path: Path, name: str) -> str:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute("SELECT sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()
        return str(row[0])
    finally:
        connection.close()


def user_version(path: Path) -> int:
    connection = sqlite3.connect(path)
    try:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])
    finally:
        connection.close()


def open_and_close(path: Path) -> None:
    SqliteSessionStore(path).close()


def test_the_version_is_five() -> None:
    assert SCHEMA_VERSION == 5


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_an_old_database_migrates_to_five_and_keeps_every_row(tmp_path: Path, version: int) -> None:
    path = tmp_path / f"v{version}.db"
    make_database(path, version)
    before = dump(path)

    open_and_close(path)

    assert user_version(path) == 5
    after = dump(path)
    assert after.pop("mensajes") == []
    for name in NEW_TABLES[version]:  # the tables of the steps in between arrive empty
        assert after.pop(name) == []
    assert after == before  # every table that already existed is identical, row by row


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_reopening_a_migrated_database_changes_nothing(tmp_path: Path, version: int) -> None:
    path = tmp_path / f"v{version}.db"
    make_database(path, version)
    open_and_close(path)
    first = dump(path)

    open_and_close(path)
    open_and_close(path)

    assert user_version(path) == 5
    assert dump(path) == first


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_a_migrated_database_has_the_same_tables_as_a_new_one(tmp_path: Path, version: int) -> None:
    old = tmp_path / "old.db"
    make_database(old, version)
    fresh = tmp_path / "fresh.db"
    open_and_close(old)
    open_and_close(fresh)

    assert user_version(fresh) == 5
    for name in ("mensajes", "contexto_esencial", "resumenes", "sessions", "events", "criterios"):
        assert table_sql(old, name) == table_sql(fresh, name)


def test_a_new_database_has_the_table_its_columns_its_key_and_its_index(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    open_and_close(path)
    connection = sqlite3.connect(path)
    try:
        info = list(connection.execute("PRAGMA table_info(mensajes)"))
        indexes = [row[1] for row in connection.execute("PRAGMA index_list(mensajes)")]
        index_columns = [
            row[2] for row in connection.execute("PRAGMA index_info(idx_mensajes_evento)")
        ]
    finally:
        connection.close()

    assert [row[1] for row in info] == [
        "sesion_id",
        "posicion",
        "rol",
        "contenido",
        "llamadas",
        "resultado_id",
        "resultado_error",
        "externo",
        "uso",
        "evento_id",
        "creado",
    ]
    assert [row[1] for row in info if row[5]] == ["sesion_id", "posicion"]
    assert "idx_mensajes_evento" in indexes and index_columns == ["evento_id"]


def message(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "sesion_id": "s1",
        "posicion": 1,
        "rol": "user",
        "contenido": "hola",
        "llamadas": None,
        "resultado_id": None,
        "resultado_error": None,
        "externo": 0,
        "uso": None,
        "evento_id": "e1",
        "creado": "2026-10-27T12:00:00+00:00",
    }
    row.update(overrides)
    return row


def insert(connection: sqlite3.Connection, **overrides: object) -> None:
    row = message(**overrides)
    names = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    connection.execute(f"INSERT INTO mensajes ({names}) VALUES ({marks})", tuple(row.values()))


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteSessionStore]:
    path = tmp_path / "v4.db"
    make_database(path, 4)
    opened = SqliteSessionStore(path)
    yield opened
    opened.close()


def test_valid_messages_of_each_role_are_accepted(store: SqliteSessionStore) -> None:
    connection = store.connection()

    insert(connection)
    insert(
        connection,
        posicion=2,
        rol="assistant",
        contenido="",
        llamadas='[{"id": "c1", "name": "leer_archivo", "arguments": {}}]',
        uso='{"input_tokens": 3, "output_tokens": 4}',
        evento_id=None,
    )
    insert(
        connection,
        posicion=3,
        rol="tool",
        contenido="salida",
        resultado_id="c1",
        resultado_error=1,
        externo=1,
        evento_id="un-evento-que-nunca-se-guardo",
    )

    assert connection.execute("SELECT count(*) FROM mensajes").fetchone() == (3,)


@pytest.mark.parametrize(
    "overrides",
    [
        {"posicion": 0},
        {"rol": "system"},
        {"rol": "tool"},
        {"rol": "tool", "resultado_id": "c1"},
        {"rol": "tool", "resultado_error": 0},
        {"rol": "user", "resultado_id": "c1", "resultado_error": 0},
        {"rol": "user", "llamadas": "[]"},
        {"externo": 2},
        {"sesion_id": "no-existe"},
        {"contenido": None},
        {"creado": None},
    ],
    ids=[
        "position zero",
        "role system",
        "tool without result",
        "tool without error flag",
        "tool without result id",
        "user with a result",
        "user with calls",
        "external flag out of range",
        "no session",
        "no content",
        "no date",
    ],
)
def test_the_constraints_refuse_a_bad_row(
    store: SqliteSessionStore, overrides: dict[str, object]
) -> None:
    connection = store.connection()

    with pytest.raises(sqlite3.IntegrityError):
        insert(connection, **overrides)

    assert connection.execute("SELECT count(*) FROM mensajes").fetchone() == (0,)


def test_a_position_cannot_be_stored_twice_in_a_session(store: SqliteSessionStore) -> None:
    connection = store.connection()
    insert(connection)

    with pytest.raises(sqlite3.IntegrityError):
        insert(connection, contenido="otro")

    insert(connection, posicion=2)
    insert(connection, sesion_id="s2")  # the same position in another session is fine


def test_a_version_six_database_is_refused_without_being_modified(tmp_path: Path) -> None:
    path = tmp_path / "v6.db"
    make_database(path, 4)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 6")
    connection.commit()
    connection.close()
    before = dump(path)

    with pytest.raises(Exception, match="versión de esquema desconocida"):
        SqliteSessionStore(path)

    assert dump(path) == before and user_version(path) == 6
