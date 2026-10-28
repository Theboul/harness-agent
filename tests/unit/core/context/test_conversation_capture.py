"""The capture of messages: what is saved at each event (HU-03-04 / T003)."""

from __future__ import annotations

from harness_agent.core import (
    ConversationCapture,
    EventType,
    Message,
    Role,
    ToolCall,
    ToolResult,
    frame_summary,
)
from tests.unit.core.context.conversation_support import (
    SESSION,
    InMemoryMessageLog,
    LoopSim,
    standard_rejection,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
PREFIX = (Message(Role.SYSTEM, "prefijo"),)
C1 = ToolCall("c1", "leer_archivo", {"path": "a.txt"})
C2 = ToolCall("c2", "buscar_texto", {"texto": "x"})


def make(
    prefix: tuple[Message, ...] = PREFIX,
) -> tuple[ConversationCapture, InMemoryMessageLog, LoopSim]:
    log = InMemoryMessageLog()
    warnings: list[str] = []
    capture = ConversationCapture(log, warn=warnings.append, rejected_text=standard_rejection)
    sim = LoopSim(capture, SESSION, prefix)
    capture.bind(SESSION, sim.history, 1, len(sim.history))
    return capture, log, sim


def pairs(log: InMemoryMessageLog) -> list[tuple[int, Role, str | None]]:
    return [(r.position, r.message.role, r.event_id) for r in log.records]


def test_it_is_inert_until_it_is_bound_and_ignores_other_sessions() -> None:
    log = InMemoryMessageLog()
    capture = ConversationCapture(log, warn=lambda text: None, rejected_text=standard_rejection)
    sim = LoopSim(capture, SESSION, PREFIX)

    sim.user("hola")  # not bound: nothing to read from, nothing to write
    assert log.calls == 0 and capture.session_id is None

    capture.bind(SESSION, sim.history, 1, 0)
    other = LoopSim(capture, "otra-sesion", PREFIX)
    other.history.append(Message(Role.USER, "ajena"))
    other.event(EventType.USER_MESSAGE, {"content": "ajena"})
    assert log.calls == 0 and capture.session_id == SESSION


def test_a_turn_with_tools_is_saved_in_order_with_the_event_of_each_message() -> None:
    capture, log, sim = make()

    sim.user("lee a.txt")  # e1
    sim.assistant("", (C1, C2))  # no event
    sim.requested(C1)  # e2: saves the assistant that only asks for tools
    sim.finished(C1, "texto de a")  # e3
    sim.requested(C2)  # e4: nothing pending
    sim.finished(C2, "sin coincidencias", is_error=True, category="tool_error")  # e5
    sim.assistant("listo")  # e6

    assert pairs(log) == [
        (1, Role.USER, "e1"),
        (2, Role.ASSISTANT, None),
        (3, Role.TOOL, "e3"),
        (4, Role.TOOL, "e5"),
        (5, Role.ASSISTANT, "e6"),
    ]
    assert [r.message for r in log.records] == sim.history[1:]
    assert capture.session_id == SESSION


def test_a_final_empty_answer_is_saved_only_when_the_turn_closes() -> None:
    capture, log, sim = make()
    sim.user("hola")
    sim.assistant("")  # an empty answer with no calls has no event

    assert pairs(log) == [(1, Role.USER, "e1")]
    capture.flush()
    capture.flush()  # nothing pending: nothing written

    assert pairs(log) == [(1, Role.USER, "e1"), (2, Role.ASSISTANT, None)]
    assert log.calls == 2


def test_two_equal_messages_are_two_messages_and_a_repeated_event_does_not_duplicate() -> None:
    capture, log, sim = make()
    sim.user("igual")
    sim.assistant("ok")
    sim.user("igual")
    repeated = sim.events[-1]

    capture.on_event(repeated)
    capture.on_event(repeated)

    assert [r.message.content for r in log.records] == ["igual", "ok", "igual"]
    assert [r.position for r in log.records] == [1, 2, 3]


def test_a_compaction_that_replaces_the_view_in_place_does_not_save_anything_else() -> None:
    capture, log, sim = make()
    sim.user("primera")
    sim.assistant("uno")
    sim.user("segunda")
    sim.assistant("dos")
    first = sim.history[1]
    recent = sim.history[-2:]
    block = Message(Role.SYSTEM, "bloque esencial")
    sim.history[:] = [*PREFIX, block, first, frame_summary("resumen"), *recent]
    saved = len(log.records)

    sim.user("tercera")
    sim.assistant("tres")

    new = log.records[saved:]
    assert [r.message.content for r in new] == ["tercera", "tres"]
    assert [r.position for r in new] == [5, 6]
    texts = [r.message.content for r in log.records]
    assert "bloque esencial" not in texts and not any("resumen" in t for t in texts)
    assert "prefijo" not in texts


def test_the_output_of_a_verifier_is_never_saved() -> None:
    capture, log, sim = make()
    sim.user("trabaja")
    sim.assistant("listo")
    feedback = Message(Role.USER, "salida del verificador", is_external=True)
    sim.history.append(feedback)

    sim.user("sigue")

    assert [r.message.content for r in log.records] == ["trabaja", "listo", "sigue"]


def test_a_rejection_is_saved_with_the_standard_text_and_never_with_the_reason() -> None:
    capture, log, sim = make()
    call = ToolCall("c9", "shell", {"command": "ls"})
    reason = f"{standard_rejection('shell')} Reason: '{SENTINEL}'"
    sim.user("haz")
    sim.assistant("", (call,))
    sim.requested(call)

    sim.finished(call, reason, is_error=True, category="approval_rejected")

    saved = log.records[-1].message
    assert saved.content == standard_rejection("shell")
    assert saved.tool_result == ToolResult("c9", standard_rejection("shell"), True)
    assert SENTINEL not in repr(log.records)
    assert sim.history[-1].content == reason  # the memory keeps what the model saw


def test_the_same_text_with_another_category_is_not_a_rejection() -> None:
    capture, log, sim = make()
    call = ToolCall("c9", "leer_archivo", {"path": "n.txt"})
    cited = f"{standard_rejection('x')} (cita de un archivo)"
    sim.user("haz")
    sim.assistant("", (call,))
    sim.requested(call)

    sim.finished(call, cited, category="ok")

    assert log.records[-1].message.content == cited


def test_a_resumed_session_does_not_save_what_it_loaded_and_saves_the_closing_results() -> None:
    log = InMemoryMessageLog()
    capture = ConversationCapture(log, warn=lambda text: None, rejected_text=standard_rejection)
    first = Message(Role.USER, "peticion")
    asks = Message(Role.ASSISTANT, "", (C1, C2))
    done = Message(Role.TOOL, "ok", tool_result=ToolResult("c1", "ok"))
    closing = Message(
        Role.TOOL,
        "[tool_interrupted] x",
        tool_result=ToolResult("c2", "[tool_interrupted] x", True),
    )
    history = [*PREFIX, first, frame_summary("resumen"), asks, done, closing]
    sim = LoopSim(capture, SESSION)
    sim.history = history
    capture.bind(SESSION, history, 5, 5)  # the closing result is not saved yet

    assert log.calls == 0
    capture.flush()  # the closing result waits for its own event
    assert log.calls == 0
    sim.event(
        EventType.TOOL_FINISHED,
        {"call_id": "c2", "name": "buscar_texto", "is_error": True, "category": "tool_interrupted"},
    )

    assert pairs(log) == [(5, Role.TOOL, "e1")]
    assert log.records[0].message == closing
    sim.user("nueva")
    assert [r.position for r in log.records] == [5, 6]


def test_a_new_session_binds_with_nothing_saved_and_numbers_from_the_position_given() -> None:
    log = InMemoryMessageLog()
    capture = ConversationCapture(log, warn=lambda text: None, rejected_text=standard_rejection)
    sim = LoopSim(capture, SESSION, PREFIX)
    capture.bind(SESSION, sim.history, 8, len(sim.history))

    sim.user("hola")

    assert [r.position for r in log.records] == [8]
