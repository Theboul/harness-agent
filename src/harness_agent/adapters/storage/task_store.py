"""SQLite store of the task criteria: the source of truth that only the harness writes (HU-11-01).

``SqliteTaskStore`` implements the ``TaskCriteria`` port on the ``criterios`` table and adds what
the port lacks: ``start_task`` (create the session, the criteria, the integrity seal and the
read-only JSON copy in one transaction) and ``verify_export`` (compare the copy with what SQLite
says, restore it and report the anomaly).

Integrity: every write recomputes a seal (the SHA-256 of the canonical export) kept in
``criterios_sello``. Every read checks each row against the rules of the table and the seal against
the rows; any mismatch publishes ``criteria_tampered`` and fails closed with
``CriteriaIntegrityError``. The seal has no secret key: it catches accidental or naive edits, not
a process with the same privileges that rewrites rows and seal together (PD-06, HU-IN-02).
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from harness_agent.adapters.storage.criteria_export import (
    EXPORT_FILE_NAME,
    CriterionRecord,
    canonical_export,
    export_matches,
    fingerprint,
    write_readonly,
)
from harness_agent.adapters.storage.errors import (
    CriteriaIntegrityError,
    CriteriaNotFound,
    ExportError,
    SessionStoreError,
)
from harness_agent.adapters.storage.sqlite_session_store import SqliteSessionStore
from harness_agent.core import (
    CriterionKind,
    Event,
    EventBus,
    EventType,
    TaskCriteria,
    TaskCriteriaItem,
    TaskDefinition,
)

_ENGINE_ERROR = "Error del almacén de criterios."
_INTEGRITY_ERROR = "Los criterios guardados muestran señales de alteración."
_NOT_FOUND_ERROR = "El criterio indicado no existe."
_SESSION_ID_ERROR = "El identificador de sesión no es válido."
_EVIDENCE_ERROR = "La evidencia no puede estar vacía."
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_ACTIVE = "active"
_MAX_ROW_ID_DIGITS = 18

TAMPER_MODIFIED = "copia_modificada"
TAMPER_MISSING = "copia_ausente"
TAMPER_NOT_REGULAR = "copia_no_regular"
TAMPER_DATABASE = "base_alterada"

_SELECT = (
    "SELECT id, orden, descripcion, tipo, comando, condicion, passes, evidencia "
    "FROM criterios WHERE sesion_id = ? ORDER BY orden"
)


@dataclass(frozen=True)
class StartedTask:
    """What starting a task produced.

    Attributes:
        session_id: The new session, whose goal is the objective of the task.
        export_path: The read-only JSON copy of its criteria.
    """

    session_id: str
    export_path: Path


class _Tampered(Exception):
    """Internal: the rows or the seal do not hold together."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _record(row: tuple[object, ...], expected_order: int) -> CriterionRecord:
    """The record of a stored row, or ``_Tampered`` if the row breaks any rule of the table."""
    row_id, order, description, kind, command, condition, passes, evidence = row
    if not isinstance(row_id, int) or order != expected_order or not _text(description):
        raise _Tampered
    if passes not in (0, 1) or not (evidence is None or isinstance(evidence, str)):
        raise _Tampered
    if passes == 1 and not _text(evidence):
        raise _Tampered
    if kind == CriterionKind.OBJECTIVE.value:
        if not (_text(command) and _text(condition)):
            raise _Tampered
    elif kind == CriterionKind.SEMANTIC.value:
        if command is not None or condition is not None:
            raise _Tampered
    else:
        raise _Tampered
    assert isinstance(description, str)
    return CriterionRecord(
        id=row_id,
        order=expected_order,
        description=description,
        kind=str(kind),
        command=None if command is None else str(command),
        condition=None if condition is None else str(condition),
        passes=passes == 1,
        evidence=evidence if isinstance(evidence, str) else None,
    )


def _item(record: CriterionRecord) -> TaskCriteriaItem:
    return TaskCriteriaItem(
        id=str(record.id),
        description=record.description,
        passes=record.passes,
        evidence=record.evidence,
        command=record.command,
    )


