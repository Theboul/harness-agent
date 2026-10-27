"""Random valid histories against the guarantees of the cut (HU-02-03, fixed seed 20261031)."""

from __future__ import annotations

import random

from harness_agent.core import (
    Message,
    Role,
    ToolCall,
    ToolResult,
    choose_cut,
    frame_summary,
    rebuild_history,
    split_history,
)

SEED = 20261031
HISTORIES = 2_000


def random_history(rng: random.Random) -> list[Message]:
    history = [Message(Role.SYSTEM, f"sistema {i}") for i in range(rng.randint(1, 3))]
    history.append(Message(Role.USER, "petición " * rng.randint(1, 20)))
    if rng.random() < 0.4:
        history.append(frame_summary("resumen " * rng.randint(1, 30)))
    counter = 0
    for _ in range(rng.randint(0, 25)):
        kind = rng.random()
        if kind < 0.25:
            history.append(Message(Role.USER, "turno " * rng.randint(1, 40)))
        elif kind < 0.3:
            history.append(Message(Role.USER, "salida de verificación", is_external=True))
        else:
            calls = tuple(
                ToolCall(f"c{counter + i}", "leer_archivo", {"path": "x" * rng.randint(1, 30)})
                for i in range(rng.choice([0, 0, 1, 1, 2, 3]))
            )
            counter += len(calls)
            history.append(Message(Role.ASSISTANT, "respuesta " * rng.randint(0, 30), calls))
            results = [
                Message(
                    Role.TOOL,
                    "dato " * rng.randint(1, 60),
                    tool_result=ToolResult(call.id, "dato"),
                    is_external=True,
                )
                for call in calls
            ]
            rng.shuffle(results)
            history.extend(results)
    return history


def orphan_results(messages: list[Message]) -> list[str]:
    """The ids of the results whose call does not appear before them in ``messages``."""
    seen: set[str] = set()
    orphans: list[str] = []
    for message in messages:
        seen.update(call.id for call in message.tool_calls)
        if message.role is Role.TOOL and message.tool_result is not None:
            if message.tool_result.call_id not in seen:
                orphans.append(message.tool_result.call_id)
    return orphans


def test_the_guarantees_of_the_contract_hold_for_random_histories() -> None:
    rng = random.Random(SEED)
    compacted = 0
    for _ in range(HISTORIES):
        history = random_history(rng)
        parts = split_history(history)
        assert parts is not None
        budget = rng.choice([0, rng.randint(0, 3_000)])
        minimum = rng.randint(1, 8)

        cut = choose_cut(history, parts.region_start, budget, minimum)

        assert cut == choose_cut(history, parts.region_start, budget, minimum)  # deterministic
        if cut is None:
            continue
        compacted += 1
        assert parts.region_start < cut <= len(history)
        assert len(history) - cut >= minimum
        assert cut == len(history) or history[cut].role is not Role.TOOL
        assert orphan_results(history[cut:]) == []
        summary = frame_summary("nuevo")
        rebuilt = rebuild_history(history, parts.region_start, cut, summary)
        assert orphan_results(rebuilt) == []
        head = history[: parts.head_end]
        assert rebuilt[: parts.head_end] == head
        assert all(a is b for a, b in zip(rebuilt[: parts.head_end], head, strict=True))
        assert rebuilt[parts.head_end] is summary
        recent = history[cut:]
        assert all(a is b for a, b in zip(rebuilt[parts.head_end + 1 :], recent, strict=True))
        assert len(rebuilt) == parts.head_end + 1 + len(recent)
    assert compacted > HISTORIES // 4  # the generator does exercise the cut
