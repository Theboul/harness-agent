"""child_environment: the environment of a command, without the provider keys (HU-01-04 / T003)."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from harness_agent.adapters.system.shell_environment import child_environment

BASE: Mapping[str, str] = {
    "PATH": "/usr/bin",
    "HOME": "/home/u",
    "ANTHROPIC_API_KEY": "v-sint-1",
    "OPENAI_API_KEY": "v-sint-2",
    "GIT_CONFIG": "kept",
}
REMOVED = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def test_removes_exactly_the_named_variables() -> None:
    result = child_environment(BASE, REMOVED, windows=False)
    assert result == {"PATH": "/usr/bin", "HOME": "/home/u", "GIT_CONFIG": "kept"}


def test_does_not_change_the_input_and_returns_a_new_dict() -> None:
    before = dict(BASE)
    result = child_environment(BASE, REMOVED, windows=False)
    assert dict(BASE) == before
    assert isinstance(result, dict)
    result["EXTRA"] = "x"
    assert "EXTRA" not in BASE


def test_nothing_to_remove_keeps_everything() -> None:
    assert child_environment(BASE, (), windows=False) == dict(BASE)


def test_names_that_are_not_present_are_ignored() -> None:
    assert child_environment(BASE, ("NO_EXISTE",), windows=False) == dict(BASE)


def test_an_empty_environment_stays_empty() -> None:
    assert child_environment({}, REMOVED, windows=True) == {}


@pytest.mark.parametrize("name", ["anthropic_api_key", "Anthropic_Api_Key"])
def test_on_windows_names_are_compared_ignoring_case(name: str) -> None:
    environ = {name: "v-sint-3", "PATH": "C:\\Windows"}
    assert child_environment(environ, ("ANTHROPIC_API_KEY",), windows=True) == {
        "PATH": "C:\\Windows"
    }


def test_on_other_systems_names_are_case_sensitive() -> None:
    environ = {"anthropic_api_key": "v-sint-3", "ANTHROPIC_API_KEY": "v-sint-4"}
    assert child_environment(environ, ("ANTHROPIC_API_KEY",), windows=False) == {
        "anthropic_api_key": "v-sint-3"
    }


def test_removes_nothing_else_even_with_similar_names() -> None:
    environ = {"ANTHROPIC_API_KEY_BACKUP": "keep", "ANTHROPIC_API_KEY": "gone"}
    assert child_environment(environ, ("ANTHROPIC_API_KEY",), windows=False) == {
        "ANTHROPIC_API_KEY_BACKUP": "keep"
    }