class SqliteTaskStore(TaskCriteria):
    """Task criteria on the same database as the sessions.

    Args:
        store: The session store whose connection (and so whose transactions) is shared.
        exports_dir: Folder under which each session gets ``<session>/criterios.json``.
        bus: Where ``criteria_tampered`` is published; ``None`` publishes nothing.
        clock: Returns the time of published events; defaults to UTC now.
        id_factory: Returns new unique identifiers (sessions and events).
    """

    def __init__(
        self,
        store: SqliteSessionStore,
        *,
        exports_dir: Path,
        bus: EventBus | None = None,
        clock: Callable[[], datetime] = _utc_now,
        id_factory: Callable[[], str] = _new_id,
    ) -> None:
        self._store = store
        self._exports_dir = exports_dir
        self._bus = bus
        self._clock = clock
        self._id_factory = id_factory

    def export_path(self, session_id: str) -> Path:
        """Where the read-only copy of ``session_id`` lives.

        Raises:
            CriteriaNotFound: The identifier is not a safe file name.
        """
        if not _SAFE_ID.match(session_id):
            raise CriteriaNotFound(_SESSION_ID_ERROR)
        return self._exports_dir / session_id / EXPORT_FILE_NAME

    # --- start --------------------------------------------------------------------------

    def start_task(self, task: TaskDefinition, *, model: str | None = None) -> StartedTask:
        """Create the session, the criteria (all pending), the seal and the copy, or nothing.

        Raises:
            ExportError: The copy could not be written (nothing is left behind).
            SessionStoreError: The store is closed or the engine failed.
        """
        conn = self._store.connection()
        session_id = self._id_factory()
        destination = self._new_export_path(session_id)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO sessions (id, status, created_at, model, goal, parent_id) "
                "VALUES (?, ?, ?, ?, ?, NULL)",
                (session_id, _ACTIVE, self._clock_utc().isoformat(), model, task.objective),
            )
            records: list[CriterionRecord] = []
            for order, criterion in enumerate(task.criteria, start=1):
                cursor = conn.execute(
                    "INSERT INTO criterios (sesion_id, orden, descripcion, tipo, comando, "
                    "condicion) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        session_id,
                        order,
                        criterion.description,
                        criterion.kind.value,
                        criterion.command,
                        criterion.expectation,
                    ),
                )
                assert cursor.lastrowid is not None
                records.append(
                    CriterionRecord(
                        id=cursor.lastrowid,
                        order=order,
                        description=criterion.description,
                        kind=criterion.kind.value,
                        command=criterion.command,
                        condition=criterion.expectation,
                        passes=False,
                        evidence=None,
                    )
                )
            data = canonical_export(records)
            conn.execute(
                "INSERT INTO criterios_sello (sesion_id, huella) VALUES (?, ?)",
                (session_id, fingerprint(data)),
            )
            write_readonly(destination, data)
            conn.commit()
        except BaseException as error:
            conn.rollback()
            self._discard_copy(destination)
            if isinstance(error, sqlite3.Error):
                raise SessionStoreError(_ENGINE_ERROR) from None
            raise
        return StartedTask(session_id=session_id, export_path=destination)

    def _new_export_path(self, session_id: str) -> Path:
        """The copy path of an identifier we just generated; an unsafe one is a store error."""
        try:
            return self.export_path(session_id)
        except CriteriaNotFound:
            raise SessionStoreError(_SESSION_ID_ERROR) from None

    # --- the TaskCriteria port ----------------------------------------------------------

    def load_criteria(self, session_id: str) -> list[TaskCriteriaItem]:
        """The criteria of the session in order, read from SQLite and verified."""
        return [_item(record) for record in self._verified(session_id)]

    def get_pending(self, session_id: str) -> list[TaskCriteriaItem]:
        """The verified criteria that have not passed yet."""
        return [item for item in self.load_criteria(session_id) if not item.passes]

    def mark_passes(self, criteria_id: str, evidence: str) -> None:
        """Mark a criterion as passed; only this changes, and the seal and the copy follow.

        Raises:
            CriteriaNotFound: ``criteria_id`` is not the identifier of a stored criterion.
            ValueError: ``evidence`` is empty.
            CriteriaIntegrityError: The stored criteria show signs of alteration.
        """
        row_id = self._row_id(criteria_id)
        if not evidence.strip():
            raise ValueError(_EVIDENCE_ERROR)
        conn = self._store.connection()
        previous: tuple[Path, bytes] | None = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            found = conn.execute(
                "SELECT sesion_id FROM criterios WHERE id = ?", (row_id,)
            ).fetchone()
            if found is None:
                raise CriteriaNotFound(_NOT_FOUND_ERROR)
            session_id = str(found[0])
            destination = self.export_path(session_id)
            previous = (destination, canonical_export(self._verified(session_id)))
            conn.execute(
                "UPDATE criterios SET passes = 1, evidencia = ? WHERE id = ?", (evidence, row_id)
            )
            data = canonical_export(self._records(session_id))
            conn.execute(
                "UPDATE criterios_sello SET huella = ? WHERE sesion_id = ?",
                (fingerprint(data), session_id),
            )
            write_readonly(destination, data)
            conn.commit()
        except BaseException as error:
            conn.rollback()
            if previous is not None:
                self._restore_quietly(*previous)
            if isinstance(error, sqlite3.Error):
                raise SessionStoreError(_ENGINE_ERROR) from None
            raise

    def export_readonly_copy(self, session_id: str, destination: Path) -> None:
        """Write the verified criteria as a read-only JSON copy at ``destination``."""
        write_readonly(destination, canonical_export(self._verified(session_id)))

    # --- verification of the copy -------------------------------------------------------

    def verify_export(self, session_id: str) -> bool:
        """Whether the copy on disk is what SQLite says; if not, restore it and report it.

        Returns:
            ``True`` if the copy was intact, ``False`` if it was altered and has been restored.

        Raises:
            CriteriaIntegrityError: The database itself shows signs of alteration.
            ExportError: The copy was altered and could not be restored.
        """
        destination = self.export_path(session_id)
        data = canonical_export(self._verified(session_id))
        if export_matches(destination, data):
            return True
        if destination.is_symlink() or (destination.exists() and not destination.is_file()):
            motive = TAMPER_NOT_REGULAR
        elif not destination.exists():
            motive = TAMPER_MISSING
        else:
            motive = TAMPER_MODIFIED
        try:
            write_readonly(destination, data)
        finally:
            self._report(session_id, motive)
        return False

    # --- internals ----------------------------------------------------------------------

    def _clock_utc(self) -> datetime:
        value = self._clock()
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    @staticmethod
    def _row_id(criteria_id: str) -> int:
        valid = criteria_id.isascii() and criteria_id.isdigit()
        if not valid or len(criteria_id) > _MAX_ROW_ID_DIGITS or int(criteria_id) < 1:
            raise CriteriaNotFound(_NOT_FOUND_ERROR)
        return int(criteria_id)

    def _records(self, session_id: str) -> list[CriterionRecord]:
        """The rows of the session as records; raises ``_Tampered`` on any broken rule."""
        try:
            rows = self._store.connection().execute(_SELECT, (session_id,)).fetchall()
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        return [_record(row, position) for position, row in enumerate(rows, start=1)]

    def _verified(self, session_id: str) -> list[CriterionRecord]:
        """The records, after checking each row and the seal; tampering is reported and raised."""
        try:
            records = self._records(session_id)
            seal = self._seal(session_id)
            if not records and seal is None:
                return records
            if seal != fingerprint(canonical_export(records)):
                raise _Tampered
            return records
        except _Tampered:
            self._report(session_id, TAMPER_DATABASE)
            raise CriteriaIntegrityError(_INTEGRITY_ERROR) from None

    def _seal(self, session_id: str) -> str | None:
        try:
            row = (
                self._store.connection()
                .execute("SELECT huella FROM criterios_sello WHERE sesion_id = ?", (session_id,))
                .fetchone()
            )
        except sqlite3.Error:
            raise SessionStoreError(_ENGINE_ERROR) from None
        return None if row is None else str(row[0])

    def _report(self, session_id: str, motive: str) -> None:
        """Publish ``criteria_tampered`` with the motive only (no content, no paths)."""
        if self._bus is None:
            return
        self._bus.emit(
            Event(
                id=self._id_factory(),
                session_id=session_id,
                type=EventType.CRITERIA_TAMPERED,
                timestamp=self._clock_utc(),
                payload={"motivo": motive},
            )
        )

    @staticmethod
    def _discard_copy(destination: Path) -> None:
        """Remove a copy (and its folder if empty) that belongs to a task that was not stored."""
        try:
            if destination.is_file():
                destination.chmod(0o600)
                destination.unlink()
            destination.parent.rmdir()
        except OSError:
            pass

    @staticmethod
    def _restore_quietly(destination: Path, data: bytes) -> None:
        """Put back the copy that matches the database after a failed change."""
        try:
            write_readonly(destination, data)
        except ExportError:
            pass
