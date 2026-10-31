"""``.env`` reader (proposed HU-00-08.1): tolerant, no expansion, real environment wins."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.adapters.system import (
    MAX_DOTENV_BYTES,
    merge_environment,
    parse_dotenv,
    read_dotenv,
)

SENTINEL = "VALOR-DE-PRUEBA-123"


def write(tmp_path: Path, text: str) -> Path:
    target = tmp_path / ".env"
    target.write_bytes(text.encode("utf-8"))
    return target


def test_plain_quoted_commented_and_blank_lines() -> None:
    text = (
        "# comment\n"
        "\n"
        f"A={SENTINEL}\n"
        "B='single value'\n"
        'C="double value"\n'
        "export D=exported\n"
        "  E = spaced  \n"
        "F=value # trailing comment\n"
        'G="quoted # not a comment"\n'
        "H=a#b\n"
    )

    result = parse_dotenv(text)

    assert result.skipped == 0
    assert result.values == {
        "A": SENTINEL,
        "B": "single value",
        "C": "double value",
        "D": "exported",
        "E": "spaced",
        "F": "value",
        "G": "quoted # not a comment",
        "H": "a#b",
    }


def test_there_is_no_variable_expansion() -> None:
    result = parse_dotenv("A=$HOME\nB=${HOME}\nC=$(whoami)\nD=`id`\n")

    assert result.values == {"A": "$HOME", "B": "${HOME}", "C": "$(whoami)", "D": "`id`"}


def test_empty_values_are_not_applied_nor_counted_as_invalid() -> None:
    result = parse_dotenv("A=\nB=''\nC=   \n")

    assert result.values == {} and result.skipped == 0


@pytest.mark.parametrize(
    "line",
    [
        "no equals sign",
        "=value",
        "1BAD=value",
        "BAD NAME=value",
        "BAD-NAME=value",
        "A='unterminated",
        "A='x' trailing",
        "A=with\x00control",
    ],
)
def test_odd_lines_are_skipped_and_counted_while_valid_ones_apply(line: str) -> None:
    result = parse_dotenv(f"{line}\nGOOD=ok\n")

    assert result.values == {"GOOD": "ok"}
    assert result.skipped == 1


def test_the_last_duplicate_wins() -> None:
    assert parse_dotenv("A=1\nA=2\n").values == {"A": "2"}


def test_windows_line_endings_and_bom(tmp_path: Path) -> None:
    result = read_dotenv(write(tmp_path, "﻿A=1\r\nB=2\r\n"))

    assert result.values == {"A": "1", "B": "2"} and not result.unreadable


def test_a_missing_file_is_empty_and_not_a_problem(tmp_path: Path) -> None:
    result = read_dotenv(tmp_path / ".env")

    assert result.values == {} and result.skipped == 0 and not result.unreadable


def test_a_directory_instead_of_a_file_is_unreadable(tmp_path: Path) -> None:
    folder = tmp_path / ".env"
    folder.mkdir()

    assert read_dotenv(folder).unreadable


def test_a_file_that_is_not_utf8_is_unreadable_and_applies_nothing(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    target.write_bytes(b"A=\xff\xfe\n")

    result = read_dotenv(target)

    assert result.unreadable and result.values == {}


def test_a_file_over_the_size_limit_is_unreadable(tmp_path: Path) -> None:
    result = read_dotenv(write(tmp_path, "A=" + "x" * MAX_DOTENV_BYTES))

    assert result.unreadable and result.values == {}


def test_merge_never_overrides_the_real_environment() -> None:
    real = {"A": "real", "KEEP": "kept"}

    merged = merge_environment(real, {"A": "from-file", "B": "new"})

    assert merged == {"A": "real", "KEEP": "kept", "B": "new"}
    assert real == {"A": "real", "KEEP": "kept"}  # the input is not mutated


def test_results_never_expose_values_in_their_text() -> None:
    result = parse_dotenv(f"A={SENTINEL}\nbad line {SENTINEL}\n")

    assert SENTINEL not in repr(result)
