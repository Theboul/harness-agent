"""Pushes the branch with git and creates the Pull Request with the GitHub CLI (HU-11-06).

Implements the ``PullRequestHost`` port of ``core.pullrequest``. This module only runs after the
core has asked a person for each outgoing action. Only static argument lists are run: no shell, a
time limit, no prompts (``GIT_TERMINAL_PROMPT=0``, ``GH_PROMPT_DISABLED=1``) and the environment
the composition hands over (without the provider keys). The branch name is validated before it
reaches a command line. The remote is always ``origin`` and the base branch is the repository's
default one (``gh`` is not given ``--base``).

Nothing git or ``gh`` says is passed on as it came: errors are fixed text plus, at most, one
cleaned and bounded line with URL credentials hidden. ``run``, ``which`` and ``environ`` are
injectable. Only the standard library and the public API of ``harness_agent.core`` are used.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from harness_agent.core import (
    REMOTE,
    PublishError,
    PullRequestDraft,
    hide_url_credentials,
    one_line,
)

DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_DETAIL_CHARS = 200
MAX_BRANCH_CHARS = 200
GH_PROGRAM = "gh"
GIT_PROGRAM = "git"
GIT_MISSING = "No se encontró el programa necesario (git o gh) en este equipo."
GH_MISSING = "No se encontró `gh` (la CLI de GitHub) en este equipo."
TIMED_OUT = "El comando tardó demasiado y se canceló."
NOT_RUNNABLE = "No se pudo ejecutar el comando."
BAD_BRANCH = "El nombre de la rama no se puede usar."
PUSH_FAILED = "No se pudo subir la rama"
CREATE_FAILED = "No se pudo crear el Pull Request"
CREATE_HINT = " (revisa `gh auth status` y el remoto)"
_BRANCH = re.compile(r"[A-Za-z0-9._/@+-]+")
_SAFE_ENVIRONMENT = {
    "GIT_TERMINAL_PROMPT": "0",
    "GH_PROMPT_DISABLED": "1",
    "GH_NO_UPDATE_NOTIFIER": "1",
    "NO_COLOR": "1",
}


@dataclass(frozen=True)
class ProcessResult:
    """What one process gave."""

    code: int
    stdout: bytes = b""
    stderr: bytes = b""


Run = Callable[[Sequence[str], Mapping[str, str]], ProcessResult]
Which = Callable[[str], str | None]


class GitHubPullRequests:
    """The ``PullRequestHost`` of a git work tree on GitHub.

    Args:
        root: The work area; git and ``gh`` run here.
        environ: The environment the processes run with (injected: this module does not read it).
        run: Runs ``argv`` with an environment; the real one when ``None``.
        which: Finds a program by name; ``shutil.which`` over ``environ['PATH']`` when ``None``.
        timeout_seconds: Time limit of each process.
    """

    def __init__(
        self,
        root: Path,
        *,
        environ: Mapping[str, str],
        run: Run | None = None,
        which: Which | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._root = root
        self._environ = {**environ, **_SAFE_ENVIRONMENT}
        self._timeout = timeout_seconds
        self._run = run if run is not None else self._subprocess
        self._which = which if which is not None else self._find

    async def available(self) -> bool:
        """Whether ``gh`` can be found."""
        return self._which(GH_PROGRAM) is not None

    async def current_branch(self) -> str | None:
        """The checked-out branch; ``None`` when ``HEAD`` is detached."""
        result = await self._call((GIT_PROGRAM, "symbolic-ref", "--short", "-q", "HEAD"))
        if result.code != 0:
            return None
        name = result.stdout.decode("utf-8", errors="replace").strip()
        return _valid_branch(name)

    async def push(self, branch: str) -> None:
        """``git push -u origin <branch>``."""
        name = _valid_branch(branch)
        result = await self._call((GIT_PROGRAM, "push", "-u", REMOTE, name))
        if result.code != 0:
            raise PublishError(PUSH_FAILED + _detail(result))

    async def create(self, draft: PullRequestDraft) -> str:
        """``gh pr create`` for ``draft``; the last line it printed (the link), or empty."""
        gh = self._which(GH_PROGRAM)
        if gh is None:
            raise PublishError(GH_MISSING)
        name = _valid_branch(draft.branch)
        result = await self._call(
            (gh, "pr", "create", f"--title={draft.title}", f"--body={draft.body}", f"--head={name}")
        )
        if result.code != 0:
            raise PublishError(CREATE_FAILED + _detail(result) + CREATE_HINT)
        lines = result.stdout.decode("utf-8", errors="replace").splitlines()
        return next((line.strip() for line in reversed(lines) if line.strip()), "")

    # --- running processes ---------------------------------------------------------------------

    async def _call(self, argv: Sequence[str]) -> ProcessResult:
        return await asyncio.to_thread(self._guarded, argv)

    def _guarded(self, argv: Sequence[str]) -> ProcessResult:
        try:
            return self._run(argv, self._environ)
        except FileNotFoundError:
            raise PublishError(GIT_MISSING) from None
        except subprocess.TimeoutExpired:
            raise PublishError(TIMED_OUT) from None
        except OSError:
            raise PublishError(NOT_RUNNABLE) from None

    def _subprocess(self, argv: Sequence[str], env: Mapping[str, str]) -> ProcessResult:
        done = subprocess.run(
            list(argv),
            cwd=self._root,
            env=dict(env),
            capture_output=True,
            timeout=self._timeout,
            check=False,
        )
        return ProcessResult(done.returncode, done.stdout, done.stderr)

    def _find(self, name: str) -> str | None:
        return shutil.which(name, path=self._environ.get("PATH"))


def _valid_branch(name: str) -> str:
    if (
        not isinstance(name, str)
        or len(name) > MAX_BRANCH_CHARS
        or name.startswith(("-", "/"))
        or ".." in name
        or _BRANCH.fullmatch(name) is None
    ):
        raise PublishError(BAD_BRANCH)
    return name


def _detail(result: ProcessResult) -> str:
    """``": <one clean line>"`` from what the process printed on stderr, or nothing."""
    text = result.stderr.decode("utf-8", errors="replace")
    line = one_line(hide_url_credentials(text), MAX_DETAIL_CHARS)
    return f": {line}" if line else ""
