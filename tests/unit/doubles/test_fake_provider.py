"""FakeProvider: scripted replay, validation, copies and call records (HU-00-03 / T003)."""

from __future__ import annotations

import asyncio
import inspect
import time

import pytest

from harness_agent.core import (
    Message,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    Role,
    TokenUsage,
    ToolCall,
    ToolDefinition,
)
from tests.doubles import FakeProvider, ScriptExhausted, run_bounded

USER = Message(role=Role.USER, content="hola")


def _text(content: str) -> ProviderResponse:
    return ProviderResponse(content=content)


def _call(call_id: str, name: str = "echo", **arguments: object) -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=dict(arguments))


class TestReplay:
    async def test_call_i_returns_step_i_in_order(self) -> None:
        script = [
            ProviderResponse(tool_calls=[_call("c1", text="uno")]),
            ProviderResponse(tool_calls=[_call("c2", text="dos")]),
            _text("listo"),
        ]
        provider = FakeProvider(script)

        results = [await provider.complete([USER]) for _ in range(3)]

        assert results == script

    async def test_text_and_tool_calls_in_one_step_are_returned_as_they_are(self) -> None:
        step = ProviderResponse(content="voy a leer", tool_calls=[_call("c1")])
        assert await FakeProvider([step]).complete([USER]) == step

    async def test_usage_is_returned_unchanged_and_none_when_absent(self) -> None:
        usage = TokenUsage(input_tokens=3, output_tokens=4)
        provider = FakeProvider([ProviderResponse(content="a", usage=usage), _text("b")])

        assert (await provider.complete([USER])).usage == usage
        assert (await provider.complete([USER])).usage is None

    async def test_tools_argument_is_optional(self) -> None:
        provider = FakeProvider([_text("a"), _text("b")])
        definition = ToolDefinition(name="echo", description="d", parameters={})

        await provider.complete([USER])
        await provider.complete([USER], [definition])

        assert provider.received_tools == [None, [definition]]

    def test_it_is_a_provider_with_the_same_complete_signature(self) -> None:
        provider = FakeProvider([_text("a")])
        assert isinstance(provider, Provider)
        assert inspect.iscoroutinefunction(provider.complete)
        assert inspect.signature(FakeProvider.complete) == inspect.signature(Provider.complete)


class TestCopies:
    async def test_the_returned_response_is_a_copy_of_the_script_step(self) -> None:
        script = [ProviderResponse(tool_calls=[_call("c1", payload={"a": 1})])]
        provider = FakeProvider(script)

        response = await provider.complete([USER])
        response.tool_calls.append(_call("c9"))
        response.tool_calls[0].arguments["payload"]["a"] = 99

        again = FakeProvider(script)
        replay = await again.complete([USER])
        assert [c.id for c in replay.tool_calls] == ["c1"]
        assert replay.tool_calls[0].arguments["payload"] == {"a": 1}

    async def test_mutating_the_original_script_after_building_has_no_effect(self) -> None:
        script = [_text("uno"), _text("dos")]
        provider = FakeProvider(script)

        script.pop()
        script[0].tool_calls.append(_call("zz"))

        assert (await provider.complete([USER])).content == "uno"
        assert (await provider.complete([USER])).content == "dos"
        assert provider.call_count == 2

    async def test_two_instances_of_the_same_script_do_not_share_state(self) -> None:
        script = [_text("uno"), _text("dos")]
        first, second = FakeProvider(script), FakeProvider(script)

        await first.complete([USER])
        await first.complete([USER])

        assert second.call_count == 0
        assert (await second.complete([USER])).content == "uno"

    async def test_received_messages_and_tools_are_copies(self) -> None:
        provider = FakeProvider([_text("a")])
        history = [USER]
        definition = ToolDefinition(name="echo", description="d", parameters={"k": {"v": 1}})
        tools = [definition]

        await provider.complete(history, tools)
        history.append(Message(role=Role.ASSISTANT, content="otro"))
        tools.clear()
        definition.parameters["k"]["v"] = 2

        assert provider.received == [[USER]]
        assert provider.received_tools is not None
        recorded = provider.received_tools[0]
        assert recorded is not None
        assert recorded[0].parameters == {"k": {"v": 1}}


class TestRecord:
    async def test_call_count_counts_each_call(self) -> None:
        provider = FakeProvider([_text("a"), _text("b")])
        assert provider.call_count == 0

        await provider.complete([USER])
        assert provider.call_count == 1
        await provider.complete([USER])
        assert provider.call_count == 2

    async def test_it_starts_not_exhausted_and_with_empty_records(self) -> None:
        provider = FakeProvider([_text("a")])
        assert provider.exhausted is False
        assert provider.received == []
        assert provider.received_tools == []


