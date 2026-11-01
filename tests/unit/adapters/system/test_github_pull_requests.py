"""GitHubPullRequests: git push and gh pr create, only through an injected runner (HU-11-06).

No test pushes, runs ``gh`` or touches the network: ``run`` and ``which`` are doubles.
"""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from harness_agent.adapters.system import GitHubPullRequests, ProcessResult
from harness_agent.core.pullrequest import PublishError, PullRequestDraft

SENTINEL = "VALOR-DE-PRUEBA-123"
GH = "/opt/gh"
DRAFT = PullRequestDraft("TAREA-1: Validar", "## Objetivo\nValidar\n\n- [x] ok", "feature/x")


class Runner:
    """Records the calls and answers the scripted results (one per call, the last repeats)."""

    def __init__(self, *results: ProcessResult | BaseException) -> None:
        self.results = list(results or (ProcessResult(0),))
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(self, argv: Sequence[str], env: Mapping[str, str]) -> ProcessResult:
        self.calls.append((list(argv), dict(env)))
        item = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(item, BaseException):
            raise item
        return item


def host(
    runner: Runner, *, gh: str | None = GH, environ: Mapping[str, str] | None = None
) -> GitHubPullRequests:
    return GitHubPullRequests(
        Path("work"),
        environ={"PATH": "/bin", "OTHER": "1"} if environ is None else environ,
        run=runner,
        which=lambda name: gh if name == "gh" else None,
    )


async def test_available_follows_which() -> None:
    assert await host(Runner()).available() is True
    assert await host(Runner(), gh=None).available() is False


async def test_current_branch_reads_the_symbolic_ref() -> None:
    runner = Runner(ProcessResult(0, b"feature/x\n"))
    assert await host(runner).current_branch() == "feature/x"
    assert runner.calls[0][0] == ["git", "symbolic-ref", "--short", "-q", "HEAD"]


async def test_detached_head_is_none() -> None:
    assert await host(Runner(ProcessResult(1))).current_branch() is None


@pytest.mark.parametrize("name", ["-x", "a b", "a..b", "x" * 300, "a;rm", ""])
async def test_odd_current_branch_names_are_refused(name: str) -> None:
    with pytest.raises(PublishError):
        await host(Runner(ProcessResult(0, name.encode()))).current_branch()


async def test_push_uses_a_fixed_command_without_a_shell() -> None:
    runner = Runner()
    await host(runner).push("feature/x")
    argv, env = runner.calls[0]
    assert argv == ["git", "push", "-u", "origin", "feature/x"]
    assert env["GIT_TERMINAL_PROMPT"] == "0" and env["OTHER"] == "1"


@pytest.mark.parametrize("name", ["--force", "-f", "a b", "", "x\ny"])
async def test_push_refuses_odd_branch_names_without_running_anything(name: str) -> None:
    runner = Runner()
    with pytest.raises(PublishError):
        await host(runner).push(name)
    assert runner.calls == []


async def test_push_failure_has_fixed_text_and_one_clean_line() -> None:
    url = f"https://user:{SENTINEL}@example.com/r.git"
    runner = Runner(
        ProcessResult(128, b"", f"fatal: no se pudo acceder a {url}\n\x1b[31mx".encode())
    )
    with pytest.raises(PublishError) as raised:
        await host(runner).push("feature/x")
    message = raised.value.message
    assert message.startswith("No se pudo subir la rama")
    assert SENTINEL not in message and "\x1b" not in message and "\n" not in message
    assert len(message) < 300


async def test_create_runs_gh_with_the_draft_and_returns_the_last_line() -> None:
    url = "https://github.com/acme/app/pull/7"
    runner = Runner(ProcessResult(0, f"Creating pull request...\n{url}\n".encode()))
    assert await host(runner).create(DRAFT) == url
    argv, env = runner.calls[0]
    assert argv == [
        GH,
        "pr",
        "create",
        "--title=TAREA-1: Validar",
        f"--body={DRAFT.body}",
        "--head=feature/x",
    ]
    assert env["GH_PROMPT_DISABLED"] == "1"


async def test_create_without_output_gives_an_empty_link() -> None:
    assert await host(Runner(ProcessResult(0, b""))).create(DRAFT) == ""


async def test_create_without_gh_says_so() -> None:
    with pytest.raises(PublishError) as raised:
        await host(Runner(), gh=None).create(DRAFT)
    assert "gh" in raised.value.message


async def test_create_failure_has_fixed_text_and_a_hint() -> None:
    runner = Runner(ProcessResult(1, b"", b"HTTP 401: Bad credentials\n"))
    with pytest.raises(PublishError) as raised:
        await host(runner).create(DRAFT)
    assert raised.value.message.startswith("No se pudo crear el Pull Request")
    assert "gh auth status" in raised.value.message


async def test_create_refuses_an_odd_branch() -> None:
    runner = Runner()
    odd = PullRequestDraft("t", "b", "--web")
    with pytest.raises(PublishError):
        await host(runner).create(odd)
    assert runner.calls == []


@pytest.mark.parametrize(
    ("error", "word"),
    [
        (FileNotFoundError(), "no se encontró"),
        (subprocess.TimeoutExpired("git", 1), "tardó demasiado"),
        (OSError(SENTINEL), "no se pudo ejecutar"),
    ],
)
async def test_process_errors_become_fixed_messages(error: BaseException, word: str) -> None:
    with pytest.raises(PublishError) as raised:
        await host(Runner(error)).push("feature/x")
    assert word in raised.value.message.lower()
    assert SENTINEL not in raised.value.message


async def test_cancellation_is_not_caught() -> None:
    with pytest.raises(asyncio.CancelledError):
        await host(Runner(asyncio.CancelledError())).push("feature/x")


async def test_default_which_and_default_runner_work_without_pushing(tmp_path: Path) -> None:
    real = GitHubPullRequests(tmp_path, environ={"PATH": ""})
    assert await real.available() is False
