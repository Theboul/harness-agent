"""The traces of the calls (HU-10-01): the provider and the registry that measure, and the table.

Everything is faked: the provider, the tools, the clocks and the log. What a trace may hold is
checked by its fields (metadata only, D-09) and with sentinels that must never reach the log.
"""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from harness_agent.core import (
    NO_DATA,
    TRACE_TABLE_ROWS,
    TRACE_WARNING,
    Message,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    RiskLevel,
    Role,
    SecretRedactor,
    TokenUsage,
    Tool,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
    TraceRecord,
    TraceRow,
    TraceSink,
    TracingProvider,
    TracingRegistry,
    format_traces,
    requester_label,
    result_category,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
PREFIXED_KEY = "s" + "k-" + "a" * 24
START = datetime(2026, 11, 4, 10, 0, 0, tzinfo=timezone.utc)


class Clocks:
    """A wall clock and a monotonic clock that advance by hand (a call takes ``step`` seconds)."""

    def __init__(self, step: float = 0.25) -> None:
        self.step = step
        self.now = 0.0

    def wall(self) -> datetime:
        return START + timedelta(seconds=self.now)

    def monotonic(self) -> float:
        self.now += self.step
        return self.now


class MemoryTraceLog:
    def __init__(self) -> None:
        self.records: list[TraceRecord] = []
        self.fail = False

    def record(self, record: TraceRecord) -> None:
        if self.fail:
            raise RuntimeError(SENTINEL)
        self.records.append(record)

    def rows(self, session_id: str, limit: int) -> list[TraceRow]:
        return []

    def count(self, session_id: str) -> int:
        return 0


class Warnings:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, text: str) -> None:
        self.lines.append(text)


def plumbing() -> tuple[MemoryTraceLog, Warnings, TraceSink]:
    log, warnings = MemoryTraceLog(), Warnings()
    return log, warnings, TraceSink(log, warnings)


class ScriptedModel(Provider):
    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.received: list[tuple[list[Message], list[ToolDefinition] | None]] = []

    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        self.received.append((messages, tools))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        response: ProviderResponse = outcome
        return response


def traced_model(model: ScriptedModel, sink: TraceSink, clocks: Clocks) -> TracingProvider:
    return TracingProvider(
        model,
        sink,
        lambda: "s1",
        lambda: "fake/test",
        clock=clocks.wall,
        monotonic=clocks.monotonic,
        redact=SecretRedactor(known=[SENTINEL]).value,
    )


MESSAGES = [Message(Role.USER, "hola " + SENTINEL)]


# --- the provider -----------------------------------------------------------------------------


async def test_the_response_comes_back_untouched_and_the_call_leaves_one_trace() -> None:
    log, _, sink = plumbing()
    response = ProviderResponse("respuesta " + SENTINEL, usage=TokenUsage(120, 30))
    provider = traced_model(ScriptedModel(response), sink, Clocks())

    result = await provider.complete(MESSAGES, None)

    assert result is response
    assert log.records == [
        TraceRecord(
            session_id="s1",
            kind="modelo",
            name="fake/test",
            started_at=START,
            duration_ms=250,
            input_tokens=120,
            output_tokens=30,
            result="ok",
            size=len("respuesta " + SENTINEL),
        )
    ]


async def test_the_messages_and_the_tools_reach_the_provider_as_they_came() -> None:
    _, _, sink = plumbing()
    model = ScriptedModel(ProviderResponse("x"))
    tools = [ToolDefinition("t", "d")]

    await traced_model(model, sink, Clocks()).complete(MESSAGES, tools)

    assert model.received[0][0] is MESSAGES and model.received[0][1] is tools


async def test_without_usage_the_tokens_are_no_data_not_zero() -> None:
    log, _, sink = plumbing()

    await traced_model(ScriptedModel(ProviderResponse("x")), sink, Clocks()).complete(MESSAGES)

    assert (log.records[0].input_tokens, log.records[0].output_tokens) == (None, None)


async def test_a_real_zero_stays_a_zero() -> None:
    log, _, sink = plumbing()
    response = ProviderResponse("", usage=TokenUsage(0, 0))

    await traced_model(ScriptedModel(response), sink, Clocks()).complete(MESSAGES)

    assert (log.records[0].input_tokens, log.records[0].output_tokens) == (0, 0)


async def test_a_provider_error_is_traced_by_its_class_and_rises_unchanged() -> None:
    log, _, sink = plumbing()
    error = ProviderTimeout(SENTINEL)
    provider = traced_model(ScriptedModel(error), sink, Clocks())

    with pytest.raises(ProviderTimeout) as raised:
        await provider.complete(MESSAGES)

    assert raised.value is error
    record = log.records[0]
    assert (record.result, record.size, record.input_tokens) == ("ProviderTimeout", 0, None)
    assert SENTINEL not in repr(record)


