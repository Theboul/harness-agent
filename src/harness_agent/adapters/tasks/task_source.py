"""Where a task comes from: a Markdown file or a GitHub issue read with ``gh`` (HU-11-01).

Both sources produce the same text format, parsed by ``parse_task``. The ``gh`` call goes through
an injectable ``GhRunner`` so tests never touch the network or the real CLI; the default runner
starts ``gh`` without a shell, with a time limit and bounded output.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from harness_agent.adapters.tasks.errors import TaskSourceError
from harness_agent.core import TaskDefinition, parse_task

MAX_TASK_FILE_BYTES = 262_144
GH_TIMEOUT_SECONDS = 30
MAX_ISSUE_NUMBER = 10**9
_MAX_GH_OUTPUT_CHARS = MAX_TASK_FILE_BYTES * 4
_REPOSITORY = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*$")

GhRunner = Callable[[Sequence[str]], str]
"""Runs ``gh`` with the given arguments (without the ``gh`` itself) and returns its output."""


def run_gh(args: Sequence[str]) -> str:
    """Run the GitHub CLI and return what it printed.

    Raises:
        TaskSourceError: ``gh`` is missing, took too long, failed or printed too much.
    """
    try:
        completed = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GH_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        raise TaskSourceError("gh_tiempo") from None
    except OSError:
        raise TaskSourceError("gh_no_disponible") from None
    if completed.returncode != 0:
        raise TaskSourceError("gh_fallo")
    if len(completed.stdout) > _MAX_GH_OUTPUT_CHARS:
        raise TaskSourceError("gh_respuesta_invalida")
    return completed.stdout


def load_task_file(path: str | Path) -> TaskDefinition:
    """Read a task file (UTF-8, bounded size) and validate it.

    Raises:
        TaskSourceError: The file cannot be read, is too large or is not UTF-8.
        TaskFormatError: The text is not a valid task.
    """
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(MAX_TASK_FILE_BYTES + 1)
    except OSError:
        raise TaskSourceError("archivo_ilegible") from None
    if len(data) > MAX_TASK_FILE_BYTES:
        raise TaskSourceError("archivo_demasiado_grande")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise TaskSourceError("archivo_no_utf8") from None
    return parse_task(text)


def load_github_issue(
    number: int, *, repo: str | None = None, runner: GhRunner = run_gh
) -> TaskDefinition:
    """Read an issue with ``gh issue view`` and validate its body as a task.

    The title of the issue names the task when the body does not start with ``# ``.

    Args:
        number: Issue number (a positive integer).
        repo: Optional ``owner/name``; by default ``gh`` infers it from the current folder.
        runner: Runs ``gh``; injected in tests.

    Raises:
        TaskSourceError: The number or repository is invalid, or ``gh`` failed or answered
            something unexpected.
        TaskFormatError: The body is not a valid task.
    """
    if (
        isinstance(number, bool)
        or not isinstance(number, int)
        or not 1 <= number <= MAX_ISSUE_NUMBER
    ):
        raise TaskSourceError("issue_invalido")
    args = ["issue", "view", str(number), "--json", "title,body"]
    if repo is not None:
        if not _REPOSITORY.match(repo):
            raise TaskSourceError("issue_invalido")
        args += ["--repo", repo]
    try:
        answer = json.loads(runner(args))
    except ValueError:
        raise TaskSourceError("gh_respuesta_invalida") from None
    if not isinstance(answer, dict):
        raise TaskSourceError("gh_respuesta_invalida")
    title, body = answer.get("title"), answer.get("body")
    if not isinstance(title, str) or not isinstance(body, str):
        raise TaskSourceError("gh_respuesta_invalida")
    return parse_task(body).with_title(title)
