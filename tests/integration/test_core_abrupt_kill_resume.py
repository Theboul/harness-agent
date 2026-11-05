"""AC-01 of HU-00-05.1: a process killed from outside loses no confirmed event and is resumed.

The child (``core_kill_child.py``) runs the real system (``compose`` + ``run_session`` over a
SQLite file in ``tmp_path``) and says on one line of its standard output which events are already
confirmed. The parent kills it with ``Popen.kill`` (SIGKILL on Linux, ``TerminateProcess`` on
Windows: the process does not get to run anything), reopens the file and resumes the session in a
second process with ``/reanudar``. The parent synchronizes on that line, never on a fixed sleep,
and every wait has a limit. Nothing reaches the network or the repository.
"""

from __future__ import annotations

import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from types import TracebackType
from typing import Any

import pytest

import harness_agent

SRC_DIR = str(Path(harness_agent.__file__).resolve().parents[1])
HELPER = Path(__file__).resolve().with_name("core_kill_child.py")
CHECKPOINT = "CHECKPOINT "
RESULT = "RESULT "
WAIT = 60.0


def environment() -> dict[str, str]:
    return {**os.environ, "PYTHONPATH": SRC_DIR}


class Child:
    """A running child: its lines arrive through a queue; it is always killed on exit."""

    def __init__(self, mode: str, database: Path, workspace: Path, *extra: str) -> None:
        self._process = subprocess.Popen(
            [sys.executable, str(HELPER), mode, str(database), str(workspace), *extra],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment(),
        )
        self._lines: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        assert self._process.stdout is not None
        for line in self._process.stdout:
            self._lines.put(line.rstrip("\n"))
        self._lines.put(None)

    def checkpoint(self) -> dict[str, Any]:
        """The first ``CHECKPOINT`` line; fails with the child's error if it died before."""
        while True:
            try:
                line = self._lines.get(timeout=WAIT)
            except queue.Empty:
                raise AssertionError("the child did not announce a checkpoint in time") from None
            if line is None:
                self.kill()
                assert self._process.stderr is not None
                raise AssertionError(f"the child ended before its checkpoint: {self._stderr()}")
            if line.startswith(CHECKPOINT):
                payload: dict[str, Any] = json.loads(line[len(CHECKPOINT) :])
                return payload

    def _stderr(self) -> str:
        assert self._process.stderr is not None
        return self._process.stderr.read()

    def kill(self) -> None:
        self._process.kill()
        self._process.wait(timeout=30)

    @property
    def returncode(self) -> int | None:
        return self._process.poll()

    def __enter__(self) -> Child:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        if self._process.poll() is None:
            self.kill()
        for stream in (self._process.stdout, self._process.stderr):
            if stream is not None:
                stream.close()


def events_of(database: Path, session: str) -> list[tuple[int, str, str]]:
    """``(seq, id, type)`` of the session, read with a fresh connection to the file."""
    connection = sqlite3.connect(str(database))
    try:
        return connection.execute(
            "SELECT seq, id, type FROM events WHERE session_id = ? ORDER BY seq", (session,)
        ).fetchall()
    finally:
        connection.close()


def integrity_of(database: Path) -> str:
    connection = sqlite3.connect(str(database))
    try:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    finally:
        connection.close()


def resume_in_a_new_process(database: Path, workspace: Path, session: str) -> dict[str, Any]:
    """A second process opens the file and runs ``/reanudar <session>`` and one more request."""
    done = subprocess.run(
        [sys.executable, str(HELPER), "resume", str(database), str(workspace), session],
        capture_output=True,
        text=True,
        env=environment(),
        timeout=90,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    lines = [line for line in done.stdout.splitlines() if line.startswith(RESULT)]
    assert len(lines) == 1, done.stdout
    result: dict[str, Any] = json.loads(lines[0][len(RESULT) :])
    return result


def workspace_of(tmp_path: Path) -> Path:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    return workspace


def assert_resumed(
    database: Path,
    workspace: Path,
    session: str,
    announced: list[tuple[str, str]],
    *,
    exact: bool,
) -> dict[str, Any]:
    """The common checks after a kill: nothing confirmed lost, intact file, session resumed."""
    after_kill = [(event_id, kind) for _seq, event_id, kind in events_of(database, session)]
    if exact:
        assert after_kill == announced
    else:
        assert after_kill[: len(announced)] == announced  # the confirmed events are a prefix
    assert integrity_of(database) == "ok"

    result = resume_in_a_new_process(database, workspace, session)

    assert result["code"] == 0
    assert "Sesión reanudada" in result["output"]
    after_resume = events_of(database, session)
    assert [seq for seq, _id, _type in after_resume] == list(range(1, len(after_resume) + 1))
    assert len({event_id for _seq, event_id, _type in after_resume}) == len(after_resume)
    assert [(event_id, kind) for _seq, event_id, kind in after_resume][: len(after_kill)] == (
        after_kill
    )
    assert len(after_resume) > len(after_kill)  # the new request went into the resumed session
    assert integrity_of(database) == "ok"
    return result


def announced_events(checkpoint: dict[str, Any]) -> list[tuple[str, str]]:
    return [(event_id, kind) for event_id, kind in checkpoint["events"]]


def test_ac01_a_killed_process_with_the_provider_in_flight_loses_no_event_and_resumes(
    tmp_path: Path,
) -> None:
    database, workspace = tmp_path / "sesiones.db", workspace_of(tmp_path)
    with Child("block-provider", database, workspace) as child:
        checkpoint = child.checkpoint()
        child.kill()
        assert child.returncode is not None and child.returncode != 0  # killed, not finished

    announced = announced_events(checkpoint)
    assert [kind for _id, kind in announced].count("user_message") == 3  # three requests so far
    assert_resumed(database, workspace, checkpoint["session"], announced, exact=True)


def test_ac01_a_process_killed_in_a_tool_resumes_with_the_call_closed(
    tmp_path: Path,
) -> None:
    database, workspace = tmp_path / "sesiones.db", workspace_of(tmp_path)
    with Child("block-tool", database, workspace) as child:
        checkpoint = child.checkpoint()
        child.kill()

    announced = announced_events(checkpoint)
    kinds = [kind for _id, kind in announced]
    assert kinds[-2:] == ["tool_requested", "permission_decided"]  # the call in flight
    result = assert_resumed(database, workspace, checkpoint["session"], announced, exact=True)
    assert "cerró 1 llamada sin resultado" in result["output"]


@pytest.mark.parametrize("attempt", range(5))
def test_ac01_a_process_killed_while_writing_keeps_the_confirmed_events_as_a_prefix(
    tmp_path: Path, attempt: int
) -> None:
    database, workspace = tmp_path / f"sesiones-{attempt}.db", workspace_of(tmp_path)
    with Child("busy", database, workspace) as child:
        checkpoint = child.checkpoint()
        child.kill()  # the child was still writing when it died

    announced = announced_events(checkpoint)
    assert len(announced) >= 10
    assert_resumed(database, workspace, checkpoint["session"], announced, exact=False)
