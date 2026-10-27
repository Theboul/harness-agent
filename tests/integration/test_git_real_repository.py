"""Sp2-45: git reads on a real temporary repository (HU-11-02 / T008, FR-014).

Real git, with strict rules:

* only inside ``tmp_path``, never the repository of the project; the search for a repository
  stops at the folder of the test (``GIT_CEILING_DIRECTORIES``);
* an isolated environment: an empty global configuration of its own (``GIT_CONFIG_GLOBAL``), no
  system configuration (``GIT_CONFIG_NOSYSTEM``), a home of its own, a test author, no prompts,
  no optional locks (so ``git status`` does not rewrite the index) and ``cat`` as pager;
* ``run_git`` only accepts ``init``, ``add``, ``commit``, ``status``, ``diff`` and ``log``, and
  refuses anything else without running it;
* the reads go through the real composition and the native shell, without an approver: the policy
  must let them run. A command the policy asks (``git commit`` asked by the model) is checked
  never to run. Nothing else is ever executed.

What is checked: ``status``, ``diff`` and ``log`` leave the repository as it was (HEAD, refs,
``status --porcelain``, ``diff --cached`` and the files of the work tree), and a long ``log`` comes
back cut with the omission notice. Skipped, with its reason, if git is not installed.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition
from harness_agent.config import Limits
from harness_agent.core import ProviderResponse, Role, ToolCall
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git no está instalado en esta máquina"
)

ALLOWED_SUBCOMMANDS = frozenset({"init", "add", "commit", "status", "diff", "log"})
RAN = "Código de salida: 0"
ASKED = "[approval_required_unavailable]"
OMITTED = "[salida recortada: se omitieron"
LONG_MESSAGE = "cambio " + "x" * 2_000
COMMITS = 20


def git_environment(base: Path) -> dict[str, str]:
    """The environment of every git call of these tests: isolated from the person's git."""
    home = base / "home"
    home.mkdir(exist_ok=True)
    global_config = base / "gitconfig-vacio"
    global_config.write_text("", encoding="utf-8")
    kept = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("GIT_", "COV_CORE", "COVERAGE"))
    }
    kept.update(
        {
            "GIT_CONFIG_GLOBAL": str(global_config),
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(home),
            "GIT_AUTHOR_NAME": "Persona de prueba",
            "GIT_AUTHOR_EMAIL": "prueba@example.invalid",
            "GIT_COMMITTER_NAME": "Persona de prueba",
            "GIT_COMMITTER_EMAIL": "prueba@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_CEILING_DIRECTORIES": str(base),
        }
    )
    return kept


def run_git(repo: Path, env: dict[str, str], *args: str) -> str:
    """Run git in ``repo`` with ``env``; only the subcommands of these tests are accepted."""
    if not args or args[0] not in ALLOWED_SUBCOMMANDS:
        raise ValueError("Subcomando de git no permitido en estas pruebas.")
    done = subprocess.run(
        ["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True
    )
    return done.stdout


def snapshot(repo: Path, env: dict[str, str]) -> dict[str, object]:
    """What a read must not change: HEAD, refs, index state and the files of the work tree."""
    git_dir = repo / ".git"
    refs = {
        path.relative_to(git_dir).as_posix(): path.read_bytes()
        for path in sorted((git_dir / "refs").rglob("*"))
        if path.is_file()
    }
    files = {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(repo.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(repo).parts
    }
    return {
        "HEAD": (git_dir / "HEAD").read_bytes(),
        "refs": refs,
        "status": run_git(repo, env, "status", "--porcelain"),
        "staged": run_git(repo, env, "diff", "--cached"),
        "files": files,
    }


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    env = git_environment(tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, env, "init", "-q")
    (repo / "a.txt").write_text("uno\n", encoding="utf-8")
    run_git(repo, env, "add", "a.txt")
    run_git(repo, env, "commit", "-q", "-m", "inicio")
    for index in range(COMMITS):
        run_git(repo, env, "commit", "-q", "--allow-empty", "-m", f"{LONG_MESSAGE} {index}")
    (repo / "a.txt").write_text("uno\ndos\n", encoding="utf-8")  # an unstaged change for diff
    return repo, env


def compose_on(
    tmp_path: Path,
    opened: list[Composition],
    repo: Path,
    env: dict[str, str],
    commands: list[str],
) -> Composition:
    script = [
        ProviderResponse(
            tool_calls=[ToolCall(id=f"c{i}", name="shell", arguments={"command": command})]
        )
        for i, command in enumerate(commands)
    ]
    script.append(ProviderResponse(content="listo"))
    config = make_config(tmp_path, workspace=repo)
    return build(opened, config, FakeProvider(script), environ=env, system_name=platform.system())


async def answers(composition: Composition) -> list[str]:
    result = await composition.loop.run_turn(
        session_id=composition.session_id, task="revisa", history=[]
    )
    return [str(m.content) for m in result.history if m.role is Role.TOOL]


# --- the helper only runs what it allows ---------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("push",),
        ("reset", "--hard"),
        ("clean", "-fd"),
        ("checkout", "."),
        ("config", "x"),
        ("st",),
    ],
)
def test_the_helper_refuses_any_other_subcommand_without_running_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: tuple[str, ...]
) -> None:
    def never(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("subprocess.run no debía llamarse")

    monkeypatch.setattr(subprocess, "run", never)

    with pytest.raises(ValueError):
        run_git(tmp_path, {}, *args)


# --- reads through the composition ----------------------------------------------------------------


async def test_reads_run_and_leave_the_repository_as_it_was(
    tmp_path: Path, opened: list[Composition], repository: tuple[Path, dict[str, str]]
) -> None:
    repo, env = repository
    before = snapshot(repo, env)
    composition = compose_on(
        tmp_path, opened, repo, env, ["git status", "git diff", "git log --oneline -3"]
    )

    status, diff, log = await answers(composition)

    assert status.startswith(RAN), status
    assert "a.txt" in status
    assert diff.startswith(RAN) and "+dos" in diff
    assert log.startswith(RAN) and "inicio" not in log  # only the last three commits
    assert snapshot(repo, env) == before


async def test_a_long_log_comes_back_cut(
    tmp_path: Path, opened: list[Composition], repository: tuple[Path, dict[str, str]]
) -> None:
    repo, env = repository
    composition = compose_on(tmp_path, opened, repo, env, ["git log"])

    (log,) = await answers(composition)

    assert log.startswith(RAN)
    assert OMITTED in log
    assert len(log) <= Limits().max_tool_output_chars


async def test_a_command_the_policy_asks_never_runs(
    tmp_path: Path, opened: list[Composition], repository: tuple[Path, dict[str, str]]
) -> None:
    repo, env = repository
    commits_before = run_git(repo, env, "log", "--oneline").count("\n")
    before = snapshot(repo, env)
    composition = compose_on(tmp_path, opened, repo, env, ["git commit -am cambio"])

    (answer,) = await answers(composition)

    assert answer.startswith(ASKED)
    assert run_git(repo, env, "log", "--oneline").count("\n") == commits_before
    assert snapshot(repo, env) == before
