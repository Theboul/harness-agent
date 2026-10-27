"""The compactor when something goes wrong (HU-02-03 / FR-011, FR-015, FR-017, SC-006, R9, R16).

A failure before the view changes leaves everything as it was, says so with a fixed
``provider_error`` and lets the turn go on. The cancellation is never caught. A failure to tell the
subscribers after the summary was saved is not a failure of the compaction.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import Any

import pytest

from harness_agent.core import (
    Event,
    EventType,
    Message,
    ToolDefinition,
    is_summary,
    threshold_tokens,
)
from harness_agent.core.interfaces import (
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
)
from tests.unit.core.context.compaction_support import (
    SESSION,
    SMALL,
    Conversation,
    FakeArchive,
    Rig,
    make_rig,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
FAILURE_PAYLOAD = {
    "reason": "compaction_failed",
    "error_type": "CompactionFailed",
    "message": "No se pudo compactar el contexto; el turno continúa sin compactar.",
}
PUBLISH_WARNING = (
    "Aviso: la compactación se guardó, pero no se pudo avisar a todos los suscriptores del "
    "evento; el turno continúa con el contexto compactado."
)


class StubProvider(Provider):
    """A provider that answers with whatever it is given, or raises it."""

    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls = 0

    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        self.calls += 1
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome  # type: ignore[return-value]


def session() -> Conversation:
    conversation = Conversation(FakeArchive())
    conversation.system()
    conversation.user("petición inicial protegida " + SENTINEL)
    conversation.assistant("pido una herramienta " + SENTINEL, "c1")
    conversation.tool("c1")
    conversation.assistant("miré el archivo " + SENTINEL)
    conversation.user("sigue con lo siguiente")
    conversation.assistant("hecho lo siguiente")
    conversation.user("y ahora lo último")
    conversation.assistant("hecho lo último")
    return conversation


def rig_with(
    conversation: Conversation,
    outcome: object,
    *,
    publish: Callable[[Event], None] | None = None,
    definitions: Sequence[ToolDefinition] | Callable[[], Sequence[ToolDefinition]] = (),
    model: str | Callable[[], str] = "fake/test",
) -> tuple[Rig, StubProvider]:
    stub = StubProvider(outcome)
    rig = make_rig(
        [],
        conversation.archive,
        provider=stub,
        definitions=definitions,
        model=model,
        publish=publish,
    )
    return rig, stub


def assert_untouched(conversation: Conversation, before: list[Message], rig: Rig) -> None:
    assert conversation.history == before
    assert not any(is_summary(m) for m in conversation.history)
    assert rig.published == []
    assert rig.archive.covered() == []
    assert not any(e.type == "context_compacted" for e in rig.archive.events)


def assert_reported_without_leaking(rig: Rig) -> None:
    assert rig.emitted == [(EventType.PROVIDER_ERROR, FAILURE_PAYLOAD)]
    assert SENTINEL not in repr(rig.emitted) + repr(rig.warnings) + repr(rig.published)
    assert rig.warnings == []


# --- failures before the view changes -------------------------------------------------------------

LONG = "x" * 20_000


def provider_failures() -> list[tuple[str, object]]:
    return [
        ("quota", QuotaExceeded(SENTINEL)),
        ("timeout", ProviderTimeout(SENTINEL)),
        ("unavailable", ProviderUnavailable(SENTINEL)),
        ("runtime error", RuntimeError(SENTINEL)),
        ("empty summary", ProviderResponse(content="")),
        ("blank summary", ProviderResponse(content="  " + chr(0x200B) + chr(10) + "  ")),
        ("too long summary", ProviderResponse(content=LONG + SENTINEL)),
        ("summary that is not text", ProviderResponse(content=None)),  # type: ignore[arg-type]
    ]


@pytest.mark.parametrize(("name", "outcome"), provider_failures(), ids=lambda v: str(v)[:24])
async def test_a_failure_of_the_summary_call_or_of_its_validation(
    name: str, outcome: object
) -> None:
    conversation = session()
    before = list(conversation.history)
    rig, stub = rig_with(conversation, outcome)

    result = await rig.compactor.before_turn(conversation.history)

    assert result is None
    assert stub.calls == 1
    assert rig.archive.commits == []  # nothing is saved if the summary is not valid
    assert_untouched(conversation, before, rig)
    assert_reported_without_leaking(rig)


async def test_a_failure_to_save_leaves_nothing_behind() -> None:
    conversation = session()
    before = list(conversation.history)
    conversation.archive.failure = RuntimeError(SENTINEL)
    rig, _ = rig_with(conversation, ProviderResponse(content="Se migró el módulo."))

    assert await rig.compactor.before_turn(conversation.history) is None

    assert len(rig.archive.commits) == 1
    assert_untouched(conversation, before, rig)
    assert_reported_without_leaking(rig)


async def test_a_failure_to_read_the_events_is_a_failure_of_the_compaction() -> None:
    conversation = session()
    before = list(conversation.history)

    def broken(session_id: str) -> list[Any]:
        raise RuntimeError(SENTINEL)

    conversation.archive.message_events = broken  # type: ignore[method-assign]
    rig, stub = rig_with(conversation, ProviderResponse(content="resumen"))

    assert await rig.compactor.before_turn(conversation.history) is None

    assert stub.calls == 0
    assert_untouched(conversation, before, rig)
    assert_reported_without_leaking(rig)


def mismatches() -> dict[str, Callable[[FakeArchive], None]]:
    def extra_event(archive: FakeArchive) -> None:
        archive.add("user_message")

    def missing_event(archive: FakeArchive) -> None:
        archive.events.pop(0)

    def wrong_kind(archive: FakeArchive) -> None:
        archive.events[0].type = "assistant_message"

    return {"extra": extra_event, "missing": missing_event, "kind": wrong_kind}


@pytest.mark.parametrize("name", ["extra", "missing", "kind"])
async def test_messages_that_do_not_match_the_events_fail_closed(name: str) -> None:
    conversation = session()
    before = list(conversation.history)
    mismatches()[name](conversation.archive)
    rig, stub = rig_with(conversation, ProviderResponse(content="resumen"))

    assert await rig.compactor.before_turn(conversation.history) is None

    assert stub.calls == 0 and rig.archive.commits == []
    assert conversation.history == before and rig.published == []
    assert_reported_without_leaking(rig)


def broken_model() -> str:
    raise RuntimeError(SENTINEL)


def broken_definitions() -> list[ToolDefinition]:
    raise RuntimeError(SENTINEL)


@pytest.mark.parametrize("source", ["model", "definitions"])
async def test_a_failing_model_or_declaration_of_the_tools_does_not_stop_the_turn(
    source: str,
) -> None:
    conversation = session()
    before = list(conversation.history)
    options: dict[str, Any] = {source: broken_model if source == "model" else broken_definitions}
    rig, stub = rig_with(conversation, ProviderResponse(content="resumen"), **options)

    assert await rig.compactor.before_turn(conversation.history) is None

    assert stub.calls == 0 and conversation.history == before
    assert_reported_without_leaking(rig)


async def test_the_turn_can_go_on_after_a_failure_and_the_next_call_may_succeed() -> None:
    conversation = session()
    rig, stub = rig_with(conversation, RuntimeError(SENTINEL))
    assert await rig.compactor.before_turn(conversation.history) is None

    stub.outcome = ProviderResponse(content="Se migró el módulo.")
    result = await rig.compactor.before_turn(conversation.history)

    assert result is not None and any(is_summary(m) for m in conversation.history)
    assert len(rig.emitted) == 1  # only the first one failed


# --- cancellation is never caught -----------------------------------------------------------------


async def test_the_cancellation_of_the_summary_call_propagates_and_leaves_nothing() -> None:
    conversation = session()
    before = list(conversation.history)
    rig, _ = rig_with(conversation, asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        await rig.compactor.before_turn(conversation.history)

    assert rig.archive.commits == [] and rig.emitted == [] and rig.warnings == []
    assert_untouched(conversation, before, rig)


async def test_the_cancellation_while_publishing_propagates() -> None:
    conversation = session()

    def cancelled(event: Event) -> None:
        raise asyncio.CancelledError

    rig, _ = rig_with(conversation, ProviderResponse(content="resumen"), publish=cancelled)

    with pytest.raises(asyncio.CancelledError):
        await rig.compactor.before_turn(conversation.history)

    assert rig.emitted == [] and rig.warnings == []


@pytest.mark.parametrize("signal", [KeyboardInterrupt, SystemExit])
async def test_only_ordinary_exceptions_are_caught(signal: type[BaseException]) -> None:
    conversation = session()
    conversation.archive.failure = signal()
    rig, _ = rig_with(conversation, ProviderResponse(content="resumen"))

    with pytest.raises(signal):
        await rig.compactor.before_turn(conversation.history)

    assert rig.emitted == []


# --- R16: the summary is saved, the subscribers could not be told ---------------------------------


async def test_r16_a_failing_publish_after_the_commit_is_not_a_failure_of_the_compaction() -> None:
    conversation = session()
    calls: list[Event] = []

    def failing(event: Event) -> None:
        calls.append(event)
        raise RuntimeError(SENTINEL)

    rig, _ = rig_with(
        conversation, ProviderResponse(content="Se migró el módulo."), publish=failing
    )

    result = await rig.compactor.before_turn(conversation.history)

    assert result is not None and (result.desde, result.hasta, result.eventos) == (2, 6, 5)
    assert len(calls) == 1 and calls[0].type is EventType.CONTEXT_COMPACTED
    assert is_summary(conversation.history[2]) and len(conversation.history) == 7
    assert rig.emitted == []  # no provider_error: the compaction did happen
    assert rig.warnings == [PUBLISH_WARNING]
    assert SENTINEL not in repr(rig.warnings)
    assert len(rig.archive.commits) == 1


async def test_r16_a_context_compacted_event_is_never_stored_twice() -> None:
    conversation = session()
    rig, _ = rig_with(conversation, ProviderResponse(content="resumen"))

    await rig.compactor.before_turn(conversation.history)

    assert [e.type for e in rig.archive.events].count("context_compacted") == 1


# --- above the threshold after compacting ---------------------------------------------------------


async def test_a_context_still_above_the_threshold_is_reported_once_and_not_retried() -> None:
    conversation = session()
    settings = SMALL.__class__(
        window_tokens=1_000,
        threshold_percent=10,
        recent_percent=5,
        min_recent_messages=4,
        summary_tokens=100,
    )
    rig = make_rig(
        [ProviderResponse(content="Se migró el módulo.")], conversation.archive, settings=settings
    )

    result = await rig.compactor.before_turn(conversation.history)

    assert result is not None
    limit = threshold_tokens(settings, "fake/test")
    assert result.estimated_after > limit
    assert rig.warnings == [
        f"Aviso: el contexto sigue por encima del umbral tras compactar "
        f"(~{result.estimated_after} de {limit} tokens); el turno continúa sin reintentar."
    ]
    assert rig.provider.call_count == 1
    assert rig.emitted == []


async def test_the_example_of_the_contract_for_the_warning() -> None:
    conversation = session()
    settings = SMALL.__class__(window_tokens=1_000, threshold_percent=10, recent_percent=5)
    rig = make_rig([ProviderResponse(content="resumen")], conversation.archive, settings=settings)

    await rig.compactor.before_turn(conversation.history)

    (warning,) = rig.warnings
    assert warning.startswith("Aviso: el contexto sigue por encima del umbral tras compactar (~")
    assert warning.endswith(" de 100 tokens); el turno continúa sin reintentar.")


async def test_a_context_below_the_threshold_after_compacting_gives_no_warning() -> None:
    conversation = session()
    rig = make_rig([ProviderResponse(content="resumen")], conversation.archive)

    result = await rig.compactor.before_turn(conversation.history)

    assert result is not None
    assert result.estimated_after <= threshold_tokens(SMALL, "fake/test")
    assert rig.warnings == []


def test_the_session_of_the_helpers_is_the_one_the_tests_expect() -> None:
    assert SESSION == "sesion-1"
    assert isinstance(ProviderError("x"), Exception)
