"""The compactor: the happy path (HU-02-03 / FR-001 to FR-007, contracts and research R4).

The model is a ``FakeProvider``; the archive is a list in memory that follows the contract of the
SQLite adapter. The failures, the cancellation and the warning are in ``test_compactor_failures``.
"""

from __future__ import annotations

import pytest

from harness_agent.core import (
    ContextSettings,
    EventType,
    Message,
    Role,
    ToolDefinition,
    estimate_messages,
    frame_summary,
    is_summary,
    summary_text,
    threshold_tokens,
)
from harness_agent.core.interfaces import ProviderResponse
from tests.unit.core.context.compaction_support import (
    PAD,
    SMALL,
    Conversation,
    FakeArchive,
    make_rig,
)

SENTINEL = "VALOR-DE-PRUEBA-123"


def reply(text: str = "Se migró el módulo.") -> ProviderResponse:
    return ProviderResponse(content=text)


def example_e1() -> Conversation:
    """The session of E1 of ``store_protocol.md``: events 1 to 10, eight of them messages."""
    conversation = Conversation(FakeArchive())
    conversation.system()
    conversation.user("petición inicial protegida")
    conversation.assistant("pido una herramienta para mirar", "c1")
    conversation.tool("c1")
    conversation.assistant("miré el archivo y sigo")
    conversation.user("sigue con lo siguiente")
    conversation.assistant("hecho lo siguiente")
    conversation.user("y ahora lo último")
    conversation.assistant("hecho lo último")
    return conversation


# --- below the threshold --------------------------------------------------------------------------


async def test_below_the_threshold_nothing_is_called_or_changed() -> None:
    conversation = Conversation(FakeArchive(), pad="")
    conversation.system()
    conversation.user("hola")
    conversation.assistant("hola")
    before = list(conversation.history)
    rig = make_rig([reply()], conversation.archive)

    result = await rig.compactor.before_turn(conversation.history)

    assert result is None
    assert conversation.history == before
    assert rig.provider.call_count == 0
    assert rig.archive.commits == [] and rig.published == [] and rig.warnings == []


async def test_exactly_at_the_threshold_is_not_above_it() -> None:
    conversation = Conversation(FakeArchive(), pad="")
    conversation.system()
    conversation.user("hola")
    conversation.assistant("adiós")
    size = estimate_messages(conversation.history)
    settings = ContextSettings(window_tokens=1_000, threshold_percent=10)
    assert size <= 100
    rig = make_rig([reply()], conversation.archive, settings=settings)

    assert await rig.compactor.before_turn(conversation.history) is None
    assert rig.provider.call_count == 0


# --- one compaction -------------------------------------------------------------------------------


async def test_e1_one_summary_call_without_tools_and_the_context_in_the_agreed_order() -> None:
    conversation = example_e1()
    history = conversation.history
    original = list(history)
    rig = make_rig([reply("Se migró el módulo.")], conversation.archive)

    result = await rig.compactor.before_turn(history)

    assert rig.provider.call_count == 1
    assert rig.provider.received_tools == [None]  # the call is separate and has no tools
    sent = rig.provider.received[0]
    assert [m.role for m in sent] == [Role.SYSTEM, Role.USER]
    body = sent[1].content
    for old in ("pido una herramienta", "resultado de la herramienta", "miré el archivo"):
        assert old in body
    for kept in (
        "entorno",
        "petición inicial protegida",
        "sigue con lo siguiente",
        "hecho lo último",
    ):
        assert kept not in body + sent[0].content
    assert history[:2] == original[:2]
    assert is_summary(history[2]) and summary_text(history[2]) == "Se migró el módulo."
    assert history[3:] == original[-4:]
    assert all(a is b for a, b in zip(history[3:], original[-4:], strict=True))
    assert len(history) == 7
    assert result is not None
    assert (result.desde, result.hasta, result.eventos) == (2, 6, 5)
    assert result.estimated_after < result.estimated_before


async def test_e1_the_commit_and_the_published_event_follow_the_contract() -> None:
    conversation = example_e1()
    rig = make_rig([reply("Se migró el módulo.")], conversation.archive)

    await rig.compactor.before_turn(conversation.history)

    (commit,) = rig.archive.commits
    assert (commit.session_id, commit.protected_seq, commit.through_seq) == ("sesion-1", 1, 6)
    assert commit.summary == "Se migró el módulo."
    assert commit.summary_id != commit.event_id
    (event,) = rig.published
    assert event.type is EventType.CONTEXT_COMPACTED
    assert event.payload == {"desde": 2, "hasta": 6, "eventos": 5}
    assert event.id == commit.event_id
    assert rig.archive.covered() == [2, 3, 4, 5, 6]
    assert rig.emitted == [] and rig.warnings == []