class TestToolCallIds:
    def test_a_repeated_id_in_the_whole_script_is_rejected_when_building(self) -> None:
        script = [
            ProviderResponse(tool_calls=[_call("c1")]),
            ProviderResponse(tool_calls=[_call("c1")]),
        ]
        with pytest.raises(ValueError, match=r"paso 1.*repite el id") as raised:
            FakeProvider(script)
        assert "c1" not in str(raised.value)  # the message does not echo the received value

    def test_a_repeated_id_inside_one_step_is_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"paso 0.*repite el id") as raised:
            FakeProvider([ProviderResponse(tool_calls=[_call("c1"), _call("c1")])])
        assert "c1" not in str(raised.value)

    def test_an_empty_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="sin id"):
            FakeProvider([ProviderResponse(tool_calls=[_call("")])])

    def test_the_message_names_the_step_index(self) -> None:
        script = [_text("a"), ProviderResponse(tool_calls=[_call("")])]
        with pytest.raises(ValueError, match="paso 1"):
            FakeProvider(script)

    def test_validation_messages_are_in_spanish(self) -> None:
        with pytest.raises(ValueError) as empty_script:
            FakeProvider([])
        with pytest.raises(ValueError) as bad_step:
            FakeProvider([None])  # type: ignore[list-item]

        for raised in (empty_script, bad_step):
            text = str(raised.value)
            assert "script" not in text.lower()
            assert "step" not in text.lower()


FAILURES = (QuotaExceeded, ProviderTimeout, ProviderUnavailable)


