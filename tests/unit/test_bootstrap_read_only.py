"""Composition root: the read-only mode (HU-05-07 / T004, T005)."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.bootstrap import (
    READ_ONLY_NOTICE,
    Composition,
    StartupArguments,
    StartupError,
    parse_arguments,
)
from harness_agent.cli.session_commands import READ_ONLY_LINE, format_model
from tests.unit.bootstrap_support import build, make_config


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class TestArguments:
    def test_the_flag_turns_it_on(self) -> None:
        assert parse_arguments(["--solo-lectura"]) == StartupArguments(read_only=True)
        assert parse_arguments([]).read_only is False

    def test_it_goes_with_a_task_in_any_order(self) -> None:
        first = parse_arguments(["--solo-lectura", "--tarea", "t.md"])
        last = parse_arguments(["--issue=12", "--solo-lectura"])

        assert (first.read_only, first.task_file) == (True, "t.md")
        assert (last.read_only, last.issue_number) == (True, 12)

    def test_a_repeated_flag_is_an_error(self) -> None:
        with pytest.raises(StartupError, match="repetida"):
            parse_arguments(["--solo-lectura", "--solo-lectura"])

    def test_the_flag_takes_no_value(self) -> None:
        with pytest.raises(StartupError, match="no reconocido"):
            parse_arguments(["--solo-lectura=si"])


class TestComposition:
    def test_the_parameter_announces_the_mode(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path), read_only=True)

        assert READ_ONLY_NOTICE in composition.notices
        assert composition.model_view is not None and composition.model_view.read_only is True

    def test_the_configuration_turns_it_on_too(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        config = dataclasses.replace(make_config(tmp_path, workspace=tmp_path), read_only=True)

        composition = build(opened, config)

        assert READ_ONLY_NOTICE in composition.notices
        assert composition.model_view is not None and composition.model_view.read_only is True

    def test_neither_source_turns_the_other_off(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        config = dataclasses.replace(make_config(tmp_path, workspace=tmp_path), read_only=True)

        composition = build(opened, config, read_only=False)

        assert READ_ONLY_NOTICE in composition.notices

    def test_without_the_mode_nothing_changes(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))

        assert READ_ONLY_NOTICE not in composition.notices
        assert composition.model_view is not None and composition.model_view.read_only is False

    def test_the_notice_is_a_fixed_line_in_spanish(self) -> None:
        assert READ_ONLY_NOTICE.startswith("Modo de solo lectura activo")
        assert "\n" not in READ_ONLY_NOTICE


class TestModelCommand:
    def test_model_shows_the_mode_only_when_it_is_on(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        on = build(opened, make_config(tmp_path, workspace=tmp_path), read_only=True)
        off = build(opened, make_config(tmp_path / "otro", workspace=tmp_path))

        assert on.model_view is not None and off.model_view is not None
        assert format_model(on.model_view).splitlines()[-1] == READ_ONLY_LINE
        assert READ_ONLY_LINE not in format_model(off.model_view)
