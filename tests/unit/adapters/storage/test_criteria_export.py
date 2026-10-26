"""Canonical export of the criteria, its fingerprint and the read-only copy (HU-11-01 / T004)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.storage.criteria_export import (
    EXPORT_FILE_NAME,
    CriterionRecord,
    canonical_export,
    export_matches,
    fingerprint,
    write_readonly,
)
from harness_agent.adapters.storage.errors import ExportError

SENTINEL = "VALOR-DE-PRUEBA-123"

OBJECTIVE = CriterionRecord(
    id=7,
    order=1,
    description="El email es obligatorio",
    kind="objetivo",
    command="pytest tests/test_email.py",
    condition="codigo_salida == 0",
    passes=False,
    evidence=None,
)
SEMANTIC = CriterionRecord(
    id=8,
    order=2,
    description="El mensaje es claro",
    kind="semantico",
    command=None,
    condition=None,
    passes=True,
    evidence="revisado por una persona",
)


def is_read_only(path: Path) -> bool:
    return not os.access(path, os.W_OK)


def test_export_file_name() -> None:
    assert EXPORT_FILE_NAME == "criterios.json"


def test_canonical_export_follows_the_prototype_of_the_story() -> None:
    data = canonical_export([OBJECTIVE, SEMANTIC])

    assert json.loads(data) == [
        {
            "descripcion": "El email es obligatorio",
            "id": 7,
            "passes": False,
            "tipo": "objetivo",
            "verificacion": {
                "comando": "pytest tests/test_email.py",
                "espera": "codigo_salida == 0",
            },
        },
        {
            "descripcion": "El mensaje es claro",
            "evidencia": "revisado por una persona",
            "id": 8,
            "passes": True,
            "tipo": "semantico",
        },
    ]


def test_canonical_export_is_deterministic_utf8_with_final_newline() -> None:
    accented = CriterionRecord(1, 1, "Ñandú — ✓", "semantico", None, None, False, None)
    first = canonical_export([accented])
    assert first == canonical_export([accented])
    assert first.endswith(b"\n")
    assert "Ñandú — ✓" in first.decode("utf-8")
    assert canonical_export([]) == b"[]\n"


def test_fingerprint_is_sha256_hex_and_changes_with_content() -> None:
    a, b = canonical_export([OBJECTIVE]), canonical_export([SEMANTIC])
    assert len(fingerprint(a)) == 64 and fingerprint(a) != fingerprint(b)
    assert fingerprint(a) == fingerprint(a)


def test_write_readonly_creates_folders_and_a_read_only_copy(tmp_path: Path) -> None:
    destination = tmp_path / "tareas" / "s1" / EXPORT_FILE_NAME
    data = canonical_export([OBJECTIVE])

    write_readonly(destination, data)

    assert destination.read_bytes() == data
    assert is_read_only(destination)
    assert not list(destination.parent.glob("*.tmp"))
    assert export_matches(destination, data)


def test_write_readonly_replaces_an_existing_read_only_copy(tmp_path: Path) -> None:
    destination = tmp_path / EXPORT_FILE_NAME
    write_readonly(destination, b"one\n")

    write_readonly(destination, b"two\n")

    assert destination.read_bytes() == b"two\n"
    assert is_read_only(destination)


def test_write_readonly_replaces_a_folder_in_its_place(tmp_path: Path) -> None:
    destination = tmp_path / EXPORT_FILE_NAME
    (destination / "inner").mkdir(parents=True)
    (destination / "inner" / "x.txt").write_text("x")
    os.chmod(destination / "inner" / "x.txt", 0o444)

    write_readonly(destination, b"data\n")

    assert destination.is_file() and destination.read_bytes() == b"data\n"


def test_write_readonly_replaces_a_stale_temporary_file(tmp_path: Path) -> None:
    destination = tmp_path / EXPORT_FILE_NAME
    stale = tmp_path / f"{EXPORT_FILE_NAME}.tmp"
    stale.write_text("old")
    os.chmod(stale, 0o444)

    write_readonly(destination, b"fresh\n")

    assert destination.read_bytes() == b"fresh\n"
    assert not stale.exists()


def test_write_readonly_replaces_a_symbolic_link_without_touching_its_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.txt"
    target.write_text("keep")
    destination = tmp_path / EXPORT_FILE_NAME
    try:
        destination.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available")

    write_readonly(destination, b"data\n")

    assert target.read_text() == "keep"
    assert not destination.is_symlink() and destination.read_bytes() == b"data\n"


def test_write_readonly_failure_is_an_export_error_without_details(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    destination = blocker / "sub" / EXPORT_FILE_NAME  # the parent cannot be a folder

    with pytest.raises(ExportError) as caught:
        write_readonly(destination, b"data\n")

    assert str(tmp_path) not in str(caught.value) and SENTINEL not in str(caught.value)


def test_export_matches_detects_every_kind_of_alteration(tmp_path: Path) -> None:
    destination = tmp_path / EXPORT_FILE_NAME
    data = canonical_export([OBJECTIVE])
    assert not export_matches(destination, data)  # missing

    write_readonly(destination, data)
    assert export_matches(destination, data)
    assert not export_matches(destination, canonical_export([SEMANTIC]))  # other content

    destination.chmod(0o644)
    destination.write_bytes(data + b" ")
    assert not export_matches(destination, data)  # modified

    destination.unlink()
    destination.mkdir()
    assert not export_matches(destination, data)  # not a regular file


def test_export_matches_rejects_a_symbolic_link_even_with_equal_content(tmp_path: Path) -> None:
    data = canonical_export([OBJECTIVE])
    real = tmp_path / "real.json"
    real.write_bytes(data)
    destination = tmp_path / EXPORT_FILE_NAME
    try:
        destination.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are not available")

    assert not export_matches(destination, data)


def test_a_failing_permission_change_does_not_stop_the_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / EXPORT_FILE_NAME
    destination.write_text("old")
    real_chmod = os.chmod
    calls: list[int] = []

    def flaky_chmod(path: object, mode: int) -> None:
        calls.append(mode)
        if len(calls) == 1:  # the one that makes the old copy writable
            raise PermissionError
        real_chmod(path, mode)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "chmod", flaky_chmod)

    write_readonly(destination, b"new\n")

    assert destination.read_bytes() == b"new\n"


def test_cleanup_failure_after_a_write_error_still_reports_an_export_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_replace(*_args: object) -> None:
        raise PermissionError

    def broken_remove(_path: Path) -> None:
        raise PermissionError

    destination = tmp_path / EXPORT_FILE_NAME
    monkeypatch.setattr(os, "replace", broken_replace)
    monkeypatch.setattr("harness_agent.adapters.storage.criteria_export._remove", broken_remove)

    with pytest.raises(ExportError):
        write_readonly(destination, b"data\n")


def test_an_unreadable_copy_does_not_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    destination = tmp_path / EXPORT_FILE_NAME
    destination.write_bytes(b"data\n")

    real_open = Path.open

    def unreadable(self: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if "r" in mode:
            raise PermissionError
        return real_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", unreadable)

    assert not export_matches(destination, b"data\n")
