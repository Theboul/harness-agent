"""ReviewingRunner: when the review opens, what each decision does (HU-11-05)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from harness_agent.core import (
    ChangeSet,
    ChangeSourceError,
    ChangeStatus,
    Choice,
    Confirmation,
    FileChange,
    Message,
    ReviewDecision,
    ReviewingRunner,
    ReviewView,
    Role,
    TaskCriteriaItem,
)

CHANGES = ChangeSet((FileChange("a.py", ChangeStatus.NEW, 3, 0),), "diff --git a/a.py")


@dataclass(frozen=True)
class Turn:
    status: str


class Inner:
    """Records the tasks it is asked to run and answers the scripted statuses."""

    def __init__(self, *statuses: str) -> None:
        self.statuses = list(statuses or ("completed",))
        self.tasks: list[str] = []

    async def run(self, task: str, history: list[Message]) -> Turn:
        self.tasks.append(task)
        return Turn(self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0])


class Source:
    def __init__(
        self,
        changes: ChangeSet = CHANGES,
        *,
        fail_snapshot: bool = False,
        fail_commit: bool = False,
    ) -> None:
        self.changes = changes
        self.fail_snapshot = fail_snapshot
        self.fail_commit = fail_commit
        self.snapshots = 0
        self.commits: list[str] = []

    async def snapshot(self) -> ChangeSet:
        self.snapshots += 1
        if self.fail_snapshot:
            raise ChangeSourceError("No se pudo leer el cambio.")
        return self.changes

    async def commit(self, message: str) -> str:
        if self.fail_commit:
            raise ChangeSourceError("No se pudo hacer el commit.")
        self.commits.append(message)
        return "abc1234"


class Reviewer:
    def __init__(self, *decisions: ReviewDecision) -> None:
        self.decisions = list(decisions)
        self.views: list[ReviewView] = []
        self.informed: list[str] = []

    async def choose(self, view: ReviewView) -> ReviewDecision:
        self.views.append(view)
        return self.decisions.pop(0)

    def inform(self, text: str) -> None:
        self.informed.append(text)


class Criteria:
    def __init__(self, items: list[TaskCriteriaItem], *, broken: bool = False) -> None:
        self.items = items
        self.broken = broken

    def load_criteria(self, session_id: str) -> list[TaskCriteriaItem]:
        if self.broken:
            raise RuntimeError("alterado")
        return list(self.items)


@dataclass
class Confirmer:
    criteria: Criteria
    result: Confirmation = Confirmation.CONFIRMED
    calls: list[tuple[str, int]] = field(default_factory=list)

    def confirm(self, session_id: str, index: int) -> Confirmation:
        self.calls.append((session_id, index))
        if self.result is Confirmation.CONFIRMED:
            old = self.criteria.items[index - 1]
            self.criteria.items[index - 1] = TaskCriteriaItem(
                old.id, old.description, True, "persona", old.command
            )
        return self.result


def objective(passes: bool = True) -> TaskCriteriaItem:
    return TaskCriteriaItem("c1", "pruebas verdes", passes, None, "pytest")


def semantic(passes: bool = False) -> TaskCriteriaItem:
    return TaskCriteriaItem("c2", "mensaje claro", passes, None, None)


def decide(
    choice: Choice, criterion: int | None = None, reason: str | None = None
) -> ReviewDecision:
    return ReviewDecision(choice, criterion, reason)


class Rig:
    def __init__(
        self,
        decisions: list[ReviewDecision],
        items: list[TaskCriteriaItem] | None = None,
        *,
        statuses: tuple[str, ...] = ("completed",),
        source: Source | None = None,
        broken: bool = False,
        confirmation: Confirmation = Confirmation.CONFIRMED,
    ) -> None:
        self.inner = Inner(*statuses)
        self.source = source or Source()
        self.reviewer = Reviewer(*decisions)
        self.criteria = Criteria(items if items is not None else [objective()], broken=broken)
        self.confirmer = Confirmer(self.criteria, confirmation)
        self.runner: ReviewingRunner[Turn] = ReviewingRunner(
            self.inner,
            self.source,
            self.reviewer,
            self.criteria,
            self.confirmer,
            session_id="s1",
            ticket="TAREA-14",
            objective="Validar el correo",
        )

    def run(self, task: str = "haz") -> Turn:
        return asyncio.run(self.runner.run(task, []))


def test_approving_commits_once_and_ends() -> None:
    rig = Rig([decide(Choice.APPROVE)])

    result = rig.run()

    assert result.status == "completed"
    assert rig.source.commits == ["TAREA-14: Validar el correo"]
    assert rig.inner.tasks == ["haz"]
    assert rig.reviewer.informed == ["Commit hecho: abc1234"]
    assert rig.reviewer.views[0].can_approve


def test_rejecting_returns_the_reason_to_the_agent_without_committing() -> None:
    rig = Rig([decide(Choice.REJECT, reason="falta el caso vacío"), decide(Choice.APPROVE)])

    rig.run()

    assert rig.inner.tasks[0] == "haz"
    assert rig.inner.tasks[1].startswith("[review_rejected]")
    assert "falta el caso vacío" in rig.inner.tasks[1]
    assert len(rig.source.commits) == 1  # the second round, once the person approved


def test_rejecting_without_a_reason_still_goes_back_to_the_agent() -> None:
    rig = Rig([decide(Choice.REJECT)], statuses=("completed", "limit_reached"))

    result = rig.run()

    assert rig.source.commits == []
    assert "Reason" not in rig.inner.tasks[1] and result.status == "limit_reached"


def test_no_decision_ends_without_commit_and_without_a_new_turn() -> None:
    rig = Rig([decide(Choice.NONE)])

    rig.run()

    assert rig.source.commits == [] and rig.inner.tasks == ["haz"]
    assert rig.reviewer.informed == ["Sin decisión: no se hizo commit."]


def test_a_turn_that_did_not_complete_opens_no_review() -> None:
    rig = Rig([], statuses=("limit_reached",))

    rig.run()

    assert rig.source.snapshots == 0 and rig.reviewer.views == []


def test_an_unmet_objective_criterion_opens_no_review() -> None:
    rig = Rig([], [objective(False)])

    rig.run()

    assert rig.source.snapshots == 0 and rig.reviewer.views == []


def test_no_changes_open_no_review() -> None:
    rig = Rig([], source=Source(ChangeSet()))

    rig.run()

    assert rig.reviewer.views == [] and rig.source.commits == []


def test_unreadable_changes_are_reported_and_nothing_is_committed() -> None:
    rig = Rig([], source=Source(fail_snapshot=True))

    rig.run()

    assert rig.reviewer.informed == ["No se pudo leer el cambio."]
    assert rig.source.commits == []


def test_unreadable_criteria_fail_closed() -> None:
    rig = Rig([], broken=True)

    rig.run()

    assert rig.source.snapshots == 0 and rig.source.commits == []
    assert rig.reviewer.informed == ["No se pudieron leer los criterios: no se revisa el cambio."]


def test_a_failed_commit_is_reported_and_not_retried() -> None:
    rig = Rig([decide(Choice.APPROVE)], source=Source(fail_commit=True))

    rig.run()

    assert rig.reviewer.informed == ["No se pudo hacer el commit."]
    assert rig.inner.tasks == ["haz"]


def test_approving_with_a_pending_semantic_criterion_is_refused_by_the_core() -> None:
    rig = Rig([decide(Choice.APPROVE), decide(Choice.NONE)], [objective(), semantic()])

    rig.run()

    assert rig.source.commits == []
    assert any("criterio" in text for text in rig.reviewer.informed)
    assert len(rig.reviewer.views) == 2


def test_confirming_a_criterion_then_approving_commits() -> None:
    rig = Rig([decide(Choice.CONFIRM, 2), decide(Choice.APPROVE)], [objective(), semantic()])

    rig.run()

    assert rig.confirmer.calls == [("s1", 2)]
    assert rig.reviewer.views[0].pending_human == (2,)
    assert rig.reviewer.views[1].pending_human == () and rig.reviewer.views[1].can_approve
    assert len(rig.source.commits) == 1


@pytest.mark.parametrize(
    "result", [Confirmation.NOT_CONFIRMABLE, Confirmation.TAMPERED, Confirmation.FAILED]
)
def test_a_confirmation_that_does_not_happen_is_reported(result: Confirmation) -> None:
    rig = Rig(
        [decide(Choice.CONFIRM, 2), decide(Choice.NONE)],
        [objective(), semantic()],
        confirmation=result,
    )

    rig.run()

    assert rig.reviewer.views[1].pending_human == (2,)
    assert "No se pudo confirmar el criterio 2." in rig.reviewer.informed


def test_rejecting_a_semantic_criterion_goes_back_to_the_agent_with_the_reason() -> None:
    rig = Rig(
        [decide(Choice.REJECT_CRITERION, 2, "no se entiende")],
        [objective(), semantic()],
        statuses=("completed", "limit_reached"),
    )

    rig.run()

    notice = rig.inner.tasks[1]
    assert notice.startswith("[criterion_rejected] Criterion 2 (mensaje claro)")
    assert "no se entiende" in notice and rig.source.commits == []
    assert rig.criteria.items[1].passes is False


def test_rejecting_an_objective_criterion_is_not_possible() -> None:
    rig = Rig([decide(Choice.REJECT_CRITERION, 1), decide(Choice.NONE)], [objective(), semantic()])

    rig.run()

    assert rig.inner.tasks == ["haz"]
    assert "Solo se pueden confirmar o rechazar criterios semánticos pendientes." in (
        rig.reviewer.informed
    )


def test_a_criterion_number_outside_the_task_is_not_valid() -> None:
    rig = Rig([decide(Choice.CONFIRM, 9), decide(Choice.NONE)], [objective(), semantic()])

    rig.run()

    assert rig.confirmer.calls == []
    assert "Solo se pueden confirmar o rechazar criterios semánticos pendientes." in (
        rig.reviewer.informed
    )


def test_a_truncated_diff_cannot_be_approved() -> None:
    cut = ChangeSet(CHANGES.files, "x", truncated=True)
    rig = Rig([decide(Choice.APPROVE), decide(Choice.NONE)], source=Source(cut))

    rig.run()

    assert rig.source.commits == []
    assert not rig.reviewer.views[0].can_approve


def test_cancellation_is_never_swallowed() -> None:
    class Cancelling(Reviewer):
        async def choose(self, view: ReviewView) -> ReviewDecision:
            raise asyncio.CancelledError

    rig = Rig([])
    rig.runner = ReviewingRunner(
        rig.inner,
        rig.source,
        Cancelling(),
        rig.criteria,
        rig.confirmer,
        session_id="s1",
        ticket=None,
        objective="o",
    )

    with pytest.raises(asyncio.CancelledError):
        rig.run()
    assert rig.source.commits == []


def test_a_reviewer_that_raises_commits_nothing() -> None:
    class Broken(Reviewer):
        async def choose(self, view: ReviewView) -> ReviewDecision:
            raise OSError("flujo roto")

    rig = Rig([])
    rig.runner = ReviewingRunner(
        rig.inner,
        rig.source,
        Broken(),
        rig.criteria,
        rig.confirmer,
        session_id="s1",
        ticket=None,
        objective="o",
    )

    with pytest.raises(OSError):
        rig.run()
    assert rig.source.commits == []


def test_the_history_is_the_one_of_the_caller() -> None:
    rig = Rig([decide(Choice.APPROVE)])
    history = [Message(Role.USER, "hola")]

    asyncio.run(rig.runner.run("haz", history))

    assert history == [Message(Role.USER, "hola")]


def test_criteria_that_cannot_be_read_after_a_confirmation_end_the_review() -> None:
    rig = Rig([decide(Choice.CONFIRM, 2), decide(Choice.APPROVE)], [objective(), semantic()])
    original = rig.confirmer.confirm

    def confirm_then_break(session_id: str, index: int) -> Confirmation:
        outcome = original(session_id, index)
        rig.criteria.broken = True
        return outcome

    rig.confirmer.confirm = confirm_then_break  # type: ignore[method-assign]

    rig.run()

    assert rig.source.commits == []
    assert rig.reviewer.informed[-1] == "No se pudieron leer los criterios: no se revisa el cambio."
