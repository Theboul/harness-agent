"""ReviewingRunner: the observer that is told about an approved commit (HU-11-06)."""

from __future__ import annotations

import asyncio

import pytest

from harness_agent.core import (
    ApprovedChange,
    Choice,
    ReviewDecision,
    ReviewingRunner,
    TaskCriteriaItem,
)
from tests.unit.core.review.test_runner import (
    CHANGES,
    Confirmer,
    Criteria,
    Inner,
    Reviewer,
    Source,
    Turn,
)

ITEMS = [TaskCriteriaItem("c1", "Pasa", True, "Código de salida: 0", "pytest")]


class Observer:
    def __init__(self, *, error: BaseException | None = None) -> None:
        self.error = error
        self.seen: list[ApprovedChange] = []

    async def on_committed(self, approved: ApprovedChange) -> None:
        self.seen.append(approved)
        if self.error is not None:
            raise self.error


def runner(reviewer: Reviewer, source: Source, observer: Observer | None) -> ReviewingRunner[Turn]:
    criteria = Criteria(list(ITEMS))
    return ReviewingRunner(
        Inner(),
        source,
        reviewer,
        criteria,
        Confirmer(criteria),
        session_id="s1",
        ticket="TAREA-1",
        objective="Validar",
        after_commit=observer,
    )


async def test_observer_receives_the_approved_change() -> None:
    observer = Observer()
    await runner(Reviewer(ReviewDecision(Choice.APPROVE)), Source(), observer).run("t", [])
    assert len(observer.seen) == 1
    approved = observer.seen[0]
    assert (approved.ticket, approved.objective, approved.commit_id) == (
        "TAREA-1",
        "Validar",
        "abc1234",
    )
    assert approved.changes == CHANGES
    assert approved.criteria == tuple(ITEMS)


async def test_observer_is_not_told_when_the_commit_fails() -> None:
    observer = Observer()
    await runner(Reviewer(ReviewDecision(Choice.APPROVE)), Source(fail_commit=True), observer).run(
        "t", []
    )
    assert observer.seen == []


async def test_observer_is_not_told_without_approval() -> None:
    observer = Observer()
    await runner(Reviewer(ReviewDecision(Choice.NONE)), Source(), observer).run("t", [])
    assert observer.seen == []


async def test_observer_failure_does_not_fail_the_run() -> None:
    reviewer = Reviewer(ReviewDecision(Choice.APPROVE))
    result = await runner(reviewer, Source(), Observer(error=RuntimeError("x"))).run("t", [])
    assert result.status == "completed"
    assert any("Pull Request" in text for text in reviewer.informed)


async def test_cancellation_of_the_observer_propagates() -> None:
    reviewer = Reviewer(ReviewDecision(Choice.APPROVE))
    with pytest.raises(asyncio.CancelledError):
        await runner(reviewer, Source(), Observer(error=asyncio.CancelledError())).run("t", [])


async def test_without_observer_nothing_changes() -> None:
    reviewer = Reviewer(ReviewDecision(Choice.APPROVE))
    await runner(reviewer, Source(), None).run("t", [])
    assert reviewer.informed == ["Commit hecho: abc1234"]