class TestFailureSteps:
    @pytest.mark.parametrize("error_type", FAILURES)
    async def test_each_canonical_failure_is_raised_with_its_exact_type(
        self, error_type: type[ProviderError]
    ) -> None:
        provider = FakeProvider([error_type("fallo simulado")])

        with pytest.raises(ProviderError) as raised:
            await provider.complete([USER])

        assert type(raised.value) is error_type
        assert str(raised.value) == "fallo simulado"

    @pytest.mark.parametrize("position", [0, 2, 4])
    async def test_a_failure_in_any_position_lets_the_earlier_steps_through(
        self, position: int
    ) -> None:
        script: list[ProviderResponse | ProviderError] = [_text(f"r{i}") for i in range(5)]
        script[position] = QuotaExceeded("cuota")
        provider = FakeProvider(script)

        for index in range(position):
            assert (await provider.complete([USER])).content == f"r{index}"
        with pytest.raises(QuotaExceeded):
            await provider.complete([USER])

    async def test_call_count_advances_on_a_failure_too(self) -> None:
        provider = FakeProvider([ProviderTimeout("t"), _text("a")])

        with pytest.raises(ProviderTimeout):
            await provider.complete([USER])
        assert provider.call_count == 1
        assert (await provider.complete([USER])).content == "a"
        assert provider.call_count == 2

    async def test_the_raised_error_is_a_copy_not_the_object_of_the_script(self) -> None:
        original = QuotaExceeded("cuota")
        first, second = FakeProvider([original]), FakeProvider([original])

        with pytest.raises(QuotaExceeded) as raised_first:
            await first.complete([USER])
        with pytest.raises(QuotaExceeded) as raised_second:
            await second.complete([USER])

        assert raised_first.value is not original
        assert raised_second.value is not original
        assert raised_first.value is not raised_second.value

    async def test_a_script_mixing_successes_and_failures_replays_the_same_way(self) -> None:
        script: list[ProviderResponse | ProviderError] = [
            _text("a"),
            ProviderUnavailable("caído"),
            _text("b"),
            QuotaExceeded("cuota"),
        ]

        async def play() -> list[str]:
            provider = FakeProvider(script)
            outcome: list[str] = []
            for _ in script:
                try:
                    outcome.append((await provider.complete([USER])).content)
                except ProviderError as error:
                    outcome.append(f"{type(error).__name__}:{error}")
            return outcome

        expected = ["a", "ProviderUnavailable:caído", "b", "QuotaExceeded:cuota"]
        assert await play() == expected
        assert await play() == expected

    @pytest.mark.parametrize("error_type", FAILURES)
    async def test_a_failure_returns_at_once_without_sleeping(
        self, error_type: type[ProviderError], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def forbidden(*_: object, **__: object) -> None:
            raise AssertionError("the provider must not wait")

        monkeypatch.setattr(asyncio, "sleep", forbidden)
        monkeypatch.setattr(time, "sleep", forbidden)
        provider = FakeProvider([error_type("t")])

        started = time.perf_counter()
        with pytest.raises(ProviderError):
            await provider.complete([USER])

        assert time.perf_counter() - started < 0.010

    async def test_failures_do_not_get_in_the_way_of_the_tool_call_id_rule(self) -> None:
        script: list[ProviderResponse | ProviderError] = [
            ProviderResponse(tool_calls=[_call("c1")]),
            QuotaExceeded("cuota"),
            ProviderResponse(tool_calls=[_call("c1")]),
        ]
        with pytest.raises(ValueError, match=r"paso 2.*repite el id"):
            FakeProvider(script)

    async def test_the_received_arguments_are_recorded_for_a_failed_call(self) -> None:
        provider = FakeProvider([QuotaExceeded("cuota")])

        with pytest.raises(QuotaExceeded):
            await provider.complete([USER])

        assert provider.received == [[USER]]


class TestExhaustedScript:
    async def test_the_call_after_the_last_step_raises_script_exhausted(self) -> None:
        provider = FakeProvider([_text("a"), _text("b")])

        await provider.complete([USER])
        await provider.complete([USER])
        assert provider.exhausted is False
        with pytest.raises(ScriptExhausted, match="llamada 3"):
            await provider.complete([USER])

        assert provider.exhausted is True
        assert provider.call_count == 3

    async def test_every_later_call_keeps_raising_and_nothing_is_invented(self) -> None:
        provider = FakeProvider([_text("a")])
        await provider.complete([USER])

        for _ in range(3):
            with pytest.raises(ScriptExhausted):
                await provider.complete([USER])

        assert provider.call_count == 4

    async def test_a_script_ending_in_a_failure_is_exhausted_after_it(self) -> None:
        provider = FakeProvider([QuotaExceeded("cuota")])
        with pytest.raises(QuotaExceeded):
            await provider.complete([USER])

        with pytest.raises(ScriptExhausted):
            await provider.complete([USER])

    async def test_script_exhausted_is_not_a_provider_error(self) -> None:
        provider = FakeProvider([_text("a")])
        await provider.complete([USER])

        with pytest.raises(ScriptExhausted) as raised:
            await provider.complete([USER])

        assert not isinstance(raised.value, ProviderError)


class TestInvalidScript:
    def test_an_empty_script_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="vacío"):
            FakeProvider([])

    @pytest.mark.parametrize(
        ("bad_step", "kind"),
        [
            (None, "NoneType"),
            ("texto", "str"),
            (42, "int"),
            (RuntimeError("otro"), "RuntimeError"),
            (ValueError("otro"), "ValueError"),
            (QuotaExceeded, "type"),
            ({"content": "x"}, "dict"),
        ],
        ids=["none", "str", "int", "runtime-error", "value-error", "error-class", "dict"],
    )
    def test_a_step_that_is_neither_a_response_nor_a_canonical_error_is_rejected(
        self, bad_step: object, kind: str
    ) -> None:
        script = [_text("ok"), bad_step]

        with pytest.raises(ValueError, match=rf"paso 1.*{kind}"):
            FakeProvider(script)  # type: ignore[arg-type]

    def test_a_base_provider_error_instance_is_accepted(self) -> None:
        FakeProvider([ProviderError("genérico")])

    def test_the_rejection_happens_when_building_not_when_calling(self) -> None:
        with pytest.raises(ValueError):
            FakeProvider([None])  # type: ignore[list-item]


class TestAsyncBehaviour:
    async def test_concurrent_calls_consume_distinct_steps_in_arrival_order(self) -> None:
        provider = FakeProvider([_text("a"), _text("b"), _text("c")])

        results = await asyncio.gather(*(provider.complete([USER]) for _ in range(3)))

        assert [r.content for r in results] == ["a", "b", "c"]
        assert provider.call_count == 3

    async def test_a_call_does_not_block_other_tasks(self) -> None:
        provider = FakeProvider([_text("a")])
        ticks: list[int] = []

        async def ticker() -> None:
            for n in range(3):
                ticks.append(n)
                await asyncio.sleep(0)

        await run_bounded(asyncio.gather(provider.complete([USER]), ticker()), timeout=2.0)

        assert ticks == [0, 1, 2]

    async def test_cancelling_between_calls_does_not_advance_the_count(self) -> None:
        provider = FakeProvider([_text("a"), _text("b")])
        await provider.complete([USER])

        async def waiter() -> None:
            await asyncio.Event().wait()
            await provider.complete([USER])

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert provider.call_count == 1
        assert (await provider.complete([USER])).content == "b"
