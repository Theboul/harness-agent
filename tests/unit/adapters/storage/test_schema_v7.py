"""Schema version 7: the ``auditoria`` and ``trazas`` tables, migrated from 1 to 6 (HU-05-05).

The databases are real files created with the SQL that versions 1 to 6 shipped (the older steps are
written out in ``test_schema_v5`` and ``test_schema_v6``), filled with data and opened by the store
of this version. The two tables have no foreign key and no ``CHECK``: the audit and the traces
must survive anything, and no session, event or message can touch them.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.adapters.storage._schema import SCHEMA_VERSION
from tests.unit.adapters.storage.test_schema_v5 import dump, user_version
from tests.unit.adapters.storage.test_schema_v6 import make_old_database as make_database_to_five

V6_DDL = """
CREATE TABLE memorias (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    clave        TEXT NOT NULL UNIQUE CHECK (length(trim(clave)) > 0),
    contenido    TEXT NOT NULL CHECK (length(trim(contenido)) > 0),
    creada       TEXT NOT NULL,
    actualizada  TEXT NOT NULL
);
CREATE INDEX idx_memorias_actualizada ON memorias (actualizada, id);
"""

MEMORY = """
INSERT INTO memorias (clave, contenido, creada, actualizada)
    VALUES ('estilo', 'Usa comillas dobles.', '2026-11-01T10:00:00+00:00',
            '2026-11-01T10:00:00+00:00');
"""

NEW_TABLES = {
    1: {"criterios", "criterios_sello", "resumenes", "contexto_esencial", "mensajes", "memorias"},
    2: {"resumenes", "contexto_esencial", "mensajes", "memorias"},
    3: {"contexto_esencial", "mensajes", "memorias"},
    4: {"mensajes", "memorias"},
    5: {"memorias"},
    6: set(),
}

AUDIT_COLUMNS = [
    "id",
    "sesion_id",
    "llamada_id",
    "herramienta",
    "argumentos",
    "decision",
    "resolucion",
    "razon",
    "accion",
    "fuente",
    "origen",
    "decidida",
    "resuelta",
]
TRACE_COLUMNS = [
    "id",
    "sesion_id",
    "tipo",
    "nombre",
    "inicio",
    "duracion_ms",
    "tokens_entrada",
    "tokens_salida",
    "resultado",
    "tamano",
]


def make_old_database(path: Path, version: int) -> None:
    """A real file at ``version`` (1 to 6), with rows in every table that version has."""
    make_database_to_five(path, min(version, 5))
    if version >= 6:
        connection = sqlite3.connect(path)
        try:
            connection.executescript(V6_DDL)
            connection.executescript(MEMORY)
            connection.execute("PRAGMA user_version = 6")
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


def test_the_version_is_seven() -> None:
    assert SCHEMA_VERSION == 7


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5, 6])
def test_an_old_database_migrates_to_seven_and_keeps_every_row(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / f"v{version}.db"
    make_old_database(path, version)
    before = dump(path)

    open_and_close(path)

    assert user_version(path) == 7
    after = dump(path)
    assert after.pop("auditoria") == []
    assert after.pop("trazas") == []
    for name in NEW_TABLES[version]:  # the tables of the steps in between
        stored = after.pop(name)
        assert stored == before.get(name, [])
    assert after == {name: rows for name, rows in before.items() if name not in NEW_TABLES[version]}


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5, 6])
def test_reopening_a_migrated_database_changes_nothing(tmp_path: Path, version: int) -> None:
    path = tmp_path / f"v{version}.db"
    make_old_database(path, version)
    open_and_close(path)
    first = dump(path)

    open_and_close(path)
    open_and_close(path)

    assert user_version(path) == 7
    assert dump(path) == first


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5, 6])
def test_a_migrated_database_has_the_same_tables_as_a_new_one(tmp_path: Path, version: int) -> None:
    old = tmp_path / "old.db"
    make_old_database(old, version)
    fresh = tmp_path / "fresh.db"
    open_and_close(old)
    open_and_close(fresh)

    assert user_version(fresh) == 7
    names = ("auditoria", "trazas", "memorias", "mensajes", "contexto_esencial", "resumenes")
    for name in (*names, "sessions", "events"):
        assert table_sql(old, name) == table_sql(fresh, name)


def test_a_new_database_has_both_tables_their_columns_and_their_indexes(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    open_and_close(path)
    connection = sqlite3.connect(path)
    try:
        audit = [row[1] for row in connection.execute("PRAGMA table_info(auditoria)")]
        traces = [row[1] for row in connection.execute("PRAGMA table_info(trazas)")]
        audit_key = [row[1] for row in connection.execute("PRAGMA table_info(auditoria)") if row[5]]
        audit_index = [
            row[2] for row in connection.execute("PRAGMA index_info(idx_auditoria_sesion)")
        ]
        trace_index = [row[2] for row in connection.execute("PRAGMA index_info(idx_trazas_sesion)")]
    finally:
        connection.close()

    assert audit == AUDIT_COLUMNS and traces == TRACE_COLUMNS
    assert audit_key == ["id"]
    assert audit_index == ["sesion_id", "id"] and trace_index == ["sesion_id", "id"]


def test_the_two_tables_have_no_foreign_key_and_no_check_and_name_no_other_table(
    tmp_path: Path,
) -> None:
    path = tmp_path / "fresh.db"
    open_and_close(path)
    connection = sqlite3.connect(path)
    try:
        foreign_keys = [
            list(connection.execute(f"PRAGMA foreign_key_list({name})"))
            for name in ("auditoria", "trazas")
        ]
    finally:
        connection.close()

    assert foreign_keys == [[], []]
    for name in ("auditoria", "trazas"):
        ddl = table_sql(path, name).upper()
        assert "REFERENCES" not in ddl and "CHECK" not in ddl
        for other in ("SESSIONS", "EVENTS", "MENSAJES", "MEMORIAS", "CRITERIOS"):
            assert other not in ddl


def test_deleting_a_session_with_its_events_does_not_touch_the_audit_or_the_traces(
    tmp_path: Path,
) -> None:
    path = tmp_path / "fresh.db"
    store = SqliteSessionStore(path)
    session = store.create_session(model="fake/test").id
    connection = store.connection()
    connection.execute(
        "INSERT INTO auditoria (sesion_id, llamada_id, herramienta, argumentos, decision, "
        "resolucion, origen, decidida) VALUES (?, 'c1', 'x', '{}', 'allow', 'permitida', "
        "'agente', 't')",
        (session,),
    )
    connection.execute(
        "INSERT INTO trazas (sesion_id, tipo, nombre, inicio, duracion_ms, resultado, tamano) "
        "VALUES (?, 'modelo', 'm', 't', 1, 'ok', 0)",
        (session,),
    )
    connection.commit()

    connection.execute("DELETE FROM events WHERE session_id = ?", (session,))
    connection.execute("DELETE FROM sessions WHERE id = ?", (session,))
    connection.commit()

    counts = [
        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("auditoria", "trazas")
    ]
    store.close()
    assert counts == [1, 1]


def test_a_version_eight_database_is_refused_without_being_modified(tmp_path: Path) -> None:
    path = tmp_path / "future.db"
    make_old_database(path, 6)
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
