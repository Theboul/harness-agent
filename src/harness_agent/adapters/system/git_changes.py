"""Reads the pending change with git and commits it after a person approved it (HU-11-05).

Implements the ``ChangeSource`` port of ``core.review``. Reading never touches the real index: the
change is staged in a **temporary index** (``GIT_INDEX_FILE``) that starts from ``HEAD`` (or empty
if there is no commit yet), so new files count and the repository stays as it was. Only static
argument lists are run, with no shell, a time limit, no prompts and no external diff programs.
The progress file of the ticket (and anything else in ``exclude``) is left out of both the summary
and the commit. The commit is the only write, and it only happens when ``commit`` is called.

Nothing git says is passed on as it came: errors are fixed text, plus (for a failed commit) one
cleaned and bounded line. ``run`` and ``environ`` are injectable. Only the standard library and
the public API of ``harness_agent.core`` are used.
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from harness_agent.core import (
    ChangeSet,
    ChangeSourceError,
    ChangeStatus,
    FileChange,
    hide_url_credentials,
    one_line,
)

DEFAULT_MAX_PATCH_CHARS = 400_000
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_DETAIL_CHARS = 200
READ_FAILED = "No se pudo leer el cambio del repositorio (¿es un repositorio de git?)."
GIT_MISSING = "No se encontró git en este equipo."
GIT_TIMEOUT = "Git tardó demasiado y se canceló."
COMMIT_FAILED = "No se pudo hacer el commit"
_STATUS = {"A": ChangeStatus.NEW, "M": ChangeStatus.MODIFIED, "D": ChangeStatus.DELETED}
_DIFF_OPTIONS = ("--cached", "--no-renames", "--no-ext-diff", "--no-textconv", "--relative")


@dataclass(frozen=True)
class GitResult:
    """What one git call gave."""

    code: int
    stdout: bytes = b""
    stderr: bytes = b""


GitRun = Callable[[Sequence[str], Mapping[str, str]], GitResult]


class GitChanges:
    """The ``ChangeSource`` of a git work tree.

    Args:
        root: The work area; git runs here and only its files are read and committed.
        exclude: Paths (relative to ``root``) that are never part of the change.
        run: Runs ``git <args>`` with an environment; the real one when ``None``.
        environ: The environment git runs with (injected: this module does not read it); the
            composition removes the provider keys.
        max_patch_chars: Longest patch that is kept; a longer one is cut and flagged.
        timeout_seconds: Time limit of each git call.
    """

    def __init__(
        self,
        root: Path,
        *,
        environ: Mapping[str, str],
        exclude: Sequence[str] = (),
        run: GitRun | None = None,
        max_patch_chars: int = DEFAULT_MAX_PATCH_CHARS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._root = root
        self._exclude = tuple(f":(exclude){path}" for path in exclude)
        self._environ = dict(environ)
        self._max_patch = max_patch_chars
        self._timeout = timeout_seconds
        self._run = run if run is not None else self._subprocess

    async def snapshot(self) -> ChangeSet:
        """The change of the work tree against ``HEAD``, read with a temporary index."""
        return await asyncio.to_thread(self._snapshot)

    async def commit(self, message: str) -> str:
        """Stage and commit the same files ``snapshot`` showed; the short id of the commit."""
        return await asyncio.to_thread(self._commit, message)

    # --- reading -------------------------------------------------------------------------------

    def _snapshot(self) -> ChangeSet:
        with tempfile.TemporaryDirectory(prefix="harness-index-") as directory:
            env = self._env({"GIT_INDEX_FILE": str(Path(directory) / "index")})
            try:
                has_head = self._git(("rev-parse", "--verify", "-q", "HEAD"), env, check=False)
                self._git(("read-tree", "HEAD" if has_head.code == 0 else "--empty"), env)
                self._git(("add", "-A", "--", ".", *self._exclude), env)
                stats = self._git(("diff", *_DIFF_OPTIONS, "--numstat", "-z"), env).stdout
                states = self._git(("diff", *_DIFF_OPTIONS, "--name-status", "-z"), env).stdout
                patch = self._git(("diff", *_DIFF_OPTIONS, "--no-color", "-U3"), env).stdout
            except _GitFailed:
                raise ChangeSourceError(READ_FAILED) from None
        text = patch.decode("utf-8", errors="replace")
        cut = len(text) > self._max_patch
        return ChangeSet(_files(stats, states), text[: self._max_patch] if cut else text, cut)

    # --- committing ----------------------------------------------------------------------------

    def _commit(self, message: str) -> str:
        env = self._env({})
        pathspec = (".", *self._exclude)
        try:
            self._git(("add", "-A", "--", *pathspec), env)
            self._git(("commit", "-q", "-m", message, "--", *pathspec), env)
            identifier = self._git(("rev-parse", "--short", "HEAD"), env).stdout
        except _GitFailed as failure:
            detail = one_line(hide_url_credentials(failure.detail), MAX_DETAIL_CHARS)
            suffix = f": {detail}" if detail else ""
            raise ChangeSourceError(f"{COMMIT_FAILED}{suffix}") from None
        return one_line(identifier.decode("utf-8", errors="replace"), 40) or "?"

    # --- running git ---------------------------------------------------------------------------

    def _env(self, extra: Mapping[str, str]) -> dict[str, str]:
        env = {k: v for k, v in self._environ.items() if k != "GIT_INDEX_FILE"}
        env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0", "GIT_PAGER": "cat"})
        env.update(extra)
        return env

    def _git(self, args: Sequence[str], env: Mapping[str, str], *, check: bool = True) -> GitResult:
        try:
            result = self._run(args, env)
        except FileNotFoundError:
            raise ChangeSourceError(GIT_MISSING) from None
        except subprocess.TimeoutExpired:
            raise ChangeSourceError(GIT_TIMEOUT) from None
        except OSError:
            raise ChangeSourceError(READ_FAILED) from None
        if check and result.code != 0:
            raise _GitFailed(result.stderr.decode("utf-8", errors="replace"))
        return result

    def _subprocess(self, args: Sequence[str], env: Mapping[str, str]) -> GitResult:
        done = subprocess.run(
            ["git", *args],
            cwd=self._root,
            env=dict(env),
            capture_output=True,
            timeout=self._timeout,
            check=False,
        )
        return GitResult(done.returncode, done.stdout, done.stderr)


class _GitFailed(Exception):
    """Internal: a write step failed; ``detail`` is git's own text, to be cleaned before use."""

    def __init__(self, detail: str) -> None:
        super().__init__("git failed")
        self.detail = detail


def _files(stats: bytes, states: bytes) -> tuple[FileChange, ...]:
    """Join ``--numstat -z`` and ``--name-status -z`` (no renames) into one list of files."""
    kinds: dict[str, ChangeStatus] = {}
    fields = states.decode("utf-8", errors="replace").split("\0")
    for code, path in zip(fields[0::2], fields[1::2], strict=False):
        kinds[path] = _STATUS.get(code[:1], ChangeStatus.OTHER)
    files: list[FileChange] = []
    for record in stats.decode("utf-8", errors="replace").split("\0"):
        parts = record.split("\t", 2)
        if len(parts) != 3:
            continue
        added, removed, path = parts
        files.append(
            FileChange(path, kinds.get(path, ChangeStatus.OTHER), _count(added), _count(removed))
        )
    return tuple(files)


def _count(text: str) -> int | None:
    return int(text) if text.isdigit() else None
