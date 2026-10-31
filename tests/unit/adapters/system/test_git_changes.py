"""GitChanges with a stand-in for git: calls, parsing and failures (HU-11-05)."""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from harness_agent.adapters.system import GitChanges
from harness_agent.adapters.system.git_changes import GitResult
from harness_agent.core import ChangeSourceError, ChangeStatus

NUMSTAT = b"12\t0\tsrc/auth.py\x006\t3\ttests/test_auth.py\x00-\t-\tlogo.png\x000\t4\told.py\x00"
NAMES = b"A\x00src/auth.py\x00M\x00tests/test_auth.py\x00M\x00logo.png\x00D\x00old.py\x00"
SECRET = "https://" + "usuario-de-prueba" + ":" + "secreto-de-prueba" + "@servidor.example/r.git"


class FakeGit:
    """Answers by subcommand and records every call with its environment."""

    def __init__(self, answers: dict[str, GitResult | BaseException] | None = None) -> None:
        self.answers = answers or {}
        self.calls: list[tuple[tuple[str, ...], dict[str, str]]] = []

    def __call__(self, args: Sequence[str], env: Mapping[str, str]) -> GitResult:
        self.calls.append((tuple(args), dict(env)))
        key = " ".join(args[:2]) if args[0] == "diff" and "--numstat" in args else args[0]
        if args[0] == "diff" and "--name-status" in args:
            key = "names"
        if args[0] == "diff" and "-U3" in args:
            key = "patch"
        if args[0] == "diff" and "--numstat" in args:
            key = "numstat"
        answer = self.answers.get(key, GitResult(0))
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def verbs(self) -> list[str]:
        return [call[0][0] for call in self.calls]


def source(fake: FakeGit, **options: object) -> GitChanges:
    return GitChanges(Path("repo"), run=fake, environ={"PATH": "x"}, **options)  # type: ignore[arg-type]


def reading() -> dict[str, GitResult | BaseException]:
    return {
        "numstat": GitResult(0, NUMSTAT),
        "names": GitResult(0, NAMES),
        "patch": GitResult(0, b"diff --git a/x b/x\n+hola\n"),
    }


def test_the_summary_joins_counts_and_statuses() -> None:
    changes = asyncio.run(source(FakeGit(reading())).snapshot())

    assert [(f.path, f.status, f.added, f.removed) for f in changes.files] == [
        ("src/auth.py", ChangeStatus.NEW, 12, 0),
        ("tests/test_auth.py", ChangeStatus.MODIFIED, 6, 3),
        ("logo.png", ChangeStatus.MODIFIED, None, None),
        ("old.py", ChangeStatus.DELETED, 0, 4),
    ]
    assert changes.patch.startswith("diff --git") and not changes.truncated


def test_the_real_index_is_never_used_and_nothing_is_written() -> None:
    fake = FakeGit(reading())

    asyncio.run(source(fake).snapshot())

    assert fake.verbs() == ["rev-parse", "read-tree", "add", "diff", "diff", "diff"]
    indexes = {env["GIT_INDEX_FILE"] for _, env in fake.calls}
    assert len(indexes) == 1 and next(iter(indexes)).endswith("index")
    assert all(env["GIT_TERMINAL_PROMPT"] == "0" for _, env in fake.calls)
    assert "commit" not in fake.verbs()
    diffs = [args for args, _ in fake.calls if args[0] == "diff"]
    assert all("--no-ext-diff" in a and "--no-textconv" in a for a in diffs)


def test_without_a_first_commit_the_index_starts_empty() -> None:
    fake = FakeGit({**reading(), "rev-parse": GitResult(1)})

    asyncio.run(source(fake).snapshot())

    assert ("read-tree", "--empty") in [args for args, _ in fake.calls]


def test_the_excluded_paths_are_left_out_of_the_pathspec() -> None:
    fake = FakeGit(reading())

    asyncio.run(source(fake, exclude=("progreso-T.md",)).snapshot())

    add = next(args for args, _ in fake.calls if args[0] == "add")
    assert add == ("add", "-A", "--", ".", ":(exclude)progreso-T.md")


