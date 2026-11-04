"""Schema version 6: the ``memorias`` table and the migration from 1, 2, 3, 4 and 5 (HU-04-01).

The databases are real files created with the SQL that versions 1 to 5 shipped (the older steps are
the ones written out in ``test_schema_v5``), filled with data and opened by the store of this
version. The memory has no foreign key: no session, event or message can touch it.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.adapters.storage._schema import SCHEMA_VERSION
from tests.unit.adapters.storage.test_schema_v5 import dump, make_database, user_version

V5_DDL = """
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

MESSAGES = """
INSERT INTO mensajes (sesion_id, posicion, rol, contenido, creado)
    VALUES ('s1', 1, 'user', 'hola', '2026-10-27T10:00:00+00:00');
"""

NEW_TABLES = {
    1: {"criterios", "criterios_sello", "resumenes", "contexto_esencial", "mensajes"},
    2: {"resumenes", "contexto_esencial", "mensajes"},
    3: {"contexto_esencial", "mensajes"},
    4: {"mensajes"},
    5: set(),
}


def make_old_database(path: Path, version: int) -> None:
    """A real file at ``version`` (1 to 5), with rows in every table that version has."""
    make_database(path, min(version, 4))
    connection = sqlite3.connect(path)
    try:
        if version >= 5:
            connection.executescript(V5_DDL)
            connection.executescript(MESSAGES)
        connection.execute(f"PRAGMA user_version = {version}")
        connection.commit()
    finally:
        connection.close()


def open_and_close(path: Path) -> None:
    SqliteSessionStore(path).close()


def table_sql(path: Path, name: str) -> str:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute("SELECT sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()
        return str(row[0])
    finally:
        connection.close()


def test_the_version_is_six() -> None:
    assert SCHEMA_VERSION == 7


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_an_old_database_migrates_to_six_and_keeps_every_row(tmp_path: Path, version: int) -> None:
    path = tmp_path / f"v{version}.db"
    make_old_database(path, version)
    before = dump(path)

    open_and_close(path)

    assert user_version(path) == 7
    after = dump(path)
    assert after.pop("memorias") == []
    assert after.pop("auditoria") == []
    assert after.pop("trazas") == []
    for name in NEW_TABLES[version]:  # the tables of the steps in between arrive empty
        stored = after.pop(name)
        assert stored == before.get(name, [])
    assert after == {name: rows for name, rows in before.items() if name not in NEW_TABLES[version]}


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_reopening_a_migrated_database_changes_nothing(tmp_path: Path, version: int) -> None:
    path = tmp_path / f"v{version}.db"
    make_old_database(path, version)
    open_and_close(path)
    first = dump(path)

    open_and_close(path)
    open_and_close(path)

    assert user_version(path) == 7
    assert dump(path) == first


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_a_migrated_database_has_the_same_tables_as_a_new_one(tmp_path: Path, version: int) -> None:
    old = tmp_path / "old.db"
    make_old_database(old, version)
    fresh = tmp_path / "fresh.db"
    open_and_close(old)
    open_and_close(fresh)

    assert user_version(fresh) == 7
    for name in ("memorias", "mensajes", "contexto_esencial", "resumenes", "sessions", "events"):
        assert table_sql(old, name) == table_sql(fresh, name)


def test_a_new_database_has_the_table_its_columns_its_key_and_its_index(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    open_and_close(path)
    connection = sqlite3.connect(path)
    try:
        info = list(connection.execute("PRAGMA table_info(memorias)"))
        indexes = [row[1] for row in connection.execute("PRAGMA index_list(memorias)")]
        index_columns = [
            row[2] for row in connection.execute("PRAGMA index_info(idx_memorias_actualizada)")
        ]
    finally:
        connection.close()

    assert [row[1] for row in info] == ["id", "clave", "contenido", "creada", "actualizada"]
    assert [row[1] for row in info if row[5]] == ["id"]
    assert "idx_memorias_actualizada" in indexes
    assert index_columns == ["actualizada", "id"]


def test_the_memory_has_no_foreign_key_and_its_ddl_names_no_other_table(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    open_and_close(path)
    connection = sqlite3.connect(path)
    try:
        foreign_keys = list(connection.execute("PRAGMA foreign_key_list(memorias)"))
    finally:
        connection.close()

    assert foreign_keys == []
    ddl = table_sql(path, "memorias")
    assert "REFERENCES" not in ddl.upper()
    for other in ("sessions", "events", "mensajes", "resumenes", "criterios"):
        assert other not in ddl


def test_the_constraints_refuse_an_empty_key_an_empty_text_and_a_repeated_key(
    tmp_path: Path,
) -> None:
    path = tmp_path / "fresh.db"
    open_and_close(path)
    connection = sqlite3.connect(path)
    insert = "INSERT INTO memorias (clave, contenido, creada, actualizada) VALUES (?, ?, 't', 't')"
    try:
        connection.execute(insert, ("a", "texto"))
        for bad in (("  ", "texto"), ("b", "   "), ("a", "otro")):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(insert, bad)
    finally:
        connection.close()


def test_a_version_seven_database_is_refused_without_being_modified(tmp_path: Path) -> None:
    path = tmp_path / "future.db"
    make_old_database(path, 5)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 8")
    connection.commit()
    connection.close()
    before = path.read_bytes()

    with pytest.raises(Exception) as raised:
        SqliteSessionStore(path)

    assert type(raised.value).__name__ == "SchemaVersionError"
    assert path.read_bytes() == before


def test_a_database_with_tables_and_no_version_is_refused_without_being_modified(
    tmp_path: Path,
) -> None:
    path = tmp_path / "unknown.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE otra (x INTEGER)")
    connection.commit()
    connection.close()
    before = path.read_bytes()

    with pytest.raises(Exception) as raised:
        SqliteSessionStore(path)

    assert type(raised.value).__name__ == "SchemaVersionError"
    assert path.read_bytes() == before
