"""environment_notice: the text that tells the model the system and the interpreter (T010)."""

from __future__ import annotations

import getpass
import os
from pathlib import Path

import pytest

from harness_agent.adapters.system.environment_notice import environment_notice


@pytest.mark.parametrize(
    ("system_name", "interpreter", "shown"),
    [("Windows", "powershell", "PowerShell"), ("Linux", "bash", "bash")],
)
def test_it_names_the_system_and_the_interpreter(
    system_name: str, interpreter: str, shown: str
) -> None:
    text = environment_notice(system_name, interpreter)
    assert system_name in text
    assert shown in text


def test_the_same_pair_gives_exactly_the_same_text() -> None:
    assert environment_notice("Linux", "bash") == environment_notice("Linux", "bash")


def test_different_pairs_give_different_texts() -> None:
    assert environment_notice("Linux", "bash") != environment_notice("Windows", "powershell")


def test_it_has_no_carriage_returns() -> None:
    assert "\r" not in environment_notice("Windows", "powershell")


def test_it_says_nothing_about_the_machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VARIABLE_CENTINELA", "VALOR-DE-PRUEBA-123")
    text = environment_notice("Windows", "powershell")
    assert "VALOR-DE-PRUEBA-123" not in text
    assert "VARIABLE_CENTINELA" not in text
    assert str(tmp_path) not in text
    assert os.getcwd() not in text
    assert getpass.getuser() not in text


def test_an_unknown_interpreter_does_not_fail_and_is_named_as_it_is() -> None:
    assert "zsh" in environment_notice("Darwin", "zsh")


def test_it_tells_the_model_each_call_is_independent_and_the_time_is_limited() -> None:
    text = environment_notice("Linux", "bash")
    assert "independiente" in text
    assert "tiempo" in text
