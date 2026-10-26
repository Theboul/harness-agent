"""SPK-03 spike: does a history summary keep the goal, and what must live outside it?

Characterization tests over a simulated long session. There is no network, no key and no real
model: the summary comes from a deterministic stress model (``LossySummarizer``) or from a
``FakeProvider`` script. They show how the context is assembled and what survives two
compactions; they do NOT show how a real model summarizes (that run is a pending human task).
Findings: ``docs/decisiones/SPK-03-compactacion-bloque-fijo.md``.
"""

from __future__ import annotations

import pytest

from harness_agent.core import Message, ProviderResponse, Role
from tests.doubles.fake_provider import FakeProvider
from tests.spikes.compaction_sim import (
    BLOCK_HEADER,
    DECISION_KEYS,
    ESSENTIAL_KEYS,
    SEEDS,
    SUMMARY_HEADER,
    CompactionState,
    CriteriaUnavailable,
    EssentialBlock,
    InMemoryCriteria,
    LossySummarizer,
    ProviderSummarizer,
    assemble_pinned_block,
    assemble_summary_only,
    block_from_seeds,
    build_long_session,
    compact,
    estimate_tokens,
    locate,
    safe_cut,
    sentinel_of,
    survival,
    text_of,
)


class TestScenario:
    """T001: the long session is deterministic and every seed sits where it should."""

    def test_session_is_deterministic(self) -> None:
        assert build_long_session() == build_long_session()

    def test_session_is_long_enough_to_need_compaction(self) -> None:
        history = build_long_session()
        assert len(history) >= 80
        assert estimate_tokens(history) > 4_000

    def test_every_sentinel_appears_exactly_once(self) -> None:
        text = [m.content for m in build_long_session()]
        for seed in SEEDS:
            hits = sum(seed.sentinel in chunk for chunk in text)
            assert hits == 1, f"{seed.key}: {hits} apariciones de {seed.sentinel}"

    def test_essential_seeds_are_in_the_first_message_and_decisions_later(self) -> None:
        history = build_long_session()
        first = history[0]
        assert first.role is Role.USER
        for key in ESSENTIAL_KEYS:
            assert sentinel_of(key) in first.content
        for key in DECISION_KEYS:
            assert sentinel_of(key) not in first.content

    def test_tool_results_always_follow_their_call(self) -> None:
        history = build_long_session()
        open_calls: set[str] = set()
        for message in history:
            if message.role is Role.ASSISTANT:
                assert not open_calls
                open_calls = {call.id for call in message.tool_calls}
            elif message.role is Role.TOOL:
                assert message.tool_result is not None
                assert message.tool_result.call_id in open_calls
                open_calls.discard(message.tool_result.call_id)
        assert not open_calls


class TestAssembly:
    """T002: the two ways of assembling the context and the cut between old and recent."""

    def test_pinned_block_is_a_system_message_before_the_summary(self) -> None:
        history = build_long_session()
        criteria = InMemoryCriteria({"criteria:TCK-4821": sentinel_of("criterios")})
        state = CompactionState(summary="resumen previo", covered_until=40)
        context = assemble_pinned_block(history, state, block_from_seeds(), criteria)
        assert context[0].role is Role.SYSTEM
        assert context[1].role is Role.SYSTEM
        for key in ESSENTIAL_KEYS:
            assert sentinel_of(key) in context[1].content
        assert "resumen previo" in context[2].content
        assert context[3:] == list(history[40:])

    def test_summary_only_has_no_task_facts_outside_the_history(self) -> None:
        history = build_long_session()
        context = assemble_summary_only(history, CompactionState())
        assert context[1:] == list(history)
        assert not any(sentinel_of(key) in context[0].content for key in ESSENTIAL_KEYS)

    def test_missing_criteria_source_fails_closed(self) -> None:
        with pytest.raises(CriteriaUnavailable):
            block_from_seeds().render(InMemoryCriteria({}))

    def test_block_has_exactly_the_five_keys_of_the_card(self) -> None:
        assert tuple(EssentialBlock.__dataclass_fields__) == (
            "goal",
            "instructions",
            "rules",
            "ticket_id",
            "criteria_ref",
        )

    @pytest.mark.parametrize("desired", range(1, 82))
    def test_safe_cut_never_orphans_a_tool_result(self, desired: int) -> None:
        history = build_long_session()
        cut = safe_cut(history, desired)
        assert 0 <= cut <= desired
        old, recent = history[:cut], history[cut:]
        if recent:
            assert recent[0].role is not Role.TOOL
        if old:
            assert not old[-1].tool_calls

    def test_safe_cut_moves_back_to_the_assistant_that_asked(self) -> None:
        history = build_long_session()
        tool_index = next(i for i, m in enumerate(history) if m.role is Role.TOOL)
        assert safe_cut(history, tool_index) == tool_index - 1


