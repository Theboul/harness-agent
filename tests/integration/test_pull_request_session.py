"""Integration (HU-11-06): the Pull Request step after an approved commit in a ticket session.

Real ``compose`` and ``run_session`` (loop, policy chain, verifier, SQLite on a temporary folder,
the console reviewer and the console prompter); the provider, git (``ChangeSource``) and the
Pull Request host are doubles: no push, no ``gh``, no network, no key.
"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.tasks import load_task_file
from harness_agent.bootstrap import Composition, run_session
from harness_agent.cli import ConsolePullRequestPrompter, ConsoleReviewer
from harness_agent.core import (
    ChangeSet,
    ChangeStatus,
    FileChange,
    ProviderResponse,
    PublishError,
    PullRequestDraft,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import FIXED_TIME, build, make_config

SENTINEL = "VALOR-DE-PRUEBA-123"
TASK_TEXT = (
    "# TAREA-15\n"
    "## Objetivo\nValidar la clave\n"
    "## Criterios de aceptación\n"
    "- El mensaje de error es claro\n"
)
CHANGES = ChangeSet((FileChange("auth.py", ChangeStatus.NEW, 5, 0),), "+def validar(): ...\n")
URL = "https://github.com/acme/app/pull/7"


class Source:
    def __init__(self) -> None:
        self.commits: list[str] = []

    async def snapshot(self) -> ChangeSet:
        return CHANGES

    async def commit(self, message: str) -> str:
        self.commits.append(message)
        return "abc1234"


class Host:
    def __init__(
        self, *, available: bool = True, branch: str | None = "feature/x", fail: bool = False
    ) -> None:
        self._available = available
        self._branch = branch
        self.fail = fail
        self.calls: list[str] = []
        self.created: list[PullRequestDraft] = []

    async def available(self) -> bool:
        return self._available

    async def current_branch(self) -> str | None:
        return self._branch

    async def push(self, branch: str) -> None:
        self.calls.append(f"push:{branch}")
        if self.fail:
            raise PublishError("No se pudo subir la rama: sin remoto.")

    async def create(self, draft: PullRequestDraft) -> str:
        self.calls.append("create")
        self.created.append(draft)
        return URL


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


async def run(
    opened: list[Composition], tmp_path: Path, host: Host, typed: str, *, with_prompter: bool = True
) -> tuple[Source, str]:
    stream, output = io.StringIO(typed), io.StringIO()
    area = tmp_path / "trabajo"
    area.mkdir(exist_ok=True)
    task_file = tmp_path / "tarea.md"
    task_file.write_text(TASK_TEXT, encoding="utf-8", newline="")
    source = Source()
    composition = build(
        opened,
        make_config(tmp_path, workspace=area),
        FakeProvider([ProviderResponse(content="hecho")]),
        task=load_task_file(task_file),
        clock=lambda: FIXED_TIME,
        changes=source,
        reviewer=ConsoleReviewer(stream, output),
        pull_request_prompter=ConsolePullRequestPrompter(stream, output) if with_prompter else None,
        pull_request_host=host,
    )
    async with asyncio.timeout(10):
        await run_session(composition, input_stream=stream, output=output)
    return source, output.getvalue()


async def test_approve_confirm_push_confirm_create(
    tmp_path: Path, opened: list[Composition]
) -> None:
    host = Host()
    source, shown = await run(opened, tmp_path, host, "haz\n4\n1\n1\n1\n/salir\n")
    assert source.commits == ["TAREA-15: Validar la clave"]
    assert host.calls == ["push:feature/x", "create"]
    draft = host.created[0]
    assert draft.title == "TAREA-15"
    assert "auth.py" in draft.body
    assert "- [x] El mensaje de error es claro — confirmado por la persona" in draft.body
    assert f"Pull Request creado: {URL}" in shown


async def test_declining_the_push_sends_nothing(tmp_path: Path, opened: list[Composition]) -> None:
    host = Host()
    _, shown = await run(opened, tmp_path, host, "haz\n4\n1\n2\n/salir\n")
    assert host.calls == []
    assert "No se subió la rama" in shown and "TAREA-15" in shown


async def test_declining_the_creation_keeps_the_push(
    tmp_path: Path, opened: list[Composition]
) -> None:
    host = Host()
    _, shown = await run(opened, tmp_path, host, "haz\n4\n1\n1\n2\n/salir\n")
    assert host.calls == ["push:feature/x"]
    assert "No se creó el Pull Request" in shown


async def test_without_gh_the_session_goes_on_with_the_text_ready(
    tmp_path: Path, opened: list[Composition]
) -> None:
    host = Host(available=False)
    source, shown = await run(opened, tmp_path, host, "haz\n4\n1\n/salir\n")
    assert source.commits and host.calls == []
    assert "no está instalado" in shown and "git push -u origin" in shown


async def test_a_failed_push_is_explained(tmp_path: Path, opened: list[Composition]) -> None:
    host = Host(fail=True)
    _, shown = await run(opened, tmp_path, host, "haz\n4\n1\n1\n/salir\n")
    assert "No se pudo subir la rama: sin remoto." in shown
    assert "create" not in host.calls


async def test_no_decision_means_no_commit_and_no_pull_request(
    tmp_path: Path, opened: list[Composition]
) -> None:
    host = Host()
    source, _ = await run(opened, tmp_path, host, "haz\n4\n/salir\n/salir\n")
    assert source.commits == [] and host.calls == []


async def test_without_the_prompter_nothing_changes(
    tmp_path: Path, opened: list[Composition]
) -> None:
    host = Host()
    source, shown = await run(opened, tmp_path, host, "haz\n4\n1\n/salir\n", with_prompter=False)
    assert source.commits and host.calls == []
    assert "Pull Request" not in shown
