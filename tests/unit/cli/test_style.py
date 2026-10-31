"""Tests of the color decision of the terminal (HU-06-05 / T002, AC-09, FR-015, FR-016)."""

from __future__ import annotations

import io
import re

import pytest

from harness_agent.cli.style import ESCAPE, PLAIN, Style, detect_style


class Terminal(io.StringIO):
    """A stream that says it is a terminal."""

    def isatty(self) -> bool:
        return True


class BrokenIsatty(io.StringIO):
    def isatty(self) -> bool:
        raise ValueError("closed")


class TestDetectStyle:
    def test_a_string_stream_is_not_a_terminal(self) -> None:
        assert detect_style(io.StringIO(), environ={}, platform="linux") == PLAIN

    def test_a_terminal_on_linux_gets_color(self) -> None:
        assert detect_style(Terminal(), environ={"TERM": "xterm"}, platform="linux").enabled

    @pytest.mark.parametrize("value", ["1", "x", "0", "true"])
    def test_no_color_with_any_value_turns_color_off(self, value: str) -> None:
        style = detect_style(Terminal(), environ={"NO_COLOR": value}, platform="linux")
        assert not style.enabled

    def test_an_empty_no_color_is_ignored(self) -> None:
        assert detect_style(Terminal(), environ={"NO_COLOR": ""}, platform="linux").enabled

    def test_a_dumb_terminal_gets_no_color(self) -> None:
        assert not detect_style(Terminal(), environ={"TERM": "dumb"}, platform="linux").enabled

    @pytest.mark.parametrize(
        "environ",
        [
            {"WT_SESSION": "abc"},
            {"ANSICON": "80x25"},
            {"ConEmuANSI": "ON"},
            {"TERM_PROGRAM": "vscode"},
        ],
    )
    def test_windows_needs_a_sign_of_ansi_support(self, environ: dict[str, str]) -> None:
        assert detect_style(Terminal(), environ=environ, platform="win32").enabled

    def test_the_classic_windows_console_gets_no_color(self) -> None:
        assert not detect_style(Terminal(), environ={}, platform="win32").enabled

    def test_windows_conemu_off_gets_no_color(self) -> None:
        style = detect_style(Terminal(), environ={"ConEmuANSI": "OFF"}, platform="win32")
        assert not style.enabled

    def test_a_stream_that_fails_to_answer_gets_no_color(self) -> None:
        assert not detect_style(BrokenIsatty(), environ={}, platform="linux").enabled

    def test_a_stream_without_isatty_gets_no_color(self) -> None:
        class Bare:
            pass

        assert not detect_style(Bare(), environ={}, platform="linux").enabled


class TestPaint:
    def test_plain_style_returns_the_same_text(self) -> None:
        assert PLAIN.paint("hola", "red", "bold") == "hola"

    def test_enabled_style_wraps_the_text(self) -> None:
        painted = Style(enabled=True).paint("hola", "red")
        assert painted.startswith(ESCAPE) and painted.endswith(ESCAPE + "[0m")
        assert "hola" in painted

    def test_the_text_without_codes_is_the_original(self) -> None:
        painted = Style(enabled=True).paint("hola", "green", "bold")
        assert re.sub(re.escape(ESCAPE) + r"\[[0-9;]*m", "", painted) == "hola"

    def test_unknown_names_are_ignored(self) -> None:
        assert Style(enabled=True).paint("hola", "magic") == "hola"

    def test_empty_text_is_not_wrapped(self) -> None:
        assert Style(enabled=True).paint("", "red") == ""