class TestSummarizers:
    """T003: the stress model is deterministic; the provider summarizer sends a separate call."""

    async def test_lossy_summary_is_deterministic_and_within_budget(self) -> None:
        old = build_long_session()[:40]
        first = await LossySummarizer(budget_chars=900).summarize(old, "")
        second = await LossySummarizer(budget_chars=900).summarize(old, "")
        assert first == second
        assert len(first) <= 900

    async def test_lossy_summary_drops_the_oldest_first(self) -> None:
        old = build_long_session()[:40]
        summary = await LossySummarizer(budget_chars=900).summarize(old, "")
        assert sentinel_of("objetivo") not in summary
        assert "salida 10" in summary

    async def test_lossy_summary_keeps_the_tail_of_the_previous_summary(self) -> None:
        previous = "ANTIGUO " * 50 + "FINAL-DEL-PREVIO"
        summary = await LossySummarizer(budget_chars=300).summarize(
            [build_long_session()[1]], previous
        )
        assert "FINAL-DEL-PREVIO" in summary
        assert len(summary) <= 300

    async def test_provider_summarizer_makes_one_separate_call_without_tools(self) -> None:
        provider = FakeProvider([ProviderResponse(content="resumen fiel")])
        old = build_long_session()[:8]
        summary = await ProviderSummarizer(provider).summarize(old, "resumen anterior")
        assert summary == "resumen fiel"
        assert provider.call_count == 1
        assert provider.received_tools == [None]
        system, request = provider.received[0]
        assert system.role is Role.SYSTEM
        assert "decisiones" in system.content
        assert request.role is Role.USER
        assert "resumen anterior" in request.content
        assert "Turno 1" in request.content


# The session grows between compactions: the first one runs at 56 messages, the second at 81.
KEEP_RECENT = 30
FIRST_PASS_AT = 56
BUDGET = 3_000
LOST_ESSENTIALS = ("objetivo", "instrucciones", "reglas", "ticket")


def criteria_source() -> InMemoryCriteria:
    return InMemoryCriteria({"criteria:TCK-4821": text_of("criterios")})


async def compact_twice(
    summarizer: LossySummarizer,
) -> tuple[tuple[Message, ...], CompactionState, CompactionState]:
    history = build_long_session()
    first = await compact(
        history[:FIRST_PASS_AT], CompactionState(), summarizer, keep_recent=KEEP_RECENT
    )
    second = await compact(history, first, summarizer, keep_recent=KEEP_RECENT)
    return history, first, second


