"""The loading of the memory at the start of a session (HU-04-02, AC-01 and AC-02)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime, timezone

import pytest

from harness_agent.core import (
    ContextSettings,
    MemoryItem,
    MemoryLoader,
    MemorySettings,
    Message,
    Role,
    is_memory_block,
    omitted_notice,
)

SENTINEL = "VALOR-DE-PRUEBA-123"


class FakeLog:
    """A ``MemoryLog`` that holds its entries (most recent first) or fails on demand."""

    def __init__(self, items: Sequence[MemoryItem] = (), failure: BaseException | None = None):
        self.items = list(items)
        self.failure = failure
        self.reads = 0

    def remember(self, key: str, content: str) -> None:  # pragma: no cover - not used here
        raise AssertionError("the loader only reads")

    def forget(self, key: str) -> bool:  # pragma: no cover - not used here
        raise AssertionError("the loader only reads")

    def recent(self) -> Sequence[MemoryItem]:
        self.reads += 1
        if self.failure is not None:
            raise self.failure
        return list(self.items)


def entry(key: str, content: str = "dato", day: int = 1) -> MemoryItem:
    when = datetime(2026, 11, day, tzinfo=timezone.utc)
    return MemoryItem(key, content, when, when)


def loader(
    log: FakeLog,
    *,
    settings: MemorySettings | None = None,
    context: ContextSettings | None = None,
    model: str = "fake/test",
    warnings: list[str] | None = None,
) -> MemoryLoader:
    sink = [] if warnings is None else warnings
    return MemoryLoader(
        log,
        settings or MemorySettings(enabled=True),
        context or ContextSettings(),
        model=lambda: model,
        warn=sink.append,
    )


def history() -> list[Message]:
    return [Message(Role.SYSTEM, "entorno"), Message(Role.SYSTEM, "git")]


def test_the_block_goes_after_the_prefix_and_the_request_can_follow() -> None:
    log = FakeLog([entry("b", "segundo", 3), entry("a", "primero", 2)])
    messages = history()

    block = loader(log).load_into(messages)
    messages.append(Message(Role.USER, "petición"))

    assert (block.loaded, block.omitted) == (2, 0)
    assert [m.role for m in messages] == [Role.SYSTEM, Role.SYSTEM, Role.USER, Role.USER]
    assert is_memory_block(messages[2]) and not is_memory_block(messages[3])
    assert "segundo" in messages[2].content and "primero" in messages[2].content


def test_calling_it_twice_does_not_duplicate_the_block() -> None:
    log = FakeLog([entry("a")])
    messages = history()
    memory = loader(log)

    memory.load_into(messages)
    memory.load_into(messages)

    assert len(messages) == 3


def test_without_entries_nothing_is_placed_and_nothing_is_said() -> None:
    warnings: list[str] = []
    messages = history()

    block = loader(FakeLog(), warnings=warnings).load_into(messages)

    assert block.text is None and len(messages) == 2 and warnings == []


def test_what_does_not_fit_is_told_with_the_exact_counts() -> None:
    warnings: list[str] = []
    log = FakeLog([entry(f"k{n}", "x" * 200, 30 - n) for n in range(30)])
    messages = history()

    block = loader(
        log, settings=MemorySettings(enabled=True, budget_tokens=400), warnings=warnings
    ).load_into(messages)

    assert 0 < block.loaded < 30 and block.omitted == 30 - block.loaded
    assert warnings == [omitted_notice(block.loaded, block.omitted)]
    assert warnings == [
        f"Memoria: se cargaron {block.loaded} entradas y se omitieron {block.omitted} más "
        "antiguas por el presupuesto."
    ]
    assert f"Se omitieron {block.omitted} entradas" in messages[2].content
    assert "k0" in messages[2].content  # the most recent one is the first to enter


def test_no_warning_when_everything_fits() -> None:
    warnings: list[str] = []

    loader(FakeLog([entry("a")]), warnings=warnings).load_into(history())

    assert warnings == []


def test_no_second_warning_when_the_block_was_already_there() -> None:
    warnings: list[str] = []
    log = FakeLog([entry(f"k{n}", "x" * 200, 30 - n) for n in range(30)])
    memory = loader(
        log, settings=MemorySettings(enabled=True, budget_tokens=400), warnings=warnings
    )
    messages = history()

    memory.load_into(messages)
    memory.load_into(messages)

    assert len(warnings) == 1 and len(messages) == 3


def test_the_budget_follows_the_model_that_is_active_at_each_loading() -> None:
    log = FakeLog([entry(f"k{n}", "x" * 150, 30 - n) for n in range(20)])
    context = ContextSettings(window_tokens=32_000, windows=(("fake/small", 1_500),))
    active = ["fake/test"]
    memory = MemoryLoader(
        log,
        MemorySettings(enabled=True, budget_tokens=2_000),
        context,
        model=lambda: active[0],
        warn=lambda text: None,
    )

    big = memory.load_into(history())
    active[0] = "fake/small"
    small = memory.load_into(history())

    assert small.loaded < big.loaded


def test_a_budget_that_admits_nothing_leaves_a_block_with_only_the_notice() -> None:
    warnings: list[str] = []
    log = FakeLog([entry("reciente", "r" * 600)])
    context = ContextSettings(windows=(("fake/tiny", 1_000),))  # 20 % of 800 = 160 tokens
    messages = history()

    block = loader(log, context=context, model="fake/tiny", warnings=warnings).load_into(messages)

    assert (block.loaded, block.omitted) == (0, 1)
    assert "Se omitieron 1 entradas más antiguas" in messages[2].content
    assert "reciente" not in messages[2].content
    assert warnings == [omitted_notice(0, 1)]


def test_a_memory_that_cannot_be_read_is_one_fixed_line_and_no_block() -> None:
    warnings: list[str] = []
    messages = history()
    log = FakeLog(failure=RuntimeError(f"disco roto {SENTINEL}"))

    block = loader(log, warnings=warnings).load_into(messages)

    assert block.text is None and len(messages) == 2
    assert warnings == ["No se pudo leer la memoria; la sesión empieza sin ella."]
    assert SENTINEL not in warnings[0]


@pytest.mark.parametrize("failure", [asyncio.CancelledError(), KeyboardInterrupt()])
def test_a_cancellation_or_an_interrupt_goes_through(failure: BaseException) -> None:
    with pytest.raises(type(failure)):
        loader(FakeLog(failure=failure)).load_into(history())
