"""Events survive abrupt process death and half-written saves (HU-03-02 / T006, T007).

A child process writes to a real file and dies with ``os._exit`` (no ``close``, no ``atexit``,
no flush by Python); the parent reopens the file. This works the same on Windows and Linux.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import harness_agent
from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.core import Event, EventType

SRC_DIR = str(Path(harness_agent.__file__).resolve().parents[1])
REPETITIONS = 20

# Child program: argv = [db_path, scenario]. Every scenario ends the process with os._exit(0).
CHILD = r"""
import os
import sys
from datetime import datetime, timezone

from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.core import Event, EventType

db_path, scenario = sys.argv[1], sys.argv[2]
T0 = datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc)


def event(n):
    return Event(id=f"e{n}", session_id=sid, type=EventType.USER_MESSAGE, timestamp=T0,
                 payload={"n": n})


class ExitOnCommit:
    def __init__(self, real):
        self._real = real

    def commit(self):
        os._exit(0)

    def __getattr__(self, name):
        return getattr(self._real, name)


class ExitAfterInsert:
    def __init__(self, real):
        self._real = real

    def execute(self, sql, *args):
        cursor = self._real.execute(sql, *args)
        if sql.lstrip().upper().startswith("INSERT INTO EVENTS"):
            os._exit(0)
        return cursor

    def __getattr__(self, name):
        return getattr(self._real, name)


store = SqliteSessionStore(db_path)
sid = store.create_session().id
print(sid, flush=True)
if scenario == "abrupt":
    for n in range(1, 6):
        store.save_event(event(n))
else:
    store.save_event(event(1))
    store.save_event(event(2))
    store._conn = (ExitOnCommit if scenario == "cut-before-commit" else ExitAfterInsert)(
        store._conn
    )
    store.save_event(event(3))
os._exit(0)
"""


def run_child(db_path: Path, scenario: str) -> str:
    """Run the child program and return the session id it created."""
    env = {**os.environ, "PYTHONPATH": SRC_DIR}
    result = subprocess.run(
        [sys.executable, "-c", CHILD, str(db_path), scenario],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def ids(events: list[Event]) -> list[str]:
    return [e.id for e in events]


# --- T006: AC-01 ---------------------------------------------------------------------------------


@pytest.mark.parametrize("attempt", range(REPETITIONS))
def test_confirmed_events_survive_an_abrupt_exit(tmp_path: Path, attempt: int) -> None:
    db = tmp_path / f"sessions-{attempt}.db"
    sid = run_child(db, "abrupt")

    with SqliteSessionStore(db) as reopened:
        events = reopened.load_session(sid)

    assert ids(events) == ["e1", "e2", "e3", "e4", "e5"]
    assert [e.payload["n"] for e in events] == [1, 2, 3, 4, 5]
    assert all(e.type is EventType.USER_MESSAGE for e in events)


def test_a_confirmed_event_is_visible_from_a_second_connection(tmp_path: Path) -> None:
    db = tmp_path / "sessions.db"
    with SqliteSessionStore(db) as writer, SqliteSessionStore(db) as reader:
        sid = writer.create_session().id
        writer.save_event(Event(id="e1", session_id=sid, type=EventType.USER_MESSAGE))

        assert ids(reader.load_session(sid)) == ["e1"]


def test_the_store_asks_the_engine_for_full_durability(tmp_path: Path) -> None:
    with SqliteSessionStore(tmp_path / "sessions.db") as store:
        assert store._conn is not None
        full = 2
        assert store._conn.execute("PRAGMA synchronous").fetchone()[0] == full


# --- T007: AC-02 ---------------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", ["cut-before-commit", "cut-after-insert"])
@pytest.mark.parametrize("attempt", range(REPETITIONS))
def test_a_cut_write_leaves_the_database_intact(
    tmp_path: Path, scenario: str, attempt: int
) -> None:
    db = tmp_path / f"sessions-{attempt}.db"
    sid = run_child(db, scenario)

    with SqliteSessionStore(db) as reopened:
        assert reopened._conn is not None
        assert reopened._conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert ids(reopened.load_session(sid)) == ["e1", "e2"]

        reopened.save_event(Event(id="e4", session_id=sid, type=EventType.USER_MESSAGE))
        seqs = reopened._conn.execute(
            "SELECT seq FROM events WHERE session_id = ? ORDER BY seq", (sid,)
        ).fetchall()

    assert [row[0] for row in seqs] == [1, 2, 3]
