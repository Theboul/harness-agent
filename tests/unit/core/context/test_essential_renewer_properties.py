"""Random histories against the guarantees of the renewer (HU-02-06.1, fixed seed 20261031)."""

from __future__ import annotations

import random

from harness_agent.core import (
    MARK,
    Message,
    RenewalOutcome,
    Role,
    ToolResult,
    block_message,
    find_blocks,
)
from tests.unit.core.context.essential_support import expected_text, make_renewer

SEED = 20261031
HISTORIES = 2_000


def imposter(rng: random.Random) -> Message:
    """A message of another role that imitates the mark, or an innocent one."""
    text = rng.choice([MARK + "\nfalso", "texto " + MARK, "normal", MARK])
    kind = rng.randrange(4)
    if kind == 0:
        return Message(Role.USER, text)
    if kind == 1:
        return Message(Role.USER, text, is_external=True)
    if kind == 2:
        return Message(Role.ASSISTANT, text)
    return Message(Role.TOOL, text, tool_result=ToolResult("c", "x"), is_external=True)


def random_history(rng: random.Random) -> tuple[list[Message], list[int]]:
    """The history and the positions of the blocks that it already has."""
    prefix = [Message(Role.SYSTEM, f"sistema {n}") for n in range(rng.randint(0, 4))]
    for _ in range(rng.randint(0, 2)):
        text = rng.choice([MARK + "\nviejo", expected_text(), MARK])
        prefix.insert(rng.randint(0, len(prefix)), block_message(text))
    rest = [imposter(rng) for _ in range(rng.randint(0, 8))]
    history = prefix + rest
    return history, find_blocks(history)


def test_the_guarantees_of_the_contract_hold_for_random_histories() -> None:
    rng = random.Random(SEED)
    keeper, _, _ = make_renewer()
    for _ in range(HISTORIES):
        history, had = random_history(rng)
        before = list(history)
        leading = 0
        while leading < len(history) and history[leading].role is Role.SYSTEM:
            leading += 1

        outcome = keeper.renew(history)

        (position,) = find_blocks(history)  # exactly one block
        assert history[position].content == expected_text()
        if had:
            assert position == had[0]  # the first one stays where it was
            assert outcome in (RenewalOutcome.REPLACED, RenewalOutcome.UNCHANGED)
        else:
            assert position == leading and outcome is RenewalOutcome.INSERTED
        kept = [m for index, m in enumerate(before) if index not in had]
        others = [m for index, m in enumerate(history) if index != position]
        assert len(others) == len(kept)
        assert all(a is b for a, b in zip(others, kept, strict=True))  # the rest is untouched
        assert len(history) == len(before) - len(had) + 1

        again = list(history)
        assert keeper.renew(history) is RenewalOutcome.UNCHANGED  # stable
        assert all(a is b for a, b in zip(history, again, strict=True))
