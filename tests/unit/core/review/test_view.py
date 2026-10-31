"""The review view: criteria states, blockers and the totals of the change (HU-11-05)."""

from __future__ import annotations

from harness_agent.core import (
    Blocker,
    ChangeSet,
    ChangeStatus,
    FileChange,
    ReviewCriterionState,
    TaskCriteriaItem,
    build_view,
)

CHANGES = ChangeSet(
    files=(
        FileChange("src/auth.py", ChangeStatus.NEW, 12, 0),
        FileChange("tests/test_auth.py", ChangeStatus.MODIFIED, 6, 3),
        FileChange("logo.png", ChangeStatus.MODIFIED, None, None),
    ),
    patch="diff",
)


def item(index: int, *, command: str | None, passes: bool) -> TaskCriteriaItem:
    return TaskCriteriaItem(f"c{index}", f"criterio {index}", passes, None, command)


def test_totals_ignore_binary_files() -> None:
    assert CHANGES.total_added == 18 and CHANGES.total_removed == 3


def test_an_empty_change_set_is_empty() -> None:
    assert ChangeSet().is_empty and not CHANGES.is_empty


def test_states_follow_command_and_passes() -> None:
    view = build_view(
        "T-1",
        CHANGES,
        [
            item(1, command="pytest", passes=True),
            item(2, command="pytest", passes=False),
            item(3, command=None, passes=False),
            item(4, command=None, passes=True),
        ],
    )

    assert [c.state for c in view.criteria] == [
        ReviewCriterionState.MET,
        ReviewCriterionState.PENDING,
        ReviewCriterionState.PENDING_HUMAN,
        ReviewCriterionState.CONFIRMED_HUMAN,
    ]
    assert [c.index for c in view.criteria] == [1, 2, 3, 4]
    assert view.objective_total == 2 and view.objective_met == 1
    assert view.pending_human == (3,)


def test_a_pending_semantic_criterion_blocks_approval() -> None:
    view = build_view("T-1", CHANGES, [item(1, command=None, passes=False)])

    assert view.blockers == (Blocker.SEMANTIC_PENDING,) and not view.can_approve


def test_a_truncated_patch_blocks_approval() -> None:
    cut = ChangeSet(CHANGES.files, "x", truncated=True)

    view = build_view("T-1", cut, [item(1, command="pytest", passes=True)])

    assert view.blockers == (Blocker.TRUNCATED,) and not view.can_approve


def test_everything_in_order_can_be_approved() -> None:
    view = build_view(
        "T-1", CHANGES, [item(1, command="pytest", passes=True), item(2, command=None, passes=True)]
    )

    assert view.can_approve and view.blockers == ()


def test_the_description_is_one_clean_line() -> None:
    odd = TaskCriteriaItem("c1", "uno\ndos\x1b[31m " + "x" * 400, False, None, None)

    (criterion,) = build_view("T", CHANGES, [odd]).criteria

    assert "\n" not in criterion.description and "\x1b" not in criterion.description
    assert len(criterion.description) <= 120


def test_no_changes_block_approval() -> None:
    view = build_view("T-1", ChangeSet(), [item(1, command="pytest", passes=True)])

    assert view.blockers == (Blocker.NO_CHANGES,) and not view.can_approve
