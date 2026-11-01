"""PullRequestFlow: two confirmations, one per outgoing action, and a safe way out (HU-11-06)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest

from harness_agent.core import (
    ApprovedChange,
    ChangeSet,
    ChangeStatus,
    FileChange,
    TaskCriteriaItem,
)
from harness_agent.core.pullrequest import (
    PublishError,
    PullRequestDraft,
    PullRequestFlow,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
URL = "https://github.com/acme/app/pull/7"
APPROVED = ApprovedChange(
    "TAREA-1: Validar",
    "Validar el correo",
    "abc1234",
    ChangeSet((FileChange("auth.py", ChangeStatus.NEW, 5, 0),), "diff"),
    (TaskCriteriaItem("c1", "Pasa", True, "Código de salida: 0", "pytest -q"),),
)


class Host:
    def __init__(
        self,
        *,
        available: bool = True,
        branch: str | None = "feature/x",
        push_error: BaseException | None = None,
        create_error: BaseException | None = None,
        branch_error: BaseException | None = None,
        url: str = URL,
    ) -> None:
        self._available = available
        self._branch = branch
        self.push_error = push_error
        self.create_error = create_error
        self.branch_error = branch_error
        self.url = url
        self.calls: list[str] = []
        self.created: list[PullRequestDraft] = []

    async def available(self) -> bool:
        self.calls.append("available")
        return self._available

    async def current_branch(self) -> str | None:
        self.calls.append("current_branch")
        if self.branch_error is not None:
            raise self.branch_error
        return self._branch

    async def push(self, branch: str) -> None:
        self.calls.append(f"push:{branch}")
        if self.push_error is not None:
            raise self.push_error

    async def create(self, draft: PullRequestDraft) -> str:
        self.calls.append("create")
        self.created.append(draft)
        if self.create_error is not None:
            raise self.create_error
        return self.url


class Prompter:
    def __init__(self, *answers: bool | BaseException) -> None:
        self.answers = list(answers)
        self.asked: list[str] = []
        self.shown: list[str] = []

    async def confirm_push(self, branch: str) -> bool:
        self.asked.append(f"push:{branch}")
        return self._next()

    async def confirm_create(self, draft: PullRequestDraft) -> bool:
        self.asked.append(f"create:{draft.title}")
        return self._next()

    def show(self, lines: Sequence[str]) -> None:
        self.shown.extend(lines)

    def _next(self) -> bool:
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    @property
    def text(self) -> str:
        return "\n".join(self.shown)


async def run(host: Host, prompter: Prompter, approved: ApprovedChange = APPROVED) -> None:
    await PullRequestFlow(host, prompter).on_committed(approved)


async def test_both_confirmed_pushes_creates_and_shows_the_link() -> None:
    host, prompter = Host(), Prompter(True, True)
    await run(host, prompter)
    assert host.calls == ["available", "current_branch", "push:feature/x", "create"]
    assert prompter.asked == ["push:feature/x", "create:TAREA-1: Validar"]
    assert host.created[0].branch == "feature/x"
    assert "## Criterios de aceptación" in host.created[0].body
    assert URL in prompter.text


async def test_declining_the_push_asks_nothing_else_and_leaves_the_text() -> None:
    host, prompter = Host(), Prompter(False)
    await run(host, prompter)
    assert host.calls == ["available", "current_branch"]
    assert prompter.asked == ["push:feature/x"]
    assert "No se subió la rama" in prompter.text
    assert "TAREA-1: Validar" in prompter.text and "## Cambios" in prompter.text
    assert "git push -u origin feature/x" in prompter.text


async def test_declining_the_creation_keeps_the_pushed_branch() -> None:
    host, prompter = Host(), Prompter(True, False)
    await run(host, prompter)
    assert host.calls == ["available", "current_branch", "push:feature/x"]
    assert "No se creó el Pull Request" in prompter.text
    assert "## Cambios" in prompter.text
    assert "git push" not in prompter.text


async def test_without_gh_nothing_is_asked_or_pushed() -> None:
    host, prompter = Host(available=False), Prompter()
    await run(host, prompter)
    assert host.calls == ["available"]
    assert prompter.asked == []
    assert "gh" in prompter.text and "no está instalado" in prompter.text
    assert "## Cambios" in prompter.text
    assert "git push -u origin" in prompter.text


@pytest.mark.parametrize("branch", ["main", "master", None])
async def test_unsuitable_branch_offers_nothing(branch: str | None) -> None:
    host, prompter = Host(branch=branch), Prompter()
    await run(host, prompter)
    assert host.calls == ["available", "current_branch"]
    assert prompter.asked == []
    assert "rama de trabajo" in prompter.text
    assert "## Cambios" in prompter.text


async def test_push_failure_is_reported_and_creation_is_not_asked() -> None:
    host = Host(push_error=PublishError("No se pudo subir la rama: sin remoto."))
    prompter = Prompter(True)
    await run(host, prompter)
    assert "No se pudo subir la rama: sin remoto." in prompter.text
    assert prompter.asked == ["push:feature/x"]
    assert "## Cambios" in prompter.text


async def test_creation_failure_is_reported_with_the_text_ready() -> None:
    host = Host(create_error=PublishError("No se pudo crear el Pull Request."))
    prompter = Prompter(True, True)
    await run(host, prompter)
    assert "No se pudo crear el Pull Request." in prompter.text
    assert "## Cambios" in prompter.text
    assert "git push" not in prompter.text


async def test_unexpected_host_errors_become_a_fixed_message() -> None:
    host = Host(push_error=RuntimeError(f"token {SENTINEL}"))
    prompter = Prompter(True)
    await run(host, prompter)
    assert SENTINEL not in prompter.text
    assert "No se pudo subir la rama" in prompter.text


async def test_error_reading_the_branch_is_contained() -> None:
    host, prompter = Host(branch_error=RuntimeError(SENTINEL)), Prompter()
    await run(host, prompter)
    assert prompter.asked == []
    assert SENTINEL not in prompter.text
    assert "## Cambios" in prompter.text


async def test_a_prompter_that_fails_means_no_and_nothing_goes_out() -> None:
    host, prompter = Host(), Prompter(RuntimeError(SENTINEL))
    await run(host, prompter)
    assert host.calls == ["available", "current_branch"]
    assert SENTINEL not in prompter.text
    assert "## Cambios" in prompter.text


async def test_a_non_boolean_answer_is_not_a_yes() -> None:
    host, prompter = Host(), Prompter("yes")  # type: ignore[arg-type]
    await run(host, prompter)
    assert "push:feature/x" not in host.calls


async def test_a_link_that_is_not_https_is_not_shown() -> None:
    host, prompter = Host(url="javascript:alert(1)"), Prompter(True, True)
    await run(host, prompter)
    assert "javascript" not in prompter.text
    assert "no se pudo leer su enlace" in prompter.text


async def test_url_credentials_in_the_link_are_hidden() -> None:
    host = Host(url=f"https://user:{SENTINEL}@github.com/acme/app/pull/7")
    prompter = Prompter(True, True)
    await run(host, prompter)
    assert SENTINEL not in prompter.text


@pytest.mark.parametrize("stage", ["push", "create", "ask"])
async def test_cancellation_propagates(stage: str) -> None:
    cancelled = asyncio.CancelledError()
    host = Host(
        push_error=cancelled if stage == "push" else None,
        create_error=cancelled if stage == "create" else None,
    )
    prompter = Prompter(cancelled if stage == "ask" else True, True)
    with pytest.raises(asyncio.CancelledError):
        await run(host, prompter)


async def test_unexpected_create_error_is_a_fixed_message() -> None:
    host = Host(create_error=RuntimeError(SENTINEL))
    prompter = Prompter(True, True)
    await run(host, prompter)
    assert SENTINEL not in prompter.text
    assert "No se pudo crear el Pull Request" in prompter.text


async def test_host_errors_before_asking_are_contained() -> None:
    class Failing(Host):
        async def available(self) -> bool:
            raise PublishError("Fallo al comprobar.")

    prompter = Prompter()
    await run(Failing(), prompter)
    assert "Fallo al comprobar." in prompter.text and prompter.asked == []

    class Broken(Host):
        async def available(self) -> bool:
            raise RuntimeError(SENTINEL)

    prompter = Prompter()
    await run(Broken(), prompter)
    assert SENTINEL not in prompter.text and "No se pudo comprobar" in prompter.text

    prompter = Prompter()
    await run(Host(branch_error=PublishError("Rama ilegible.")), prompter)
    assert "Rama ilegible." in prompter.text