async def test_an_error_that_is_not_the_providers_is_just_an_error() -> None:
    log, _, sink = plumbing()
    provider = traced_model(ScriptedModel(ValueError(SENTINEL)), sink, Clocks())

    with pytest.raises(ValueError):
        await provider.complete(MESSAGES)

    assert log.records[0].result == "error"


async def test_a_cancelled_call_leaves_a_cancelled_trace_and_the_cancellation_rises() -> None:
    log, _, sink = plumbing()

    class Hanging(Provider):
        async def complete(
            self, messages: list[Message], tools: list[ToolDefinition] | None = None
        ) -> ProviderResponse:
            await asyncio.Event().wait()
            raise AssertionError("never")

    provider = TracingProvider(
        Hanging(),
        sink,
        lambda: "s1",
        lambda: "fake/test",
        clock=Clocks().wall,
        monotonic=Clocks().monotonic,
        redact=SecretRedactor().value,
    )
    task = asyncio.ensure_future(provider.complete(MESSAGES))
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert [record.result for record in log.records] == ["cancelado"]


async def test_the_model_name_is_taken_when_the_call_ends_and_is_redacted() -> None:
    log, _, sink = plumbing()
    names = iter(["primero", PREFIXED_KEY])
    provider = TracingProvider(
        ScriptedModel(ProviderResponse("x")),
        sink,
        lambda: "s1",
        lambda: next(names),
        clock=Clocks().wall,
        monotonic=Clocks().monotonic,
        redact=SecretRedactor().value,
    )

    await provider.complete(MESSAGES)

    assert log.records[0].name == "primero"  # one reading per call, at the end
    assert PREFIXED_KEY not in repr(log.records)


async def test_the_session_is_read_when_the_call_ends() -> None:
    log, _, sink = plumbing()
    session = ["antes"]
    provider = TracingProvider(
        ScriptedModel(ProviderResponse("x")),
        sink,
        lambda: session[0],
        lambda: "fake/test",
        clock=Clocks().wall,
        monotonic=Clocks().monotonic,
        redact=SecretRedactor().value,
    )
    session[0] = "despues"

    await provider.complete(MESSAGES)

    assert log.records[0].session_id == "despues"


async def test_the_inner_provider_is_exposed_for_the_composition_and_the_tests() -> None:
    _, _, sink = plumbing()
    model = ScriptedModel()

    assert traced_model(model, sink, Clocks()).inner is model


async def test_a_failing_log_changes_nothing_and_warns_once_with_a_fixed_line() -> None:
    log, warnings, sink = plumbing()
    log.fail = True
    response = ProviderResponse("x")
    provider = traced_model(ScriptedModel(response, response, ProviderTimeout("t")), sink, Clocks())

    assert await provider.complete(MESSAGES) is response
    assert await provider.complete(MESSAGES) is response
    with pytest.raises(ProviderTimeout):
        await provider.complete(MESSAGES)

    assert warnings.lines == [TRACE_WARNING]
    assert SENTINEL not in TRACE_WARNING


async def test_a_clock_or_a_redactor_that_fails_is_a_failed_trace_not_a_failed_call() -> None:
    _, warnings, sink = plumbing()

    def broken(value: Any) -> Any:
        raise RuntimeError(SENTINEL)

    provider = TracingProvider(
        ScriptedModel(ProviderResponse("x")),
        sink,
        lambda: "s1",
        lambda: "fake/test",
        clock=Clocks().wall,
        monotonic=Clocks().monotonic,
        redact=broken,
    )

    assert (await provider.complete(MESSAGES)).content == "x"
    assert warnings.lines == [TRACE_WARNING]


async def test_odd_usage_values_are_no_data() -> None:
    log, _, sink = plumbing()
    odd = ProviderResponse("x", usage=TokenUsage(True, -1))

    await traced_model(ScriptedModel(odd), sink, Clocks()).complete(MESSAGES)

    assert (log.records[0].input_tokens, log.records[0].output_tokens) == (None, None)


async def test_the_duration_is_never_negative() -> None:
    log, _, sink = plumbing()
    clocks = Clocks(step=-1.0)

    await traced_model(ScriptedModel(ProviderResponse("x")), sink, clocks).complete(MESSAGES)

    assert log.records[0].duration_ms == 0


# --- the registry and its tools ----------------------------------------------------------------


class EchoTool(Tool):
    def __init__(self, name: str = "eco", outcome: Any = None) -> None:
        self._name = name
        self._outcome = outcome
        self.received: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "describe"

    @property
    def schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    @property
    def risk(self) -> RiskLevel:
        return RiskLevel.HIGH

    async def run(self, args: dict[str, Any]) -> ToolResult:
        self.received.append(args)
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        if self._outcome is not None:
            outcome: ToolResult = self._outcome
            return outcome
        return ToolResult("c1", "salida " + SENTINEL, False)


