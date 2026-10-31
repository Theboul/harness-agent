"""GitChanges on a real temporary repository (HU-11-05 / SC-002).

Real git, with the same rules as ``test_git_real_repository.py``: only inside ``tmp_path`` (the
search for a repository stops there), an isolated environment (empty global configuration, no
system configuration, a test author, no prompts) and only the subcommands this file lists. Skipped,
with its reason, if git is not installed.

What is checked: new, modified and deleted files count; the real index and the files are exactly as
they were after reading; the excluded file is neither summarized nor committed; the commit holds
the files (new ones included) and nothing else; an empty repository (no commits) works.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from harness_agent.adapters.system import GitChanges
from harness_agent.core import ChangeSourceError, ChangeStatus

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git no está instalado en esta máquina"
)

ALLOWED = frozenset({"init", "add", "commit", "status", "diff", "log", "show", "ls-files"})


def environment(base: Path) -> dict[str, str]:
    home = base / "home"
    home.mkdir(exist_ok=True)
    empty = base / "gitconfig-vacio"
    empty.write_text("", encoding="utf-8")
    kept = {
        k: v
        for k, v in os.environ.items()
        if not k.upper().startswith(("GIT_", "COV_CORE", "COVERAGE"))
    }
    kept.update(
        {
            "GIT_CONFIG_GLOBAL": str(empty),
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(home),
            "GIT_AUTHOR_NAME": "Persona de prueba",
            "GIT_AUTHOR_EMAIL": "prueba@example.invalid",
            "GIT_COMMITTER_NAME": "Persona de prueba",
            "GIT_COMMITTER_EMAIL": "prueba@example.invalid",
            "GIT_CEILING_DIRECTORIES": str(base),
        }
    )
    return kept


def git(repo: Path, env: dict[str, str], *args: str) -> str:
    if args[0] not in ALLOWED:
        raise ValueError("Subcomando de git no permitido en estas pruebas.")
    done = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return done.stdout


def fingerprint(repo: Path) -> dict[str, object]:
    index = repo / ".git" / "index"
    return {
        "index": hashlib.sha256(index.read_bytes()).hexdigest() if index.exists() else None,
        "files": {
            p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(repo.rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(repo).parts
        },
    }


@pytest.fixture
def repo(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    env = environment(tmp_path)
    root = tmp_path / "repo"
    root.mkdir()
    git(root, env, "init", "-q")
    (root / "keep.txt").write_text("uno\n", encoding="utf-8")
    (root / "gone.txt").write_text("adiós\n", encoding="utf-8")
    git(root, env, "add", ".")
    git(root, env, "commit", "-q", "-m", "inicio")
    return root, env


def make_changes(root: Path) -> None:
    (root / "keep.txt").write_text("uno\ndos\n", encoding="utf-8")
    (root / "gone.txt").unlink()
    (root / "nuevo ñandú.txt").write_text("hola\n", encoding="utf-8")
    (root / "progreso-T.md").write_text("estado\n", encoding="utf-8")


def source(root: Path, env: dict[str, str]) -> GitChanges:
    return GitChanges(root, environ=env, exclude=("progreso-T.md",))


def test_the_summary_matches_the_real_changes_and_leaves_the_repository_untouched(
    repo: tuple[Path, dict[str, str]],
) -> None:
    root, env = repo
    make_changes(root)
    before = fingerprint(root)

    changes = asyncio.run(source(root, env).snapshot())

    found = {f.path: (f.status, f.added, f.removed) for f in changes.files}
    assert found == {
        "gone.txt": (ChangeStatus.DELETED, 0, 1),
        "keep.txt": (ChangeStatus.MODIFIED, 1, 0),
        "nuevo ñandú.txt": (ChangeStatus.NEW, 1, 0),
    }
    assert "+dos" in changes.patch and "progreso" not in changes.patch
    assert fingerprint(root) == before
    assert git(root, env, "status", "--porcelain").count("??") == 2  # still untracked


def test_commit_holds_the_reviewed_files_and_not_the_excluded_one(
    repo: tuple[Path, dict[str, str]],
) -> None:
    root, env = repo
    make_changes(root)

    identifier = asyncio.run(source(root, env).commit("TAREA-14: probar"))

    assert identifier and git(root, env, "log", "-1", "--format=%s").strip() == "TAREA-14: probar"
    listing = git(root, env, "show", "--name-only", "-z", "--format=", "HEAD")
    names = set(listing.split("\0")) - {""}
    assert names == {"gone.txt", "keep.txt", "nuevo ñandú.txt"}
    assert "progreso-T.md" in git(root, env, "status", "--porcelain")  # left alone


def test_a_clean_tree_has_no_changes(repo: tuple[Path, dict[str, str]]) -> None:
    root, env = repo

    assert asyncio.run(source(root, env).snapshot()).is_empty


def test_a_repository_without_commits_counts_everything_as_new(tmp_path: Path) -> None:
    env = environment(tmp_path)
    root = tmp_path / "vacio"
    root.mkdir()
    git(root, env, "init", "-q")
    (root / "a.txt").write_text("a\n", encoding="utf-8")

    changes = asyncio.run(GitChanges(root, environ=env).snapshot())

    assert [(f.path, f.status) for f in changes.files] == [("a.txt", ChangeStatus.NEW)]


def test_a_folder_that_is_not_a_repository_fails_closed(tmp_path: Path) -> None:
    env = environment(tmp_path)
    folder = tmp_path / "suelto"
    folder.mkdir()

    with pytest.raises(ChangeSourceError, match="repositorio de git"):
        asyncio.run(GitChanges(folder, environ=env).snapshot())


def test_a_work_area_inside_a_larger_repository_only_sees_its_own_files(
    repo: tuple[Path, dict[str, str]],
) -> None:
    root, env = repo
    (root / "sub").mkdir()
    (root / "sub" / "dentro.txt").write_text("x\n", encoding="utf-8")
    (root / "fuera.txt").write_text("y\n", encoding="utf-8")

    changes = asyncio.run(GitChanges(root / "sub", environ=env).snapshot())

    assert [f.path for f in changes.files] == ["dentro.txt"]


def test_a_commit_that_git_refuses_is_reported_without_a_trace(tmp_path: Path) -> None:
    env = environment(tmp_path)
    for name in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
    ):
        env.pop(name)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    root = tmp_path / "sinautor"
    root.mkdir()
    git(root, env, "init", "-q")
    (root / "a.txt").write_text("a\n", encoding="utf-8")

    with pytest.raises(ChangeSourceError) as caught:
        asyncio.run(GitChanges(root, environ=env).commit("m"))

    assert caught.value.message.startswith("No se pudo hacer el commit")
    assert "\n" not in caught.value.message
