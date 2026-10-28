"""Schema version 3: the ``resumenes`` table and the migration from 1 and 2 (HU-02-03 / T006).

The databases are real files created with the SQL that versions 1 and 2 shipped, filled with data,
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

DATA = """
INSERT INTO sessions (id, created_at, model, goal, status)
    VALUES ('s1', '2026-10-27T10:00:00+00:00', 'fake/test', 'meta', 'active');
INSERT INTO sessions (id, created_at, status)
    VALUES ('s2', '2026-10-27T11:00:00+00:00', 'completed');
INSERT INTO events (id, session_id, seq, type, content, created_at, compacted_by)
    VALUES ('e1', 's1', 1, 'user_message', '{"text": "hola"}', 't1', NULL);
INSERT INTO events (id, session_id, seq, type, content, created_at, compacted_by)
    VALUES ('e2', 's1', 2, 'assistant_message', '{"text": "ok"}', 't2', 'resumen-viejo');
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


def make_database(path: Path, version: int) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(V1_DDL)
        connection.executescript(DATA)
        if version >= 2:
            connection.executescript(V2_DDL)
            connection.executescript(CRITERIA)
        connection.execute(f"PRAGMA user_version = {version}")
        connection.commit()
    finally:
        connection.close()


def dump(path: Path, skip: frozenset[str] = frozenset()) -> dict[str, list[tuple[object, ...]]]:
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
            if name not in skip
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


def test_the_version_is_three() -> None:
    assert SCHEMA_VERSION == 5


@pytest.mark.parametrize("version", [1, 2])
def test_an_old_database_migrates_to_three_and_keeps_every_row(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / f"v{version}.db"
    make_database(path, version)
    before = dump(path)

    open_and_close(path)

    assert user_version(path) == 5
    after = dump(path)
    assert after.pop("resumenes") == []
    assert after.pop("contexto_esencial") == []
    assert after.pop("mensajes") == []
    if version == 1:  # the criteria tables of version 2 arrive empty on the way
        assert after.pop("criterios") == [] and after.pop("criterios_sello") == []
    assert after == before  # every table that already existed is identical, row by row


@pytest.mark.parametrize("version", [1, 2])
def test_reopening_a_migrated_database_changes_nothing(tmp_path: Path, version: int) -> None:
    path = tmp_path / f"v{version}.db"
    make_database(path, version)
    open_and_close(path)
    first = dump(path)

    open_and_close(path)
    open_and_close(path)

    assert user_version(path) == 5
    assert dump(path) == first


@pytest.mark.parametrize("version", [1, 2])
def test_a_migrated_database_has_the_same_table_as_a_new_one(tmp_path: Path, version: int) -> None:
    old = tmp_path / "old.db"
    make_database(old, version)
    fresh = tmp_path / "fresh.db"
    open_and_close(old)
    open_and_close(fresh)

    assert table_sql(old, "resumenes") == table_sql(fresh, "resumenes")
    assert user_version(fresh) == 5
    for name in ("sessions", "events", "criterios", "criterios_sello"):
        assert table_sql(old, name) == table_sql(fresh, name)


def test_the_index_of_the_summaries_exists(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    open_and_close(path)
    connection = sqlite3.connect(path)
    try:
        columns = [row[2] for row in connection.execute("PRAGMA index_info(idx_resumenes_sesion)")]
    finally:
        connection.close()

    assert columns == ["sesion_id", "evento_hasta"]


def test_the_columns_of_the_summaries(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    open_and_close(path)
    connection = sqlite3.connect(path)
    try:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(resumenes)")]
    finally:
        connection.close()

    assert columns == ["id", "sesion_id", "evento_desde", "evento_hasta", "texto", "creado"]


def summary_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": "r1",
        "sesion_id": "s1",
        "evento_desde": 2,
        "evento_hasta": 6,
        "texto": "Se migró el módulo.",
        "creado": "2026-10-27T12:00:00+00:00",
    }
    row.update(overrides)
    return row


def insert_summary(connection: sqlite3.Connection, **overrides: object) -> None:
    row = summary_row(**overrides)
    names = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    connection.execute(f"INSERT INTO resumenes ({names}) VALUES ({marks})", tuple(row.values()))


@pytest.fixture
def store(tmp_path: Path) -> Iterator[SqliteSessionStore]:
    path = tmp_path / "v2.db"
    make_database(path, 2)
    opened = SqliteSessionStore(path)
    yield opened
    opened.close()


def test_a_valid_summary_is_accepted(store: SqliteSessionStore) -> None:
    connection = store.connection()

    insert_summary(connection)

    assert connection.execute(
        "SELECT id, evento_desde, evento_hasta FROM resumenes"
    ).fetchall() == [("r1", 2, 6)]


@pytest.mark.parametrize(
    "overrides",
    [
        {"evento_desde": 0, "evento_hasta": 0},
        {"evento_desde": 5, "evento_hasta": 4},
        {"texto": ""},
        {"texto": "   "},
        {"sesion_id": "no-existe"},
        {"creado": None},
    ],
    ids=[
        "from zero",
        "range reversed",
        "empty text",
        "blank text",
        "no session",
        "no date",
    ],
)
def test_the_constraints_refuse_a_bad_row(
    store: SqliteSessionStore, overrides: dict[str, object]
) -> None:
    connection = store.connection()

    with pytest.raises(sqlite3.IntegrityError):
        insert_summary(connection, **overrides)

    assert connection.execute("SELECT count(*) FROM resumenes").fetchone()[0] == 0


def test_the_identifier_of_a_summary_is_unique(store: SqliteSessionStore) -> None:
    connection = store.connection()
    insert_summary(connection)

    with pytest.raises(sqlite3.IntegrityError):
        insert_summary(connection, evento_desde=7, evento_hasta=9)


def test_a_range_of_one_event_is_valid(store: SqliteSessionStore) -> None:
    insert_summary(store.connection(), evento_desde=3, evento_hasta=3)