class FakeRegistry(ToolRegistry):
    def __init__(self, *tools: Tool) -> None:
        self.tools = {tool.name: tool for tool in tools}
        self.calls: list[str] = []

    def register(self, tool: Tool) -> None:
        self.calls.append("register")
        self.tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self.tools.get(name)

    def list(self) -> list[Tool]:
        self.calls.append("list")
        return list(self.tools.values())

    def validate_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("validate")
        return {**args, "validado": True}


def traced_registry(
    registry: ToolRegistry, sink: TraceSink, clocks: Clocks, session: str = "s1"
) -> TracingRegistry:
    return TracingRegistry(
        registry,
        sink,
        lambda: session,
        clock=clocks.wall,
        monotonic=clocks.monotonic,
        redact=SecretRedactor(known=[SENTINEL]).value,
    )


async def test_a_measured_tool_looks_like_the_real_one_and_returns_the_same_result() -> None:
    log, _, sink = plumbing()
    real = EchoTool()
    registry = traced_registry(FakeRegistry(real), sink, Clocks())

    tool = registry.get("eco")

    assert tool is not None and tool is not real
    assert (tool.name, tool.description, tool.schema, tool.risk) == (
        "eco",
        "describe",
        {"type": "object", "properties": {}},
        RiskLevel.HIGH,
    )
    result = await tool.run({"a": 1})
    assert result == ToolResult("c1", "salida " + SENTINEL, False)
    assert real.received == [{"a": 1}]
    assert log.records == [
        TraceRecord(
            session_id="s1",
            kind="herramienta",
            name="eco",
            started_at=START,
            duration_ms=250,
            input_tokens=None,
            output_tokens=None,
            result="ok",
            size=len("salida " + SENTINEL),
        )
    ]


async def test_an_unknown_tool_is_none_and_the_other_calls_go_to_the_registry_inside() -> None:
    _, _, sink = plumbing()
    inner = FakeRegistry(EchoTool())
    registry = traced_registry(inner, sink, Clocks())

    assert registry.get("nada") is None
    registry.register(EchoTool("otra"))
    assert {tool.name for tool in registry.list()} == {"eco", "otra"}
    assert registry.validate_args("eco", {"x": 1}) == {"x": 1, "validado": True}
    assert inner.calls == ["register", "list", "validate"]


@pytest.mark.parametrize(
    ("content", "category"),
    [
        ("[fuera_del_area] No se puede " + SENTINEL, "fuera_del_area"),
        ("sin etiqueta " + SENTINEL, "error"),
        ("[Con Mayusculas] x", "error"),
        ("[" + "a" * 41 + "] x", "error"),
        ("[] x", "error"),
    ],
)
async def test_an_error_result_is_traced_by_its_label_or_as_an_error(
    content: str, category: str
) -> None:
    log, _, sink = plumbing()
    tool = traced_registry(
        FakeRegistry(EchoTool(outcome=ToolResult("c1", content, True))), sink, Clocks()
    ).get("eco")
    assert tool is not None

    result = await tool.run({})

    assert result.is_error and result.content == content
    assert log.records[0].result == category
    assert log.records[0].size == len(content)  # the size of an error result is kept too
    assert SENTINEL not in repr(log.records)


async def test_an_exception_of_the_tool_is_traced_by_its_class_and_rises_unchanged() -> None:
    log, _, sink = plumbing()
    error = KeyError(SENTINEL)
    tool = traced_registry(FakeRegistry(EchoTool(outcome=error)), sink, Clocks()).get("eco")
    assert tool is not None

    with pytest.raises(KeyError) as raised:
        await tool.run({})

    assert raised.value is error
    assert (log.records[0].result, log.records[0].size) == ("KeyError", 0)


async def test_a_result_that_is_not_a_result_is_an_error_with_no_size() -> None:
    log, _, sink = plumbing()
    tool = traced_registry(FakeRegistry(EchoTool(outcome="no es un resultado")), sink, Clocks())
    measured = tool.get("eco")
    assert measured is not None

    outcome: object = await measured.run({})

    assert outcome == "no es un resultado"

    assert (log.records[0].result, log.records[0].size) == ("error", 0)


async def test_a_cancelled_tool_leaves_a_cancelled_trace_and_the_cancellation_rises() -> None:
    log, _, sink = plumbing()

    class Hanging(EchoTool):
        async def run(self, args: dict[str, Any]) -> ToolResult:
            await asyncio.Event().wait()
            raise AssertionError("never")

    tool = traced_registry(FakeRegistry(Hanging()), sink, Clocks()).get("eco")
    assert tool is not None
    task = asyncio.ensure_future(tool.run({}))
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert [record.result for record in log.records] == ["cancelado"]


