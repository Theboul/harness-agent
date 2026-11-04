"""The ``AuditLog`` protocol of the core against its real SQLite implementation (HU-05-05).

The same assertions run against a small in-memory log (kept here: the shared doubles are protected)
and against ``SqliteAuditStore`` on a real file, so the two cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from harness_agent.adapters.storage import SqliteAuditStore, SqliteSessionStore
from harness_agent.core import AuditEntry, AuditLog, AuditRow

T0 = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


class MemoryAuditLog:
    def __init__(self) -> None:
        self._rows: list[AuditRow] = []

    def record_decision(self, entry: AuditEntry) -> None:
        self._rows.append(
            AuditRow(
                session_id=entry.session_id,
                parent_id=None,
                call_id=entry.call_id,
                tool=entry.tool,
                arguments=entry.arguments,
                decision=entry.decision,
                resolution=entry.resolution,
                reason=entry.reason,
                action=None,
                source=None,
                origin=entry.origin,
                decided_at=entry.decided_at,
                resolved_at=None,
            )
        )

    def record_resolution(
        self,
        session_id: str,
        call_id: str,
        resolution: str,
        action: str | None,
        source: str | None,
        resolved_at: datetime,
    ) -> None:
        for index in range(len(self._rows) - 1, -1, -1):
            row = self._rows[index]
            if (row.session_id, row.call_id) == (session_id, call_id):
                self._rows[index] = replace(
                    row,
                    resolution=resolution,
                    action=action,
                    source=source,
                    resolved_at=resolved_at,
                )
                return

    def rows(self, session_id: str, limit: int) -> list[AuditRow]:
        own = [row for row in self._rows if row.session_id == session_id]
        return own[-limit:] if limit > 0 else []

    def count(self, session_id: str) -> int:
        return len([row for row in self._rows if row.session_id == session_id])


@pytest.fixture(params=["memory", "sqlite"])
def log(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[tuple[AuditLog, str]]:
    if request.param == "memory":
        yield MemoryAuditLog(), "s1"
        return
    sessions = SqliteSessionStore(tmp_path / "sessions.db")
    try:
        yield SqliteAuditStore(sessions), sessions.create_session(model="fake/test").id
    finally:
        sessions.close()


def entry(session: str, call: str) -> AuditEntry:
    return AuditEntry(
        session_id=session,
        call_id=call,
        tool="leer_archivo",
        arguments="{}",
        decision="allow",
        resolution="permitida",
        reason=None,
        origin="agente",
        decided_at=T0,
    )


def test_the_implementation_is_an_audit_log(log: tuple[AuditLog, str]) -> None:
    assert log[0].count(log[1]) == 0 and log[0].rows(log[1], 10) == []


def test_the_rows_come_back_in_order_and_only_the_latest_ones_up_to_the_limit(
    log: tuple[AuditLog, str],
) -> None:
    audit, session = log
    for index in range(4):
        audit.record_decision(entry(session, f"c{index}"))

    assert [row.call_id for row in audit.rows(session, 10)] == ["c0", "c1", "c2", "c3"]
    assert [row.call_id for row in audit.rows(session, 2)] == ["c2", "c3"]
    assert audit.rows(session, 0) == []
    assert audit.count(session) == 4


def test_a_resolution_completes_the_latest_row_of_the_call(log: tuple[AuditLog, str]) -> None:
    audit, session = log
    audit.record_decision(entry(session, "c1"))
    audit.record_decision(entry(session, "c1"))

    audit.record_resolution(session, "c1", "aprobada", "approve_once", "user", T0 + timedelta(1))

    rows = audit.rows(session, 10)
    assert [row.resolution for row in rows] == ["permitida", "aprobada"]
    assert (rows[1].action, rows[1].source) == ("approve_once", "user")


def test_a_resolution_without_a_row_is_not_an_error(log: tuple[AuditLog, str]) -> None:
    audit, session = log
    audit.record_decision(entry(session, "c1"))

    audit.record_resolution(session, "otra", "rechazada", None, None, T0)

    assert [row.resolution for row in audit.rows(session, 10)] == ["permitida"]