class TestDoubleCompaction:
    """T004: what survives two compactions with 'summary only' and with the 'pinned block'."""

    async def test_summary_only_still_has_everything_after_the_first_pass(self) -> None:
        history, first, _ = await compact_twice(LossySummarizer(BUDGET))
        context = assemble_summary_only(history[:FIRST_PASS_AT], first)
        assert all(survival(context, ESSENTIAL_KEYS).values())
        assert {locate(context, sentinel_of(key)) for key in ESSENTIAL_KEYS} == {"resumen"}

    async def test_summary_only_loses_goal_instructions_rules_and_ticket_on_the_second(
        self,
    ) -> None:
        history, _, second = await compact_twice(LossySummarizer(BUDGET))
        found = survival(assemble_summary_only(history, second), ESSENTIAL_KEYS)
        assert [key for key, alive in found.items() if not alive] == list(LOST_ESSENTIALS)
        # The criteria text survives only because it sat at the tail of the opening line: luck.
        assert found["criterios"]

    async def test_pinned_block_keeps_all_five_after_both_passes(self) -> None:
        history, _, second = await compact_twice(LossySummarizer(BUDGET))
        context = assemble_pinned_block(history, second, block_from_seeds(), criteria_source())
        assert all(survival(context, ESSENTIAL_KEYS).values())
        assert {locate(context, sentinel_of(key)) for key in ESSENTIAL_KEYS} == {"bloque"}
        initial = assemble_pinned_block(
            history[:FIRST_PASS_AT], CompactionState(), block_from_seeds(), criteria_source()
        )
        assert context[1] == initial[1]

    def test_pinned_block_does_not_depend_on_the_summary_at_all(self) -> None:
        history = build_long_session()
        empty = CompactionState(summary="", covered_until=len(history) - KEEP_RECENT)
        context = assemble_pinned_block(history, empty, block_from_seeds(), criteria_source())
        assert all(survival(context, ESSENTIAL_KEYS).values())

    async def test_decisions_survive_two_passes_only_because_they_are_recent(self) -> None:
        history, _, second = await compact_twice(LossySummarizer(BUDGET))
        for context in (
            assemble_summary_only(history, second),
            assemble_pinned_block(history, second, block_from_seeds(), criteria_source()),
        ):
            assert all(survival(context, DECISION_KEYS).values())

    async def test_a_third_pass_drops_every_decision_in_both_designs(self) -> None:
        history = build_long_session(40)
        summarizer = LossySummarizer(BUDGET)
        state = CompactionState()
        for size in (56, 100, len(history)):
            state = await compact(history[:size], state, summarizer, keep_recent=KEEP_RECENT)
        for context in (
            assemble_summary_only(history, state),
            assemble_pinned_block(history, state, block_from_seeds(), criteria_source()),
        ):
            assert not any(survival(context, DECISION_KEYS).values())

    async def test_compaction_shrinks_the_context_to_a_bounded_size(self) -> None:
        history, _, second = await compact_twice(LossySummarizer(BUDGET))
        full = estimate_tokens(history)
        compacted = estimate_tokens(
            assemble_pinned_block(history, second, block_from_seeds(), criteria_source())
        )
        assert compacted < full * 0.6
        block_tokens = estimate_tokens([block_from_seeds().render(criteria_source())])
        assert block_tokens < 150


class TestCompactionProperties:
    """T005: what goes into the separate summary call and what comes out of the compaction."""

    @staticmethod
    def provider() -> FakeProvider:
        return FakeProvider(
            [ProviderResponse(content="resumen uno"), ProviderResponse(content="resumen dos")]
        )

    async def test_summary_call_gets_only_old_events_and_the_previous_summary(self) -> None:
        history = build_long_session()
        provider = self.provider()
        summarizer = ProviderSummarizer(provider)
        first = await compact(
            history[:FIRST_PASS_AT], CompactionState(), summarizer, keep_recent=KEEP_RECENT
        )
        await compact(history, first, summarizer, keep_recent=KEEP_RECENT)
        assert provider.call_count == 2
        one, two = (request[1].content for request in provider.received)
        assert "Turno 6" in one
        assert "Turno 14" not in one
        assert "Resumen anterior:\nresumen uno" in two
        assert "Turno 6:" not in two
        for request in provider.received:
            assert all(BLOCK_HEADER not in message.content for message in request)
            assert request[0].role is Role.SYSTEM
            assert len(request) == 2

    async def test_recent_messages_stay_whole_and_the_cut_is_safe(self) -> None:
        history = build_long_session()
        state = await compact(history, CompactionState(), LossySummarizer(BUDGET), keep_recent=31)
        context = assemble_summary_only(history, state)
        recent = list(history[state.covered_until :])
        assert len(recent) >= 31
        assert context[-len(recent) :] == recent
        assert recent[0].role is not Role.TOOL

    async def test_the_original_history_is_never_modified(self) -> None:
        history = build_long_session()
        await compact(history, CompactionState(), LossySummarizer(BUDGET), keep_recent=KEEP_RECENT)
        assert history == build_long_session()

    async def test_compacting_again_with_nothing_new_makes_no_call(self) -> None:
        history = build_long_session()
        provider = self.provider()
        summarizer = ProviderSummarizer(provider)
        once = await compact(history, CompactionState(), summarizer, keep_recent=KEEP_RECENT)
        again = await compact(history, once, summarizer, keep_recent=KEEP_RECENT)
        assert again == once
        assert provider.call_count == 1

    async def test_nothing_to_compact_when_the_history_is_shorter_than_the_recent_window(
        self,
    ) -> None:
        history = build_long_session()[:20]
        provider = self.provider()
        state = await compact(
            history, CompactionState(), ProviderSummarizer(provider), keep_recent=KEEP_RECENT
        )
        assert state == CompactionState()
        assert provider.call_count == 0