async def test_the_session_of_the_registry_is_the_one_it_was_given() -> None:
    log, _, sink = plumbing()
    tool = traced_registry(FakeRegistry(EchoTool()), sink, Clocks(), session="hija").get("eco")
    assert tool is not None

    await tool.run({})

    assert log.records[0].session_id == "hija"


async def test_a_failing_log_does_not_change_the_result_of_a_tool() -> None:
    log, warnings, sink = plumbing()
    log.fail = True
    tool = traced_registry(FakeRegistry(EchoTool()), sink, Clocks()).get("eco")
    assert tool is not None

    result = await tool.run({})

    assert result.content == "salida " + SENTINEL
    assert warnings.lines == [TRACE_WARNING]


# --- what a trace holds -----------------------------------------------------------------------


def test_a_trace_holds_only_metadata_and_no_free_text_field_but_the_name_and_the_result() -> None:
    fields = {field.name: field.type for field in dataclasses.fields(TraceRecord)}

    assert list(fields) == [
        "session_id",
        "kind",
        "name",
        "started_at",
        "duration_ms",
        "input_tokens",
        "output_tokens",
        "result",
        "size",
    ]
    assert [name for name, kind in fields.items() if kind == "str"] == [
        "session_id",
        "kind",
        "name",
        "result",
    ]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ProviderTimeout("x"), "ProviderTimeout"),
        (ProviderError("x"), "ProviderError"),
        (ValueError("x"), "ValueError"),
    ],
)
def test_the_category_of_an_error_is_the_name_of_its_class(error: Exception, expected: str) -> None:
    assert result_category(error) == expected


def test_a_class_name_that_is_not_a_plain_identifier_is_just_an_error() -> None:
    odd = type("N" + "x" * 80, (Exception,), {})

    assert result_category(odd()) == "error"


# --- the table --------------------------------------------------------------------------------


def trace_row(**overrides: Any) -> TraceRow:
    values: dict[str, Any] = {
        "session_id": "s1",
        "parent_id": None,
        "kind": "modelo",
        "name": "fake/test",
        "started_at": START,
        "duration_ms": 1250,
        "input_tokens": 100,
        "output_tokens": 20,
        "result": "ok",
        "size": 40,
    }
    return TraceRow(**{**values, **overrides})


def test_the_table_has_a_header_one_line_per_trace_and_the_data_of_each_call() -> None:
    text = format_traces([trace_row()], total=1, session_id="s1")

    lines = text.splitlines()
    assert lines[0] == "Trazas de la sesión s1 (1 llamada)."
    for column in ("hora", "tipo", "nombre", "duración", "tokens", "resultado"):
        assert column in lines[1]
    assert "10:00:00" in lines[2] and "modelo" in lines[2] and "fake/test" in lines[2]
    assert "1250 ms" in lines[2] and "100/20" in lines[2] and lines[2].rstrip().endswith("ok")
    assert len(lines) == 3


def test_missing_tokens_read_no_data_and_a_zero_reads_zero() -> None:
    rows = [
        trace_row(input_tokens=None, output_tokens=None),
        trace_row(input_tokens=0, output_tokens=0),
        trace_row(input_tokens=5, output_tokens=None),
    ]

    lines = format_traces(rows, total=3, session_id="s1").splitlines()[2:]

    assert NO_DATA in lines[0] and "0/0" in lines[1] and NO_DATA in lines[2]


def test_without_rows_it_says_so_in_one_fixed_line() -> None:
    assert format_traces([], total=0, session_id="s1") == "Sin trazas para esa sesión."


def test_more_rows_than_the_table_holds_says_how_many_are_shown() -> None:
    rows = [trace_row() for _ in range(TRACE_TABLE_ROWS)]

    text = format_traces(rows, total=45, session_id="s1")

    assert text.splitlines()[0] == (
        f"Trazas de la sesión s1 ({TRACE_TABLE_ROWS} de 45 llamadas; últimas mostradas)."
    )


def test_a_child_session_shows_who_it_is_and_the_own_session_shows_a_dash() -> None:
    rows = [trace_row(), trace_row(session_id="hija-0123456789", parent_id="s1")]

    lines = format_traces(rows, total=2, session_id="s1").splitlines()

    assert "sesión" in lines[1]
    assert requester_label("hija-0123456789") in lines[3]
    assert " - " in lines[2]


def test_a_long_name_is_shortened_in_the_table() -> None:
    text = format_traces([trace_row(name="m" * 100)], total=1, session_id="s1")

    assert "m" * 50 not in text and "..." in text.splitlines()[2]


def test_hidden_characters_in_a_stored_field_never_reach_the_screen() -> None:
    hostile = trace_row(name="x" + chr(0x202E) + "y\nz", result="a\tb")

    text = format_traces([hostile], total=1, session_id="s1")

    assert chr(0x202E) not in text
    assert len(text.splitlines()) == 3