async def test_the_commit_happens_before_the_view_changes_and_the_event_after() -> None:
    conversation = example_e1()
    history = conversation.history
    size_at_commit: list[int] = []
    size_at_publish: list[int] = []
    conversation.archive.on_commit = lambda commit: size_at_commit.append(len(history))
    rig = make_rig(
        [reply()], conversation.archive, publish=lambda event: size_at_publish.append(len(history))
    )

    await rig.compactor.before_turn(history)

    assert size_at_commit == [9]  # still the whole history when it is saved
    assert size_at_publish == [7]  # already compacted when the event is published


async def test_the_summary_that_enters_the_context_is_clean_and_has_the_credential_hidden() -> None:
    conversation = example_e1()
    url = "https://" + "usuario" + ":" + SENTINEL + "@servidor.example/repo.git"
    rig = make_rig([reply("Se migró." + chr(0x200B) + " Ver " + url)], conversation.archive)

    await rig.compactor.before_turn(conversation.history)

    (commit,) = rig.archive.commits
    expected = "Se migró. Ver https://<secreto oculto>@servidor.example/repo.git"
    assert commit.summary == expected
    assert summary_text(conversation.history[2]) == expected
    assert SENTINEL not in repr(conversation.history) + repr(rig.published)


async def test_a_second_call_that_does_not_grow_does_not_compact_again() -> None:
    conversation = example_e1()
    rig = make_rig([reply(), reply("otro")], conversation.archive)
    await rig.compactor.before_turn(conversation.history)
    after_first = list(conversation.history)

    again = await rig.compactor.before_turn(conversation.history)

    assert again is None
    assert conversation.history == after_first
    assert rig.provider.call_count == 1


async def test_e4_a_second_compaction_replaces_the_summary_and_feeds_it_to_the_model() -> None:
    conversation = example_e1()
    rig = make_rig([reply("primer resumen"), reply("segundo resumen")], conversation.archive)
    head = list(conversation.history[:2])
    await rig.compactor.before_turn(conversation.history)
    conversation.turns(3)
    first_recent = conversation.history[3]

    result = await rig.compactor.before_turn(conversation.history)

    sent = rig.provider.received[1][1].content
    assert sent.startswith("Resumen anterior:\nprimer resumen\n\nConversación a resumir:\n")
    summaries = [m for m in conversation.history if is_summary(m)]
    assert len(summaries) == 1 and summary_text(summaries[0]) == "segundo resumen"
    assert first_recent not in conversation.history
    assert conversation.history[:2] == head
    assert result is not None
    commit = rig.archive.commits[1]
    assert commit.protected_seq == 1
    ranges = [(c.protected_seq, c.through_seq) for c in rig.archive.commits]
    assert ranges[0][1] < ranges[1][1]
    first, second = rig.published
    assert second.payload["desde"] > first.payload["hasta"]
    covered = rig.archive.covered()
    assert len(covered) == len(set(covered)) and 1 not in covered


async def test_the_threshold_is_recalculated_when_the_model_changes() -> None:
    conversation = example_e1()
    settings = ContextSettings(
        window_tokens=1_000,
        windows=(("a/pequeño", 1_000), ("b/grande", 1_000_000)),
        threshold_percent=10,
        recent_percent=5,
        min_recent_messages=4,
        summary_tokens=100,
    )
    rig = make_rig([reply()], conversation.archive, settings=settings, model="b/grande")
    before = list(conversation.history)

    assert await rig.compactor.before_turn(conversation.history) is None
    assert conversation.history == before and rig.provider.call_count == 0

    rig.model[0] = "a/pequeño"
    assert await rig.compactor.before_turn(conversation.history) is not None
    assert rig.provider.call_count == 1


async def test_the_estimate_includes_the_declarations_of_the_tools() -> None:
    conversation = Conversation(FakeArchive(), pad="")
    conversation.system()
    conversation.user("hola")
    conversation.assistant("hola")
    conversation.turns(2)
    quiet = make_rig(
        [reply()],
        conversation.archive,
        settings=ContextSettings(window_tokens=1_000, recent_percent=5),
    )
    assert estimate_messages(conversation.history) < 800
    assert await quiet.compactor.before_turn(conversation.history) is None
    big = ToolDefinition("buscar", "descripción " * 400, {"type": "object"})

    loud = make_rig(
        [reply()],
        conversation.archive,
        settings=ContextSettings(window_tokens=1_000, recent_percent=5),
        definitions=[big],
    )
    result = await loud.compactor.before_turn(conversation.history)

    assert result is not None and result.estimated_before > 800


# --- E5: an assistant message without content has no event ----------------------------------------


