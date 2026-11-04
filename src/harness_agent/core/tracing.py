"""Structured traces of every call to the model and to a tool (HU-10-01).

Two wrappers measure what the loop does, without the loop knowing: ``TracingProvider`` implements
``Provider`` and ``TracingRegistry`` implements ``ToolRegistry`` (its tools are measured copies with
the same name, schema and risk). A trace holds **metadata only** (kind, name, start, duration,
tokens, result and the size of the content in characters); never a message, an argument or the text
of a result. The tokens come from ``ProviderResponse.usage`` and are ``None`` when there is none:
a number is never invented.

Writing a trace never changes the call: every failure of the log is caught here (``Exception``
only) and becomes one fixed warning per run. The cancellation is never caught: a ``finally`` notes
a cancelled call and lets it rise. The clocks, the redactor and the log come from outside.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from harness_agent.core.audit import NO_DATA
from harness_agent.core.entities import Message, ToolResult
from harness_agent.core.interfaces.provider import (
    Provider,
    ProviderError,
    ProviderResponse,
    ToolDefinition,
)
from harness_agent.core.interfaces.tool import RiskLevel, Tool, ToolRegistry
from harness_agent.core.subagents.approval import requester_label

TRACE_TABLE_ROWS = 30
NAME_COLUMN_CHARS = 40
TRACE_WARNING = "No se pudo guardar una traza; la sesión continúa sin ella."
NO_TRACE_ROWS = "Sin trazas para esa sesión."
TRACE_READ_FAILED = "No se pudieron leer las trazas."
TRACES_OFF = "Las trazas están apagadas en la configuración."
_MAX_NAME_CHARS = 200
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,59}")
_LABEL = re.compile(r"\[([a-z_]{1,40})\]")


@dataclass(frozen=True)
class TraceRecord:
    """One call, as it is written. ``None`` tokens mean the provider gave no usage."""

    session_id: str
    kind: str
    name: str
    started_at: datetime
    duration_ms: int
    input_tokens: int | None
    output_tokens: int | None
    result: str
    size: int


@dataclass(frozen=True)
class TraceRow(TraceRecord):
    """A stored trace, as it is read (``parent_id`` tells whether its session is a child)."""

    parent_id: str | None


class TraceLog(Protocol):
    """Where the traces are kept (a small port of its own, not one of ``core/interfaces/``)."""

    def record(self, record: TraceRecord) -> None:
        """Write one trace."""

    def rows(self, session_id: str, limit: int) -> list[TraceRow]:
        """The latest ``limit`` traces of the session and of its direct children, oldest first."""

    def count(self, session_id: str) -> int:
        """How many traces ``rows`` could return for the session."""


class TraceSink:
    """Writes traces and never fails: a failure becomes one fixed warning per run."""

    def __init__(self, log: TraceLog, warn: Callable[[str], None]) -> None:
        self._log = log
        self._warn = warn
        self._warned = False

    def capture(self, build: Callable[[], TraceRecord]) -> None:
        """Build the trace and write it; any ordinary failure only warns (once)."""
        try:
            self._log.record(build())
        except Exception:
            if not self._warned:
                self._warned = True
                self._warn(TRACE_WARNING)


def result_category(error: Exception) -> str:
    """The category of a failed call: the name of the class of the error (never its text)."""
    name = type(error).__name__
    return name if _IDENTIFIER.fullmatch(name) else "error"


def _tokens(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _milliseconds(begin: float, end: float) -> int:
    return max(0, round((end - begin) * 1000))


def _bounded(text: str) -> str:
    return text[:_MAX_NAME_CHARS]


class TracingProvider(Provider):
    """A ``Provider`` that measures each call and delegates it untouched.

    Args:
        inner: The provider that does the call (the whole chain of retries and failover).
        sink: Where the traces go.
        session: The session of the trace, read when the call ends.
        model: The active model, read when the call ends (a failover may have changed it).
        clock: Wall clock (UTC) for the start of the call.
        monotonic: Monotonic clock for the duration.
        redact: Cleans every text of the trace (the name of the model).
    """

    def __init__(
        self,
        inner: Provider,
        sink: TraceSink,
        session: Callable[[], str],
        model: Callable[[], str],
        *,
        clock: Callable[[], datetime],
        monotonic: Callable[[], float],
        redact: Callable[[Any], Any],
    ) -> None:
        self._inner = inner
        self._sink = sink
        self._session = session
        self._model = model
        self._clock = clock
        self._monotonic = monotonic
        self._redact = redact

    @property
    def inner(self) -> Provider:
        """The provider this one wraps."""
        return self._inner

    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        started = self._clock()
        begin = self._monotonic()
        result = "cancelado"
        response: ProviderResponse | None = None
        try:
            response = await self._inner.complete(messages, tools)
            result = "ok"
            return response
        except ProviderError as error:
            result = result_category(error)
            raise
        except Exception:
            result = "error"
            raise
        finally:
            self._sink.capture(lambda: self._trace(started, begin, result, response))

    def _trace(
        self, started: datetime, begin: float, result: str, response: ProviderResponse | None
    ) -> TraceRecord:
        usage = None if response is None else response.usage
        content = None if response is None else response.content
        return TraceRecord(
            session_id=self._session(),
            kind="modelo",
            name=_bounded(str(self._redact(self._model()))),
            started_at=started,
            duration_ms=_milliseconds(begin, self._monotonic()),
            input_tokens=None if usage is None else _tokens(usage.input_tokens),
            output_tokens=None if usage is None else _tokens(usage.output_tokens),
            result=result,
            size=len(content) if isinstance(content, str) else 0,
        )


def _tool_outcome(outcome: Any) -> tuple[str, int]:
    """The result category and the size in characters of what a tool returned."""
    if not isinstance(outcome, ToolResult) or not isinstance(outcome.content, str):
        return "error", 0
    if not outcome.is_error:
        return "ok", len(outcome.content)
    label = _LABEL.match(outcome.content)
    return (label.group(1) if label else "error"), len(outcome.content)


class _TracedTool(Tool):
    """A tool that measures its own ``run``; everything else is the tool inside."""

    def __init__(
        self,
        inner: Tool,
        sink: TraceSink,
        session: Callable[[], str],
        clock: Callable[[], datetime],
        monotonic: Callable[[], float],
        redact: Callable[[Any], Any],
    ) -> None:
        self._inner = inner
        self._sink = sink
        self._session = session
        self._clock = clock
        self._monotonic = monotonic
        self._redact = redact

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def description(self) -> str:
        return self._inner.description

    @property
    def schema(self) -> dict[str, Any]:
        return self._inner.schema

    @property
    def risk(self) -> RiskLevel:
        return self._inner.risk

    async def run(self, args: dict[str, Any]) -> ToolResult:
        started = self._clock()
        begin = self._monotonic()
        result, size = "cancelado", 0
        try:
            outcome = await self._inner.run(args)
            result, size = _tool_outcome(outcome)
            return outcome
        except Exception as error:
            result = result_category(error)
            raise
        finally:
            self._sink.capture(lambda: self._trace(started, begin, result, size))

    def _trace(self, started: datetime, begin: float, result: str, size: int) -> TraceRecord:
        return TraceRecord(
            session_id=self._session(),
            kind="herramienta",
            name=_bounded(str(self._redact(self._inner.name))),
            started_at=started,
            duration_ms=_milliseconds(begin, self._monotonic()),
            input_tokens=None,
            output_tokens=None,
            result=result,
            size=size,
        )


class TracingRegistry(ToolRegistry):
    """A ``ToolRegistry`` whose tools are measured; registering and listing go to the one inside."""

    def __init__(
        self,
        inner: ToolRegistry,
        sink: TraceSink,
        session: Callable[[], str],
        *,
        clock: Callable[[], datetime],
        monotonic: Callable[[], float],
        redact: Callable[[Any], Any],
    ) -> None:
        self._inner = inner
        self._sink = sink
        self._session = session
        self._clock = clock
        self._monotonic = monotonic
        self._redact = redact

    def register(self, tool: Tool) -> None:
        self._inner.register(tool)

    def get(self, name: str) -> Tool | None:
        tool = self._inner.get(name)
        if tool is None:
            return None
        return _TracedTool(
            tool, self._sink, self._session, self._clock, self._monotonic, self._redact
        )

    def list(self) -> list[Tool]:
        return self._inner.list()

    def validate_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return self._inner.validate_args(name, args)


def _plain(text: str) -> str:
    """The text on one line, with what is not printable (control, hidden, direction) as ``?``."""
    return "".join(char if char.isprintable() else "?" for char in text)


def _tokens_column(row: TraceRow) -> str:
    if row.input_tokens is None or row.output_tokens is None:
        return NO_DATA
    return f"{row.input_tokens}/{row.output_tokens}"


def format_traces(rows: list[TraceRow], *, total: int, session_id: str) -> str:
    """The short table behind ``/trazas``; it only returns text."""
    if not rows:
        return NO_TRACE_ROWS
    shown = len(rows)
    if total > shown:
        counted = f"{shown} de {total} llamadas; últimas mostradas"
    else:
        counted = f"{total} llamada" if total == 1 else f"{total} llamadas"
    cells = [("hora", "sesión", "tipo", "nombre", "duración", "tokens", "resultado")]
    for row in rows:
        name = _plain(row.name)
        if len(name) > NAME_COLUMN_CHARS:
            name = name[: NAME_COLUMN_CHARS - 3] + "..."
        cells.append(
            (
                row.started_at.strftime("%H:%M:%S"),
                "-" if row.parent_id is None else _plain(requester_label(row.session_id)),
                _plain(row.kind),
                name,
                f"{row.duration_ms} ms",
                _tokens_column(row),
                _plain(row.result),
            )
        )
    widths = [max(len(line[column]) for line in cells) for column in range(6)]
    lines = [f"Trazas de la sesión {_plain(session_id)} ({counted})."]
    for line in cells:
        padded = [line[column].ljust(widths[column]) for column in range(6)]
        lines.append("  ".join([*padded, line[6]]))
    return "\n".join(lines)
