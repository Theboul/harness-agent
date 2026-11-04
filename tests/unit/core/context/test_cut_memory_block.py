"""``split_history`` and the memory block: it is protected head, never summarised (D-09)."""

from __future__ import annotations

from harness_agent.core import (
    HistoryParts,
    MemoryBlock,
    Message,
    Role,
    build_block,
    frame_summary,
    is_memory_block,
    place_memory_block,
    rebuild_history,
    split_history,
)
from harness_agent.core.interfaces.storage import MemoryItem


def memory() -> Message:
    text = build_block([MemoryItem("a", "dato")], 2_000).text
    assert text is not None
    return Message(Role.USER, text, is_external=True)


def system() -> Message:
    return Message(Role.SYSTEM, "entorno")


def request() -> Message:
    return Message(Role.USER, "petición")


def reply(text: str = "respuesta") -> Message:
    return Message(Role.ASSISTANT, text)


def test_with_the_block_the_parts_are_those_of_the_history_without_it() -> None:
    plain = [system(), request(), reply()]
    with_block = [system(), memory(), request(), reply()]

    assert split_history(plain) == HistoryParts(2, None, 2)
    assert split_history(with_block) == HistoryParts(3, None, 3)


def test_a_summary_after_the_request_is_still_found() -> None:
    history = [system(), memory(), request(), frame_summary("resumen"), reply()]

    assert split_history(history) == HistoryParts(3, 3, 4)


def test_without_a_request_there_is_nothing_to_split() -> None:
    assert split_history([system(), memory()]) is None
    assert split_history([memory()]) is None
    assert split_history([system(), memory(), reply()]) is None


def test_an_external_user_message_that_is_not_the_block_still_disables_it() -> None:
    other = Message(Role.USER, "cualquier cosa", is_external=True)

    assert split_history([system(), other, request()]) is None
    assert (
        split_history([system(), Message(Role.USER, "[memoria persistente] x", is_external=True)])
        is None
    )


def test_the_block_stays_in_the_head_when_the_history_is_rebuilt() -> None:
    block = memory()
    history = [system(), block, request(), reply("a"), reply("b"), reply("c")]
    parts = split_history(history)
    assert parts is not None

    rebuilt = rebuild_history(history, parts.region_start, 5, frame_summary("resumen"))

    assert rebuilt[1] is block and rebuilt[0].role is Role.SYSTEM
    assert [m.content for m in rebuilt[2:3]] == ["petición"]
    assert sum(is_memory_block(m) for m in rebuilt) == 1
    # What is summarised is the region after the head: the block is not part of it.
    assert block not in history[parts.region_start : 5]


def test_placing_the_block_does_not_disable_the_compaction() -> None:
    history = [system(), request(), reply()]
    place_memory_block(history, MemoryBlock(build_block([MemoryItem("a", "x")], 2_000).text, 1, 0))

    assert is_memory_block(history[1])
    assert split_history(history) == HistoryParts(3, None, 3)
