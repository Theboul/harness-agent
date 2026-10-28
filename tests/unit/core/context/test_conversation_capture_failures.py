"""The capture fails closed and loudly: fixed notice, sticky failure, no silent loss (T003b)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from harness_agent.core import (
    ConversationCapture,
    ConversationSaveError,
    EventType,
    Message,
    Role,
    ToolCall,
    ToolResult,
)
from tests.unit.core.context.conversation_support import (
    SESSION,
    InMemoryMessageLog,
    LoopSim,
    standard_rejection,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
FIXED = "No se pudo guardar un mensaje de la conversación; la sesión no podrá reanudarse."
PREFIX = (Message(Role.SYSTEM, "prefijo"),)
CALL = ToolCall("c1", "leer_archivo", {"path": "a.txt"})


def make() -> tuple[ConversationCapture, InMemoryMessageLog, LoopSim, list[str]]:
    log = InMemoryMessageLog()
    warnings: list[str] = []
    capture = ConversationCapture(log, warn=warnings.append, rejected_text=standard_rejection)
    sim = LoopSim(capture, SESSION, PREFIX)
    capture.bind(SESSION, sim.history, 1, len(sim.history))
    return capture, log, sim, warnings


def test_a_store_that_fails_gives_one_fixed_notice_and_a_fixed_error_without_content() -> None:
    capture, log, sim, warnings = make()
    log.fail_at = 3
    sim.user("primera")
    sim.assistant("uno")

    with pytest.raises(ConversationSaveError) as caught:
        sim.user(f"segunda {SENTINEL}")

    assert str(caught.value) == FIXED and SENTINEL not in repr(caught.value)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert warnings == [FIXED]
    assert [r.message.content for r in log.records] == ["primera", "uno"]
    assert capture.incomplete_sessions == frozenset({SESSION})


def test_the_failure_is_sticky_nothing_more_is_written_and_the_notice_is_not_repeated() -> None:
    capture, log, sim, warnings = make()
    log.fail_at = 1
    with pytest.raises(ConversationSaveError):
        sim.user("primera")
    calls = log.calls

    for action in (lambda: sim.assistant("uno"), lambda: sim.user("dos"), capture.flush):
        with pytest.raises(ConversationSaveError):
            action()

    assert log.calls == calls and log.records == []
    assert warnings == [FIXED]


def test_binding_to_another_session_saves_again_and_keeps_the_memory_of_the_failure() -> None:
    capture, log, sim, warnings = make()
    log.fail_at = 1
    with pytest.raises(ConversationSaveError):
        sim.user("primera")

    other = LoopSim(capture, "otra", PREFIX)
    capture.bind("otra", other.history, 1, len(other.history))
    other.user("hola")

    assert [r.message.content for r in log.records] == ["hola"]
    assert capture.incomplete_sessions == frozenset({SESSION})
    assert warnings == [FIXED]


def test_a_cancellation_or_an_interrupt_is_not_caught_and_changes_nothing() -> None:
    for error in (asyncio.CancelledError(), KeyboardInterrupt()):
        capture, log, sim, warnings = make()
        log.fail_at = 1
        log.error = error

        with pytest.raises(type(error)):
            sim.user("primera")

        assert warnings == [] and capture.incomplete_sessions == frozenset()
        sim.event(EventType.USER_MESSAGE, {"content": "primera"})  # the retry saves it
        assert [(r.position, r.message.content) for r in log.records] == [(1, "primera")]


def test_a_repeated_event_after_a_success_does_not_duplicate() -> None:
    capture, log, sim, warnings = make()
    sim.user("primera")

    capture.on_event(sim.events[-1])
    capture.on_event(sim.events[-1])

    assert [r.position for r in log.records] == [1] and warnings == []


@pytest.mark.parametrize(
    "scenario",
    [
        "last saved is gone",
        "user event with an assistant pending",
        "tool event for an unknown call",
        "content differs from the result",
        "rejection without a name",
    ],
)
def test_an_incoherent_state_fails_with_the_fixed_error_and_the_notice(scenario: str) -> None:
    capture, log, sim, warnings = make()
    sim.user("primera")
    sim.assistant("uno")
    action: Callable[[], object]
    if scenario == "last saved is gone":
        sim.history[:] = [*PREFIX]  # the message followed is no longer there
        action = lambda: sim.event(EventType.USER_MESSAGE, {})  # noqa: E731
        sim.history.append(Message(Role.USER, "nuevo"))
    elif scenario == "user event with an assistant pending":
        sim.history.append(Message(Role.ASSISTANT, "sin evento"))
        action = lambda: sim.event(EventType.USER_MESSAGE, {})  # noqa: E731
    elif scenario == "tool event for an unknown call":
        sim.history.append(Message(Role.TOOL, "x", tool_result=ToolResult("otro", "x")))
        action = lambda: sim.event(EventType.TOOL_FINISHED, {"call_id": "c1", "name": "n"})  # noqa: E731
    elif scenario == "content differs from the result":
        sim.history.append(Message(Role.TOOL, "uno", tool_result=ToolResult("c1", "otro")))
        action = lambda: sim.event(EventType.TOOL_FINISHED, {"call_id": "c1", "name": "n"})  # noqa: E731
    else:
        sim.history.append(Message(Role.TOOL, "x", tool_result=ToolResult("c1", "x", True)))
        action = lambda: sim.event(  # noqa: E731
            EventType.TOOL_FINISHED, {"call_id": "c1", "category": "approval_rejected"}
        )
    saved = len(log.records)

    with pytest.raises(ConversationSaveError) as caught:
        action()

    assert str(caught.value) == FIXED and warnings == [FIXED]
    assert len(log.records) == saved and capture.incomplete_sessions == frozenset({SESSION})


def test_a_notice_that_cannot_be_written_does_not_hide_the_error() -> None:
    log = InMemoryMessageLog()

    def broken(text: str) -> None:
        raise OSError("sin salida")

    capture = ConversationCapture(log, warn=broken, rejected_text=standard_rejection)
    sim = LoopSim(capture, SESSION, PREFIX)
    capture.bind(SESSION, sim.history, 1, len(sim.history))
    log.fail_at = 1

    with pytest.raises(ConversationSaveError):
        sim.user("primera")

    assert capture.incomplete_sessions == frozenset({SESSION})


def test_flushing_without_being_bound_does_nothing() -> None:
    log = InMemoryMessageLog()
    capture = ConversationCapture(log, warn=lambda text: None, rejected_text=standard_rejection)

    capture.flush()

    assert log.calls == 0


def test_a_tuple_in_the_arguments_is_cleaned_too() -> None:
    capture, log, sim, warnings = make()
    call = ToolCall("c1", "leer_archivo", {"rutas": ("a.txt", "b.txt")})
    sim.user("haz")
    sim.assistant("", (call,))
    sim.requested(call)

    assert log.records[-1].message.tool_calls[0].arguments == {"rutas": ("a.txt", "b.txt")}
    assert warnings == []


def test_binding_again_to_the_session_that_failed_keeps_the_failure() -> None:
    capture, log, sim, warnings = make()
    log.fail_at = 1
    with pytest.raises(ConversationSaveError):
        sim.user("primera")
    calls = log.calls

    capture.bind(SESSION, sim.history, 1, len(sim.history))

    with pytest.raises(ConversationSaveError):
        sim.user("segunda")
    assert log.calls == calls and warnings == [FIXED]
    assert capture.incomplete_sessions == frozenset({SESSION})
