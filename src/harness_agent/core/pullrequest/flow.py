"""The step after an approved commit: push the branch and create the Pull Request (HU-11-06).

``PullRequestFlow`` is the ``CommitObserver`` that hangs from the review (HU-11-05). Both outgoing
actions are sensitive and **always ask**, one confirmation each, nothing remembered (rule 1):

1. check that the GitHub CLI exists (without it nothing is pushed: the Pull Request cannot be made);
2. read the branch (``main``/``master`` or a detached ``HEAD`` get no offer);
3. ask, then push; ask again, then create.

It fails closed: an exception from the host or the prompter means *not done* and is reported with
fixed text; ``asyncio.CancelledError`` always propagates. After any path that does not end in a
Pull Request the person gets the commit state and the text of the Pull Request, ready to copy.

Only the standard library and ``harness_agent.core`` are used here.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import TypeVar

from harness_agent.core.pullrequest.draft import PullRequestDraft, build_draft
from harness_agent.core.pullrequest.ports import PublishError, PullRequestHost, PullRequestPrompter
from harness_agent.core.redaction import hide_url_credentials
from harness_agent.core.review.approved import ApprovedChange
from harness_agent.core.verification.feedback import one_line

T = TypeVar("T")

PROTECTED_BRANCHES = frozenset({"main", "master"})
REMOTE = "origin"
MAX_URL_CHARS = 300
NO_GH = (
    "`gh` (la CLI de GitHub) no está instalado o no se puede ejecutar: no se subió nada. "
    "La rama quedó commiteada."
)
GH_CHECK_FAILED = "No se pudo comprobar si `gh` está instalado: no se subió nada."
BRANCH_UNREADABLE = "No se pudo leer la rama actual: no se subió nada."
UNSUITABLE_BRANCH = (
    "Estás en una rama que no sirve para un Pull Request (la principal o HEAD desacoplado): "
    "crea una rama de trabajo y vuelve a intentarlo. No se subió nada."
)
PROMPT_FAILED = "No se pudo pedir la confirmación: no se hizo nada."
PUSH_FAILED = "No se pudo subir la rama."
CREATE_FAILED = "No se pudo crear el Pull Request."
PUSH_DECLINED = "No se subió la rama."
CREATE_DECLINED = "No se creó el Pull Request; la rama ya está subida."
LINK_UNREADABLE = "Pull Request creado, pero no se pudo leer su enlace."
TEXT_HEADER = "Texto del Pull Request (para copiarlo):"


class PullRequestFlow:
    """Offers the Pull Request after an approved commit.

    Args:
        host: Pushes and creates (git and ``gh`` in the real one).
        prompter: Asks the person before each outgoing action and shows what happened.
    """

    def __init__(self, host: PullRequestHost, prompter: PullRequestPrompter) -> None:
        self._host = host
        self._prompter = prompter

    async def on_committed(self, approved: ApprovedChange) -> None:
        """Run the step for ``approved``; never raises except for cancellation."""
        draft = await self._prepare(approved)
        if draft is None:
            return
        pushed = False
        if not await self._ask(self._prompter.confirm_push(draft.branch)):
            self._finish(draft, PUSH_DECLINED, pushed)
            return
        if not await self._run(self._host.push(draft.branch), PUSH_FAILED, draft, pushed):
            return
        pushed = True
        if not await self._ask(self._prompter.confirm_create(draft)):
            self._finish(draft, CREATE_DECLINED, pushed)
            return
        link = await self._call(self._host.create(draft), CREATE_FAILED, draft, pushed)
        if link is None:
            return
        self._prompter.show([_link_line(link)])

    async def _prepare(self, approved: ApprovedChange) -> PullRequestDraft | None:
        """The draft, or ``None`` after telling the person why nothing can be offered."""
        fallback = build_draft(approved, "")
        try:
            available = await self._host.available()
        except PublishError as error:
            self._finish(fallback, error.message, False)
            return None
        except Exception:
            self._finish(fallback, GH_CHECK_FAILED, False)
            return None
        if not available:
            self._finish(fallback, NO_GH, False)
            return None
        try:
            branch = await self._host.current_branch()
        except PublishError as error:
            self._finish(fallback, error.message, False)
            return None
        except Exception:
            self._finish(fallback, BRANCH_UNREADABLE, False)
            return None
        if branch is None or branch in PROTECTED_BRANCHES:
            self._finish(fallback, UNSUITABLE_BRANCH, True)
            return None
        return build_draft(approved, branch)

    async def _ask(self, question: Awaitable[bool]) -> bool:
        """The answer; anything but ``True`` (including a failure) is no."""
        try:
            return await question is True
        except Exception:
            self._prompter.show([PROMPT_FAILED])
            return False

    async def _call(
        self, action: Awaitable[T], failure: str, draft: PullRequestDraft, pushed: bool
    ) -> T | None:
        """The result of an outgoing ``action``; ``None`` after reporting why it failed."""
        try:
            return await action
        except PublishError as error:
            self._finish(draft, error.message, pushed)
        except Exception:
            self._finish(draft, failure, pushed)
        return None

    async def _run(
        self, action: Awaitable[None], failure: str, draft: PullRequestDraft, pushed: bool
    ) -> bool:
        """Whether an outgoing ``action`` that returns nothing worked."""
        try:
            await action
        except PublishError as error:
            self._finish(draft, error.message, pushed)
            return False
        except Exception:
            self._finish(draft, failure, pushed)
            return False
        return True

    def _finish(self, draft: PullRequestDraft, reason: str, pushed: bool) -> None:
        """Tell why there is no Pull Request and leave its text ready to copy."""
        lines = [
            reason,
            TEXT_HEADER,
            f"Título: {draft.title}",
            "Descripción:",
            *draft.body.splitlines(),
        ]
        if not pushed and draft.branch:
            lines.append(f"Para subir la rama a mano: git push -u {REMOTE} {draft.branch}")
        elif not pushed:
            lines.append(f"Para subir la rama a mano: git push -u {REMOTE} <rama>")
        self._prompter.show(lines)


def _link_line(link: object) -> str:
    text = one_line(hide_url_credentials(link), MAX_URL_CHARS) if isinstance(link, str) else ""
    if not text.startswith("https://") or " " in text:
        return LINK_UNREADABLE
    return f"Pull Request creado: {text}"
