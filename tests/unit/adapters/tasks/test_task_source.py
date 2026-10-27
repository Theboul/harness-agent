"""Task sources: file and GitHub issue (HU-11-01 / T009)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.tasks import (
    MAX_TASK_FILE_BYTES,
    TaskSourceError,
    load_github_issue,
    load_task_file,
    run_gh,
)
from harness_agent.core import TaskFormatError

SENTINEL = "VALOR-DE-PRUEBA-123"
BODY = (
    "## Objetivo\nHacer algo\n## Criterios de aceptación\n"
    "- Funciona\n  - comando: ls\n  - espera: codigo_salida == 0\n"
)


class FakeGh:
    """A ``gh`` runner that records the arguments and answers a fixed text."""

    def __init__(self, answer: str | BaseException) -> None:
        self.answer = answer
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


def issue_json(title: object = "Validar el correo", body: object = BODY) -> str:
    return json.dumps({"title": title, "body": body})


# --- file -----------------------------------------------------------------------------------


def test_a_task_file_is_read_and_parsed(tmp_path: Path) -> None:
    path = tmp_path / "tarea.md"
    path.write_text("# TAREA-1\n" + BODY, encoding="utf-8")

    task = load_task_file(path)

    assert task.title == "TAREA-1" and task.objective == "Hacer algo"
    assert task.criteria[0].command == "ls"


def test_a_utf8_bom_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "tarea.md"
    path.write_bytes(b"\xef\xbb\xbf" + BODY.encode("utf-8"))

    assert load_task_file(path).objective == "Hacer algo"


def test_a_file_with_an_invalid_task_raises_the_format_error(tmp_path: Path) -> None:
    path = tmp_path / "tarea.md"
    path.write_text("## Objetivo\nx\n", encoding="utf-8")

    with pytest.raises(TaskFormatError) as caught:
        load_task_file(path)

    assert caught.value.code == "sin_criterios"


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        ("missing", "archivo_ilegible"),
        ("folder", "archivo_ilegible"),
        ("binary", "archivo_no_utf8"),
        ("huge", "archivo_demasiado_grande"),
    ],
)
def test_file_problems_are_source_errors_without_path_or_content(
    tmp_path: Path, setup: str, code: str
) -> None:
    path = tmp_path / f"{SENTINEL}.md"
    if setup == "folder":
        path.mkdir()
    elif setup == "binary":
        path.write_bytes(b"\xff\xfe\x00bad" + SENTINEL.encode())
    elif setup == "huge":
        path.write_bytes(b"x" * (MAX_TASK_FILE_BYTES + 1))

    with pytest.raises(TaskSourceError) as caught:
        load_task_file(path)

    assert caught.value.code == code
    assert SENTINEL not in str(caught.value) and str(tmp_path) not in str(caught.value)


def test_a_file_of_exactly_the_maximum_size_is_read(tmp_path: Path) -> None:
    path = tmp_path / "tarea.md"
    path.write_bytes(b"x" * MAX_TASK_FILE_BYTES)

    with pytest.raises(TaskFormatError) as caught:  # read in full; rejected by the format
        load_task_file(path)

    assert caught.value.code == "demasiado_grande"


# --- issue ----------------------------------------------------------------------------------


def test_an_issue_becomes_a_task_with_the_issue_title_as_fallback() -> None:
    gh = FakeGh(issue_json())

    task = load_github_issue(14, runner=gh)

    assert gh.calls == [["issue", "view", "14", "--json", "title,body"]]
    assert task.title == "Validar el correo" and task.objective == "Hacer algo"


def test_the_title_of_the_body_wins_over_the_issue_title() -> None:
    gh = FakeGh(issue_json(body="# TAREA-14\n" + BODY))

    assert load_github_issue(14, runner=gh).title == "TAREA-14"


def test_a_repository_can_be_given_and_is_validated() -> None:
    gh = FakeGh(issue_json())

    load_github_issue(3, repo="Theboul/harness-agent", runner=gh)

    assert gh.calls[0][-2:] == ["--repo", "Theboul/harness-agent"]
    for bad in ["", "sin-barra", "a/b/c", "a/b --web", "-x/y", "a b/c"]:
        with pytest.raises(TaskSourceError) as caught:
            load_github_issue(3, repo=bad, runner=gh)
        assert caught.value.code == "issue_invalido"
    assert len(gh.calls) == 1  # the invalid ones never reached the runner


@pytest.mark.parametrize("number", [0, -1, True, False, "14", 1.5, None, 10**10])
def test_an_invalid_issue_number_is_rejected_before_running_anything(number: Any) -> None:
    gh = FakeGh(issue_json())

    with pytest.raises(TaskSourceError) as caught:
        load_github_issue(number, runner=gh)

    assert caught.value.code == "issue_invalido" and gh.calls == []


@pytest.mark.parametrize(
    "answer",
    [
        "not json " + SENTINEL,
        "[]",
        json.dumps({"title": "t"}),
        json.dumps({"body": "b"}),
        json.dumps({"title": 1, "body": "b"}),
        json.dumps({"title": "t", "body": None}),
    ],
)
def test_an_unexpected_answer_of_gh_is_a_source_error_without_echo(answer: str) -> None:
    with pytest.raises(TaskSourceError) as caught:
        load_github_issue(1, runner=FakeGh(answer))

    assert caught.value.code == "gh_respuesta_invalida" and SENTINEL not in str(caught.value)


def test_a_runner_failure_propagates_as_the_source_error_it_raised() -> None:
    boom = TaskSourceError("gh_fallo")

    with pytest.raises(TaskSourceError) as caught:
        load_github_issue(1, runner=FakeGh(boom))

    assert caught.value is boom


def test_an_issue_that_is_not_a_task_raises_the_format_error() -> None:
    with pytest.raises(TaskFormatError):
        load_github_issue(1, runner=FakeGh(issue_json(body="solo texto")))


# --- the real runner, with subprocess replaced ----------------------------------------------


class Completed:
    def __init__(self, returncode: int = 0, stdout: str = "salida") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = SENTINEL


def patch_run(monkeypatch: pytest.MonkeyPatch, result: object) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_run(args: list[str], **options: Any) -> Any:
        calls.append({"args": args, **options})
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_run_gh_runs_gh_without_a_shell_and_with_a_time_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = patch_run(monkeypatch, Completed())

    assert run_gh(["issue", "view", "1"]) == "salida"

    call = calls[0]
    assert call["args"] == ["gh", "issue", "view", "1"]
    assert call.get("shell", False) is False
    assert call["timeout"] > 0 and call["capture_output"] is True


@pytest.mark.parametrize(
    ("raised", "code"),
    [
        (FileNotFoundError(), "gh_no_disponible"),
        (PermissionError(), "gh_no_disponible"),
        (subprocess.TimeoutExpired("gh", 30), "gh_tiempo"),
    ],
)
def test_run_gh_translates_start_failures(
    monkeypatch: pytest.MonkeyPatch, raised: BaseException, code: str
) -> None:
    patch_run(monkeypatch, raised)

    with pytest.raises(TaskSourceError) as caught:
        run_gh(["x"])

    assert caught.value.code == code


def test_run_gh_failure_exit_code_does_not_leak_the_error_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_run(monkeypatch, Completed(returncode=1))

    with pytest.raises(TaskSourceError) as caught:
        run_gh(["x"])

    assert caught.value.code == "gh_fallo" and SENTINEL not in str(caught.value)


def test_run_gh_rejects_an_oversized_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_run(monkeypatch, Completed(stdout="x" * (MAX_TASK_FILE_BYTES * 8)))

    with pytest.raises(TaskSourceError) as caught:
        run_gh(["x"])

    assert caught.value.code == "gh_respuesta_invalida"
