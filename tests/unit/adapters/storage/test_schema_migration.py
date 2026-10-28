"""Schema version 2: the ``criterios`` tables and the migration from version 1 (HU-11-01 / T003)."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.storage._schema import SCHEMA_VERSION, ensure_schema
from harness_agent.adapters.storage.errors import SchemaVersionError

# The schema exactly as version 1 shipped it (HU-03-01).
V1_DDL = """
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
PRAGMA user_version = 1;
COMMIT;
"""


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    yield connection
    connection.close()


def user_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def tables(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def add_session(conn: sqlite3.Connection, session_id: str = "s1") -> None:
    conn.execute(
        "INSERT INTO sessions (id, created_at, status) VALUES (?, 't', 'active')", (session_id,)
    )


def add_criterion(conn: sqlite3.Connection, **overrides: object) -> None:
    row: dict[str, object] = {
        "sesion_id": "s1",
        "orden": 1,
        "descripcion": "algo",
        "tipo": "semantico",
        "comando": None,
        "condicion": None,
        "passes": 0,
        "evidencia": None,
    }
    row.update(overrides)
    names = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    conn.execute(f"INSERT INTO criterios ({names}) VALUES ({marks})", tuple(row.values()))


def test_schema_version_is_two() -> None:
    assert SCHEMA_VERSION == 5


def test_new_database_gets_the_criteria_tables(conn: sqlite3.Connection) -> None:
    ensure_schema(conn)

    assert user_version(conn) == 5
    assert {"sessions", "events", "criterios", "criterios_sello"} <= tables(conn)
    assert columns(conn, "criterios") == [
        "id",
        "sesion_id",
        "orden",
        "descripcion",
        "tipo",
        "comando",
        "condicion",
        "passes",
        "evidencia",
        "confirmado_por",
    ]
    assert columns(conn, "criterios_sello") == ["sesion_id", "huella"]


def test_version_one_database_migrates_without_losing_data(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(V1_DDL)
    old.execute(
        "INSERT INTO sessions (id, created_at, goal, status) VALUES ('s1','t','g','active')"
    )
    old.execute(
        "INSERT INTO events (id, session_id, seq, type, content, created_at) "
        "VALUES ('e1','s1',1,'user_message','{}','t')"
    )
    old.commit()
    old.close()

    conn = sqlite3.connect(path)
    try:
        ensure_schema(conn)
        assert user_version(conn) == 5
        assert conn.execute("SELECT id, goal FROM sessions").fetchall() == [("s1", "g")]
        assert conn.execute("SELECT id FROM events").fetchall() == [("e1",)]
        assert "criterios" in tables(conn)
    finally:
        conn.close()


def test_migration_runs_once_and_version_two_is_accepted_as_is(conn: sqlite3.Connection) -> None:
    conn.executescript(V1_DDL)
    ensure_schema(conn)
    add_session(conn)
    add_criterion(conn)
    conn.commit()

    ensure_schema(conn)

    assert conn.execute("SELECT count(*) FROM criterios").fetchone()[0] == 1


def test_failed_migration_leaves_the_database_at_version_one(conn: sqlite3.Connection) -> None:
    conn.executescript(V1_DDL)
    conn.execute("CREATE TABLE criterios (x INTEGER)")  # a clash the migration cannot overcome

    with pytest.raises(sqlite3.OperationalError):
        ensure_schema(conn)

    assert not conn.in_transaction
    assert user_version(conn) == 1
    assert "criterios_sello" not in tables(conn)


def test_unknown_versions_are_still_refused(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE marker (x INTEGER)")
    conn.execute("PRAGMA user_version = 6")
    with pytest.raises(SchemaVersionError):
        ensure_schema(conn)


def test_session_must_exist_for_a_criterion(conn: sqlite3.Connection) -> None:
    ensure_schema(conn)
    with pytest.raises(sqlite3.IntegrityError):
        add_criterion(conn)


@pytest.mark.parametrize(
    "overrides",
    [
        {"tipo": "otro"},
        {"descripcion": "   "},
        {"orden": 0},
        {"passes": 2},
        {"tipo": "objetivo"},  # objective without command and condition
        {"tipo": "objetivo", "comando": "ls"},  # objective without condition
        {"comando": "ls", "condicion": "ok"},  # semantic with a command
        {"passes": 1},  # passed without evidence
        {"passes": 1, "evidencia": "  "},
    ],
)
def test_rows_that_break_the_rules_are_rejected(
    conn: sqlite3.Connection, overrides: dict[str, object]
) -> None:
    ensure_schema(conn)
    add_session(conn)
    with pytest.raises(sqlite3.IntegrityError):
        add_criterion(conn, **overrides)


def test_valid_rows_are_accepted_and_order_is_unique_per_session(
    conn: sqlite3.Connection,
) -> None:
    ensure_schema(conn)
    add_session(conn)
    add_criterion(conn, tipo="objetivo", comando="ls", condicion="ok", orden=1)
    add_criterion(conn, passes=1, evidencia="visto", orden=2)
    with pytest.raises(sqlite3.IntegrityError):
        add_criterion(conn, orden=2)