class TestEssentialBlock:
    """T006: prefix stability, criteria by reference and what a model would actually receive."""

    async def test_block_message_is_identical_before_and_after_compacting(self) -> None:
        history, first, second = await compact_twice(LossySummarizer(BUDGET))
        block = block_from_seeds()
        early = history[:FIRST_PASS_AT]
        rendered = [
            assemble_pinned_block(early, CompactionState(), block, criteria_source())[1],
            assemble_pinned_block(early, first, block, criteria_source())[1],
            assemble_pinned_block(history, second, block, criteria_source())[1],
        ]
        assert rendered[0] == rendered[1] == rendered[2]
        assert rendered[0].content.encode() == rendered[2].content.encode()

    def test_criteria_are_read_from_the_source_at_every_assembly(self) -> None:
        history = build_long_session()
        block = block_from_seeds()
        live = InMemoryCriteria({block.criteria_ref: "CRI-9999 criterio vigente"})
        state = CompactionState(summary="Los criterios eran: CRI-0000 viejo", covered_until=50)
        context = assemble_pinned_block(history, state, block, live)
        assert locate(context, "CRI-9999") == "bloque"
        assert locate(context, "CRI-0000") == "resumen"
        order = [m.content.split("\n")[0] for m in context if m.role is Role.SYSTEM]
        assert order.index(BLOCK_HEADER) < order.index(SUMMARY_HEADER)

    def test_missing_source_fails_closed_even_if_the_summary_has_a_copy(self) -> None:
        history = build_long_session()
        state = CompactionState(summary=text_of("criterios"), covered_until=50)
        with pytest.raises(CriteriaUnavailable):
            assemble_pinned_block(history, state, block_from_seeds(), InMemoryCriteria({}))

    async def test_context_sent_to_the_provider_after_compacting_carries_the_goal(self) -> None:
        history, _, second = await compact_twice(LossySummarizer(BUDGET))
        context = assemble_pinned_block(history, second, block_from_seeds(), criteria_source())
        provider = FakeProvider([ProviderResponse(content="ok")])
        await provider.complete(context)
        sent = provider.received[0]
        assert sent[1].role is Role.SYSTEM
        assert sentinel_of("objetivo") in sent[1].content
        # Not shown here: that a real model answers the goal correctly (pending human task).

    def test_block_is_rebuilt_without_the_summary_when_resuming(self) -> None:
        history = build_long_session()
        block = block_from_seeds()
        resumed = assemble_pinned_block(history, CompactionState(), block, criteria_source())
        compacted = assemble_pinned_block(
            history, CompactionState("x", 40), block, criteria_source()
        )
        assert resumed[1] == compacted[1]


class TestProviderSummaryThatDropsTheGoal:
    """T015: a faithless provider summary (FakeProvider script) hurts design A but not design B."""

    async def test_goal_missing_from_the_summary_is_lost_in_a_but_kept_in_b(self) -> None:
        history = build_long_session()
        provider = FakeProvider(
            [ProviderResponse(content="Se revisaron varios archivos sin novedades.")]
        )
        state = await compact(
            history, CompactionState(), ProviderSummarizer(provider), keep_recent=KEEP_RECENT
        )
        context_a = assemble_summary_only(history, state)
        context_b = assemble_pinned_block(history, state, block_from_seeds(), criteria_source())
        assert not survival(context_a, ESSENTIAL_KEYS)["objetivo"]
        assert locate(context_b, sentinel_of("objetivo")) == "bloque"
        assert all(survival(context_b, ESSENTIAL_KEYS).values())