async def test_e5_an_empty_assistant_message_has_no_event_and_the_mapping_still_holds() -> None:
    conversation = Conversation(FakeArchive())
    conversation.system()
    conversation.user("petición inicial")
    conversation.assistant("", "c1")
    conversation.tool("c1")
    conversation.assistant("Listo, el archivo tiene dos líneas")
    conversation.user("segundo mensaje del usuario con texto")
    conversation.assistant("respuesta al segundo mensaje")
    conversation.user("tercer mensaje del usuario con texto")
    conversation.assistant("respuesta al tercer mensaje")
    rig = make_rig([reply()], conversation.archive)

    result = await rig.compactor.before_turn(conversation.history)

    assert result is not None
    (commit,) = rig.archive.commits
    assert (commit.protected_seq, commit.through_seq) == (1, 5)
    assert rig.archive.covered() == [2, 3, 4, 5]


async def test_e5_a_cut_before_the_empty_assistant_leaves_its_events_unmarked() -> None:
    conversation = Conversation(FakeArchive())
    conversation.system()
    conversation.user("petición inicial")
    conversation.assistant("respuesta previa con texto")
    conversation.user("otro mensaje del usuario con texto")
    conversation.assistant("", "c1")
    conversation.tool("c1")
    conversation.assistant("Ok, hecho")
    conversation.user("último mensaje del usuario con texto")
    conversation.assistant("última respuesta")
    rig = make_rig([reply()], conversation.archive)

    result = await rig.compactor.before_turn(conversation.history)

    assert result is not None
    (commit,) = rig.archive.commits
    assert (commit.protected_seq, commit.through_seq) == (1, 3)
    assert rig.archive.covered() == [2, 3]  # the requested/decided events of c1 stay as they are
    assert conversation.history[3].tool_calls  # the empty assistant message is on the recent side


# --- nothing to do --------------------------------------------------------------------------------


async def test_without_an_initial_request_nothing_is_compacted() -> None:
    conversation = Conversation(FakeArchive(), pad="")
    conversation.system("a " * 1_200)
    conversation.assistant("sin petición " * 20)
    assert estimate_messages(conversation.history) > threshold_tokens(SMALL, "fake/test")
    rig = make_rig([reply()], conversation.archive)

    assert await rig.compactor.before_turn(conversation.history) is None
    assert rig.provider.call_count == 0


async def test_when_everything_is_recent_there_is_nothing_to_summarise() -> None:
    conversation = Conversation(FakeArchive())
    conversation.system()
    conversation.user("petición inicial con un texto bastante largo " * 20)
    conversation.assistant("respuesta con un texto bastante largo " * 20)
    conversation.user("segundo mensaje con un texto bastante largo " * 20)
    conversation.assistant("segunda respuesta con un texto bastante largo " * 20)
    rig = make_rig([reply()], conversation.archive)

    assert estimate_messages(conversation.history) > threshold_tokens(SMALL, "fake/test")
    assert await rig.compactor.before_turn(conversation.history) is None
    assert rig.provider.call_count == 0 and rig.archive.commits == []


async def test_a_region_without_message_events_is_left_alone() -> None:
    """Only the output of a verification (no event of its own) lies between head and recent."""
    conversation = Conversation(FakeArchive())
    conversation.system()
    conversation.user("petición inicial")
    conversation.history.append(
        Message(Role.USER, "salida de la verificación " + PAD * 3, is_external=True)
    )
    conversation.assistant("respuesta uno")
    conversation.user("mensaje dos")
    conversation.assistant("respuesta dos")
    conversation.user("mensaje tres")
    rig = make_rig([reply()], conversation.archive)
    before = list(conversation.history)

    assert estimate_messages(before) > threshold_tokens(SMALL, "fake/test")
    assert await rig.compactor.before_turn(conversation.history) is None
    assert conversation.history == before
    assert rig.provider.call_count == 0 and rig.archive.commits == []


async def test_when_the_archive_has_nothing_to_cover_the_history_is_left_alone() -> None:
    conversation = example_e1()
    conversation.archive.answer_none = True
    before = list(conversation.history)
    rig = make_rig([reply()], conversation.archive)

    assert await rig.compactor.before_turn(conversation.history) is None
    assert conversation.history == before
    assert rig.published == [] and rig.warnings == []


async def test_a_summary_message_object_is_the_framed_one() -> None:
    conversation = example_e1()
    rig = make_rig([reply("Se migró el módulo.")], conversation.archive)

    await rig.compactor.before_turn(conversation.history)

    assert conversation.history[2] == frame_summary("Se migró el módulo.")
    assert isinstance(conversation.history[2], Message)


@pytest.mark.parametrize("session", ["sesion-1"])
async def test_the_session_of_the_commit_is_the_one_of_the_compactor(session: str) -> None:
    conversation = example_e1()
    rig = make_rig([reply()], conversation.archive, settings=SMALL)

    await rig.compactor.before_turn(conversation.history)

    assert rig.archive.commits[0].session_id == session