def test_a_long_patch_is_cut_and_flagged() -> None:
    answers = reading()
    answers["patch"] = GitResult(0, b"x" * 50)

    changes = asyncio.run(source(FakeGit(answers), max_patch_chars=10).snapshot())

    assert changes.truncated and len(changes.patch) == 10


def test_a_clean_tree_is_an_empty_change_set() -> None:
    changes = asyncio.run(source(FakeGit()).snapshot())

    assert changes.is_empty and changes.patch == ""


@pytest.mark.parametrize("failing", ["read-tree", "add", "numstat", "names", "patch"])
def test_a_failed_read_is_a_fixed_error_without_git_text(failing: str) -> None:
    answers = reading()
    answers[failing] = GitResult(128, b"", b"fatal: VALOR-DE-PRUEBA-123 " + SECRET.encode())

    with pytest.raises(ChangeSourceError) as caught:
        asyncio.run(source(FakeGit(answers)).snapshot())

    assert "VALOR-DE-PRUEBA-123" not in caught.value.message
    assert "secreto-de-prueba" not in caught.value.message
    assert "repositorio de git" in caught.value.message


def test_git_missing_and_timeout_are_reported() -> None:
    with pytest.raises(ChangeSourceError, match="No se encontró git"):
        asyncio.run(source(FakeGit({"rev-parse": FileNotFoundError()})).snapshot())
    timeout = subprocess.TimeoutExpired("git", 1)
    with pytest.raises(ChangeSourceError, match="tardó demasiado"):
        asyncio.run(source(FakeGit({"rev-parse": timeout})).snapshot())
    with pytest.raises(ChangeSourceError, match="repositorio de git"):
        asyncio.run(source(FakeGit({"rev-parse": PermissionError()})).snapshot())


def test_commit_stages_commits_only_the_reviewed_paths_and_returns_the_id() -> None:
    fake = FakeGit({"rev-parse": GitResult(0, b"abc1234\n")})

    identifier = asyncio.run(
        source(fake, exclude=("progreso-T.md",)).commit("TAREA-14: Validar el correo")
    )

    assert identifier == "abc1234"
    calls = [args for args, _ in fake.calls]
    assert calls == [
        ("add", "-A", "--", ".", ":(exclude)progreso-T.md"),
        ("commit", "-q", "-m", "TAREA-14: Validar el correo", "--", ".", ":(exclude)progreso-T.md"),
        ("rev-parse", "--short", "HEAD"),
    ]
    assert all("GIT_INDEX_FILE" not in env for _, env in fake.calls)


def test_a_failed_commit_shows_one_clean_bounded_line_without_credentials() -> None:
    stderr = f"Author identity unknown\n{SECRET}\n".encode() + b"\x1b[31m" + b"y" * 500
    fake = FakeGit({"commit": GitResult(128, b"", stderr)})

    with pytest.raises(ChangeSourceError) as caught:
        asyncio.run(source(fake).commit("m"))

    message = caught.value.message
    assert message.startswith("No se pudo hacer el commit: Author identity unknown")
    assert "\n" not in message and "\x1b" not in message
    assert "secreto-de-prueba" not in message and len(message) < 260


def test_a_failed_add_before_the_commit_is_also_a_commit_failure() -> None:
    fake = FakeGit({"add": GitResult(1, b"", b"error: index.lock")})

    with pytest.raises(ChangeSourceError, match="No se pudo hacer el commit: error: index.lock"):
        asyncio.run(source(fake).commit("m"))
    assert "commit" not in fake.verbs()


def test_the_environment_of_git_drops_a_foreign_index_and_asks_nothing() -> None:
    fake = FakeGit(reading())
    mine = GitChanges(Path("repo"), run=fake, environ={"GIT_INDEX_FILE": "otro", "PATH": "x"})

    asyncio.run(mine.snapshot())

    assert all(env["GIT_INDEX_FILE"] != "otro" for _, env in fake.calls)
