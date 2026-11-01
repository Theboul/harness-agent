"""Tests of ``only_git_reads`` (HU-05-07 / T001): only a command of pure git reads is a read."""

from __future__ import annotations

import pytest

from harness_agent.core import Dialect, only_git_reads

BASH, POWERSHELL = Dialect.BASH, Dialect.POWERSHELL


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git diff HEAD~1",
        "git log --oneline -n 5",
        "git status && git log",
        "git branch",
        "git stash list",
    ],
)
def test_pure_git_reads_are_reads(command: str) -> None:
    assert only_git_reads(command, BASH) is True


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x",
        "git push origin main",
        "git reset --hard",
        "git status && git push",
        "git status; rm -rf x",
        "ls",
        "cat archivo",
        "echo a > f",
        "git diff --output=f",
        "git log $(rm x)",
        "git status | tee f",
        "eval git status",
        "git -c core.pager=x log",
        "GIT_DIR=x git status",
        "",
        "   ",
    ],
)
def test_anything_else_is_not_a_read(command: str) -> None:
    assert only_git_reads(command, BASH) is False


def test_powershell_dialect_is_honoured() -> None:
    assert only_git_reads("git status", POWERSHELL) is True
    assert only_git_reads("git add .", POWERSHELL) is False


@pytest.mark.parametrize("value", [None, 3, b"git status", ["git", "status"]])
def test_a_value_that_is_not_text_is_not_a_read(value: object) -> None:
    assert only_git_reads(value, BASH) is False  # type: ignore[arg-type]
