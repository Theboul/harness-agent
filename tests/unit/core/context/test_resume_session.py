"""resume_session: the order of the checks and what is read (HU-03-04 / T005b)."""

from __future__ import annotations

import pytest

from harness_agent.core import (
    AlreadyCurrentSession,
    ConversationInconsistent,
    InvalidSessionId,
    Message,
    MessageRecord,
    Role,
    SessionDetailMissing,
    StoredConversation,
    StoredMessage,
    TaskSessionNotResumable,
    UnknownSession,
    resume_session,
)
from tests.unit.core.context.conversation_support import InMemoryConversationSource

SENTINEL = "VALOR-DE-PRUEBA-123"
P = Message(Role.SYSTEM, "prefijo")


class Spy:
    """A source that returns what it is given and counts the reads."""

    def __init__(self, stored: StoredConversation | None) -> None:
        self.stored = stored
        self.reads: list[str] = []

    def load_conversation(self, session_id: str) -> StoredConversation | None:
        self.reads.append(session_id)
        return self.stored


def conversation(**changes: object) -> StoredConversation:
    rows = (
        StoredMessage(MessageRecord(1, Message(Role.USER, "hola"), "e1"), False),
        StoredMessage(MessageRecord(2, Message(Role.ASSISTANT, "ok"), "e2"), False),
    )
    values: dict[str, object] = {
        "session_id": "s1",
        "model": "m",
        "is_task": False,
        "messages": rows,
        "summary": None,
        "events_without_row": 0,
        "last_event_type": "assistant_message",
    }
    values.update(changes)
    return StoredConversation(**values)  # type: ignore[arg-type]


def resume(source: Spy, text: object, **keywords: object):  # type: ignore[no-untyped-def]
    options: dict[str, object] = {
        "prefix": (P,),
        "current_model": "m",
        "current_session_id": "actual",
    }
    options.update(keywords)
    return resume_session(source, text, **options)  # type: ignore[arg-type]


@pytest.mark.parametrize("text", ["", "../x", "a" * 129, SENTINEL + "/x"])
def test_an_invalid_identifier_never_reaches_the_source(text: str) -> None:
    source = Spy(conversation())

    with pytest.raises(InvalidSessionId):
        resume(source, text)

    assert source.reads == []


def test_the_current_session_is_refused_without_reading_anything() -> None:
    source = Spy(conversation())

    with pytest.raises(AlreadyCurrentSession):
        resume(source, " actual ", current_session_id="actual")

    assert source.reads == []


def test_a_session_whose_saving_failed_in_this_run_is_refused_even_if_it_looks_whole() -> None:
    source = Spy(conversation())

    with pytest.raises(SessionDetailMissing):
        resume(source, "s1", known_incomplete=frozenset({"s1"}))

    assert source.reads == []


def test_the_current_session_is_checked_before_the_incomplete_ones() -> None:
    with pytest.raises(AlreadyCurrentSession):
        resume(Spy(None), "x", current_session_id="x", known_incomplete=frozenset({"x"}))


def test_an_unknown_session_a_task_session_and_a_missing_detail_each_get_their_error() -> None:
    with pytest.raises(UnknownSession):
        resume(Spy(None), "s1")
    with pytest.raises(TaskSessionNotResumable):
        resume(Spy(conversation(is_task=True)), "s1")
    with pytest.raises(SessionDetailMissing):
        resume(Spy(conversation(events_without_row=2)), "s1")


def test_a_task_session_is_refused_before_looking_at_its_messages() -> None:
    broken = conversation(is_task=True, messages=(), summary="S")

    with pytest.raises(TaskSessionNotResumable):
        resume(Spy(broken), "s1")


def test_a_good_session_is_rebuilt_with_the_prefix_and_the_current_model() -> None:
    source = Spy(conversation(model="viejo"))

    resumed = resume(source, "s1", current_model="nuevo")

    assert source.reads == ["s1"]
    assert resumed.history[0] == P and len(resumed.history) == 3 and resumed.model_changed


def test_an_empty_session_resumes_as_a_new_one_with_the_prefix() -> None:
    resumed = resume(Spy(conversation(messages=(), last_event_type=None)), "s1")

    assert resumed.history == (P,) and resumed.empty and resumed.next_position == 1


def test_an_incoherent_session_fails_with_the_fixed_error() -> None:
    with pytest.raises(ConversationInconsistent) as caught:
        resume(Spy(conversation(summary="S")), "s1")

    assert SENTINEL not in str(caught.value)


def test_the_in_memory_source_reports_a_session_it_does_not_know_as_none() -> None:
    source = InMemoryConversationSource()

    with pytest.raises(UnknownSession):
        resume_session(source, "nada", prefix=(P,), current_model="m", current_session_id="x")
