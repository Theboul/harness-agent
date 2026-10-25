"""Canonical JSON export of the criteria and the read-only copy on disk (HU-11-01).

The export is a deterministic byte string: its SHA-256 is the fingerprint compared with the copy
on disk and also the integrity seal kept in SQLite. The copy is written read-only through a
temporary file and an atomic replace; whatever sits in its place (a modified file, a link, a
folder) is removed first, because restoring it is the point.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_agent.adapters.storage.errors import ExportError

EXPORT_FILE_NAME = "criterios.json"

_EXPORT_ERROR = "No se pudo escribir la copia de solo lectura de los criterios."


@dataclass(frozen=True)
class CriterionRecord:
    """One row of ``criterios`` as it is exported and sealed.

    Attributes:
        id: Row identifier.
        order: Position inside the task (1-based).
        description: What must be true.
        kind: ``objetivo`` or ``semantico``.
        command: Verification command (objective criteria only).
        condition: Expected condition of the command (objective criteria only).
        passes: Whether the harness marked the criterion as satisfied.
        evidence: Evidence given when it was marked, if any.
    """

    id: int
    order: int
    description: str
    kind: str
    command: str | None
    condition: str | None
    passes: bool
    evidence: str | None


def _entry(record: CriterionRecord) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": record.id,
        "tipo": record.kind,
        "descripcion": record.description,
        "passes": record.passes,
    }
    if record.command is not None:
        entry["verificacion"] = {"comando": record.command, "espera": record.condition}
    if record.evidence is not None:
        entry["evidencia"] = record.evidence
    return entry


def canonical_export(records: Sequence[CriterionRecord]) -> bytes:
    """The deterministic JSON bytes of ``records`` (in the order given)."""
    text = json.dumps(
        [_entry(record) for record in records], ensure_ascii=False, indent=2, sort_keys=True
    )
    return (text + "\n").encode("utf-8")


def fingerprint(data: bytes) -> str:
    """SHA-256 of ``data`` in hexadecimal."""
    return hashlib.sha256(data).hexdigest()


def _make_writable(path: str | os.PathLike[str]) -> None:
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def _remove(path: Path) -> None:
    """Remove whatever is at ``path`` (file, link or folder); nothing if there is nothing."""
    if path.is_symlink() or path.is_file():
        _make_writable(path)
        path.unlink()
    elif path.exists():

        def retry(function: Any, failing: str, _error: BaseException) -> None:
            _make_writable(failing)
            function(failing)

        shutil.rmtree(path, onexc=retry)


def write_readonly(destination: Path, data: bytes) -> None:
    """Write ``data`` at ``destination`` as a read-only file, replacing whatever is there.

    Raises:
        ExportError: The copy could not be written (no detail of the cause is given).
    """
    temporary = destination.with_name(destination.name + ".tmp")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        _remove(temporary)
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _remove(destination)
        os.replace(temporary, destination)
        os.chmod(destination, stat.S_IREAD)
    except OSError:
        try:
            _remove(temporary)
        except OSError:
            pass
        raise ExportError(_EXPORT_ERROR) from None


def export_matches(destination: Path, data: bytes) -> bool:
    """Whether ``destination`` is a regular file (not a link) whose content is ``data``."""
    try:
        if destination.is_symlink() or not destination.is_file():
            return False
        with destination.open("rb") as handle:
            return fingerprint(handle.read()) == fingerprint(data)
    except OSError:
        return False
