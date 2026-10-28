"""Saving and rebuilding with random histories, a fixed seed (HU-03-04 / T005b).

A world follows the order of the loop and of the bus: the message is appended, the capture saves
it and then the recorder stores the event; now and then a compaction replaces the view in memory
and covers the events as the archive does. Whatever the story, what is rebuilt is the live view,
and a process that dies at any event leaves something that either rebuilds into a valid history or
fails with a fixed error.
"""

from __future__ import annotations

import itertools
import random

import pytest

from harness_agent.core import (
    ConversationCapture,
    Message,
    Resumed,
    ResumeError,
    Role,
    ToolCall,
    check_structure,
    frame_summary,
    is_summary,
    resume_session,
)
from tests.unit.core.context.conversation_support import (
    SESSION,
    Cut,
    InMemoryConversationSource,
    LoopSim,
    Tee,
    standard_rejection,
)

SEED = 20261101
RUNS = 120
PREFIX = (Message(Role.SYSTEM, "prefijo"),)
NAMES = ("leer_archivo", "buscar_texto", "shell")


class World:
    """One random conversation kept in step with a source, as the real system would."""

    def __init__(self, seed: int, *, compactions: bool, empties: bool = False) -> None:
        self.rng = random.Random(seed)
        self.compactions = compactions
        self.empties = empties
        self.source = InMemoryConversationSource()
        self.capture = ConversationCapture(
            self.source, warn=lambda text: None, rejected_text=standard_rejection
        )
        self.tee = Tee(self.capture, self.source)
        self.sim = LoopSim(self.tee, SESSION, PREFIX)
        self.capture.bind(SESSION, self.sim.history, 1, len(PREFIX))
        self.ids = itertools.count(1)
        self.summaries = itertools.count(1)
        self.positions: dict[int, int] = {}
        self.keep: list[Message] = []

    def reg(self, message: Message) -> Message:
        self.keep.append(message)
        self.positions[id(message)] = len(self.keep)
        return message

    def turn(self) -> None:
        rng, sim = self.rng, self.sim
        self.reg(sim.user(f"pedido {rng.randrange(10**6)}"))
        for _ in range(rng.randrange(0, 3)):
            calls = tuple(
                ToolCall(f"c{next(self.ids)}", rng.choice(NAMES), {"n": rng.randrange(9)})
                for _ in range(rng.randrange(1, 3))
            )
            self.reg(sim.assistant(rng.choice(("", "pienso")), calls))
            for call in calls:
                sim.requested(call)
                error = rng.random() < 0.3
                self.reg(
                    sim.finished(
                        call,
                        f"salida {call.id}",
                        is_error=error,
                        category="tool_error" if error else "ok",
                        external=rng.random() < 0.5,
                    )
                )
        empty = self.empties and rng.random() < 0.3
        self.reg(sim.assistant("" if empty else f"final {rng.randrange(10**6)}"))
        self.capture.flush()
        if self.compactions and rng.random() < 0.6:
            self.compact()

    def compact(self) -> None:
        view = self.sim.history
        head_end = next(i for i, m in enumerate(view) if m.role is Role.USER) + 1
        region = head_end + 1 if head_end < len(view) and is_summary(view[head_end]) else head_end
        cuts = [c for c in range(region + 1, len(view)) if view[c].role is not Role.TOOL]
        if not cuts:
            return
        cut = self.rng.choice(cuts)
        with_event = [
            m
            for m in view[region:cut]
            if m.role is not Role.ASSISTANT or m.content  # an answer with no text has no event
        ]
        if not with_event:
            return
        summary = f"resumen {next(self.summaries)}"
        self.source.cover_through(SESSION, self.positions[id(with_event[-1])], summary)
        view[:] = [*view[:head_end], frame_summary(summary), *view[cut:]]

    def run(self, turns: int) -> None:
        for _ in range(turns):
            self.turn()

    def resume(self) -> Resumed:
        return resume_session(
            self.source, SESSION, prefix=PREFIX, current_model="m", current_session_id="otra"
        )


@pytest.mark.parametrize("compactions", [False, True])
def test_the_rebuilt_context_is_the_live_view_whatever_the_story(compactions: bool) -> None:
    for run in range(RUNS):
        world = World(SEED + run, compactions=compactions)
        world.run(world.rng.randrange(1, 7))

        resumed = world.resume()

        assert list(resumed.history) == world.sim.history, f"seed {SEED + run}"
        assert resumed.closed_calls == () and check_structure(resumed.history) is None


def test_with_empty_answers_and_no_compaction_the_view_is_still_rebuilt_exactly() -> None:
    for run in range(RUNS):
        world = World(SEED + run, compactions=False, empties=True)
        world.run(world.rng.randrange(1, 6))

        assert list(world.resume().history) == world.sim.history, f"seed {SEED + run}"


def test_the_rebuild_is_deterministic() -> None:
    for run in range(20):
        world = World(SEED + run, compactions=True)
        world.run(5)

        assert world.resume() == world.resume()


@pytest.mark.parametrize("stage", ["before_capture", "after_capture"])
def test_a_process_that_dies_at_any_event_leaves_a_context_that_rebuilds_or_fails_fixed(
    stage: str,
) -> None:
    for run in range(RUNS):
        seed = SEED + run
        full = World(seed, compactions=True)
        full.run(4)
        events = full.tee.count
        assert events > 0
        world = World(seed, compactions=True)
        world.tee.die_at = random.Random(seed).randrange(1, events + 1)
        world.tee.stage = stage

        try:
            world.run(4)
        except Cut:
            pass

        try:
            resumed = world.resume()
        except ResumeError as error:
            assert str(error), f"seed {seed}"
            continue
        live = world.sim.history
        saved = list(resumed.history)[: resumed.saved_count]
        assert saved == live[: resumed.saved_count], f"seed {seed} {stage}"
        assert check_structure(resumed.history) is None, f"seed {seed} {stage}"
        closing = [m for m in resumed.history[resumed.saved_count :]]
        assert all(m.role is Role.TOOL and m.tool_result is not None for m in closing)
        assert [c for c, _ in resumed.closed_calls] == [
            m.tool_result.call_id for m in closing if m.tool_result
        ]
