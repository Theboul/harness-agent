"""Audit of the permission decisions (HU-05-05): what is written, how, and how it reads.

The events of the loop carry no arguments on purpose, so the audit completes them from the policy:
``ArgumentsTap`` wraps the outermost policy and remembers the redacted arguments of every call it
evaluates (it never changes the decision), and ``AuditRecorder`` (a subscriber of the bus) writes
the row when ``permission_decided`` arrives and completes it when ``approval_resolved`` arrives. It
relies on the decision being published right after it is evaluated, with no ``await`` in between,
which is how the loop, the verifier and the startup routine work.

Everything here is pure: the log, the redactor and the events come from outside. The audit fails
closed: a failure of the log is never caught here, so it reaches the bus and the tool does not run.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from harness_agent.core.entities import ToolCall
from harness_agent.core.events import Event
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy
from harness_agent.core.subagents.approval import requester_label

NO_DATA = "sin dato"
MAX_VALUE_CHARS = 200
MAX_ARGUMENT_CHARS = 2000
MAX_NAME_CHARS = 200
MAX_PENDING = 256
AUDIT_TABLE_ROWS = 30
ARGUMENT_COLUMN_CHARS = 50
VERIFICATION_PREFIX = "verificacion-"
STARTUP_PREFIX = "arranque-"
NO_AUDIT_ROWS = "Sin registros de auditoría para esa sesión."
AUDIT_READ_FAILED = "No se pudo leer la auditoría."
_TOTAL_MARK = "[recortado]"
_ORIGIN_NAMES = {"verificacion": "verificación", "arranque": "arranque", "agente": "agente"}


@dataclass(frozen=True)
class AuditEntry:
    """A decision as it is written: the arguments are already redacted and shortened."""

    session_id: str
    call_id: str
    tool: str
    arguments: str
    decision: str
    resolution: str
    reason: str | None
    origin: str
    decided_at: datetime


@dataclass(frozen=True)
class AuditRow:
    """A stored decision, as it is read (``parent_id`` tells whether its session is a child)."""

    session_id: str
    parent_id: str | None
    call_id: str
    tool: str
    arguments: str
    decision: str
    resolution: str
    reason: str | None
    action: str | None
    source: str | None
    origin: str
    decided_at: datetime
    resolved_at: datetime | None


class AuditLog(Protocol):
    """Where the audit is kept (a small port of its own, not one of ``core/interfaces/``)."""

    def record_decision(self, entry: AuditEntry) -> None:
        """Write one row."""

    def record_resolution(
        self,
        session_id: str,
        call_id: str,
        resolution: str,
        action: str | None,
        source: str | None,
        resolved_at: datetime,
    ) -> None:
        """Complete the latest row of that session and call (nothing happens without one)."""

    def rows(self, session_id: str, limit: int) -> list[AuditRow]:
        """The latest ``limit`` rows of the session and of its direct children, oldest first."""

    def count(self, session_id: str) -> int:
        """How many rows ``rows`` could return for the session."""


def _shorten(text: str) -> str:
    if len(text) <= MAX_VALUE_CHARS:
        return text
    return f"{text[:MAX_VALUE_CHARS]}[+{len(text) - MAX_VALUE_CHARS}]"


def _shortened(value: Any) -> Any:
    if isinstance(value, str):
        return _shorten(value)
    if isinstance(value, dict):
        return {
            _shorten(key) if isinstance(key, str) else key: _shortened(v)
            for key, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [_shortened(item) for item in value]
    return value


def prepare_arguments(arguments: Any, redact: Callable[[Any], Any]) -> str:
    """The arguments as the audit stores them; it never raises.

    They are redacted **first** (so a secret is never cut in half), then every text is shortened
    to ``MAX_VALUE_CHARS``, then written as ASCII JSON (hidden and direction characters come out
    escaped, so they are visible) and the whole is capped at ``MAX_ARGUMENT_CHARS``. If anything
    fails the result is ``NO_DATA``: the original is never written.
    """
    try:
        text = json.dumps(_shortened(redact(arguments)), ensure_ascii=True, sort_keys=True)
    except Exception:
        return NO_DATA
    if len(text) > MAX_ARGUMENT_CHARS:
        return text[: MAX_ARGUMENT_CHARS - len(_TOTAL_MARK)] + _TOTAL_MARK
    return text


def resolution_of(decision: str, resolved_as: str) -> str:
    """What a decision amounts to when it is published (a question is pending until answered)."""
    if decision == "allow":
        return "permitida"
    if decision == "deny":
        return "denegada"
    if decision == "ask":
        return "denegada" if resolved_as == "deny" else "pendiente"
    return NO_DATA


def origin_of(call_id: str) -> str:
    """Who asked, from the identifier of the call (the verifier and the startup have prefixes)."""
    if call_id.startswith(VERIFICATION_PREFIX):
        return "verificacion"
    if call_id.startswith(STARTUP_PREFIX):
        return "arranque"
    return "agente"


class ArgumentsTap(PermissionPolicy):
    """Wraps the outermost policy: returns its decision untouched and remembers the arguments.

    The arguments are kept redacted, by the identifier of the call, in a bounded map (the oldest
    entry goes first), until the recorder takes them.
    """

    def __init__(self, inner: PermissionPolicy, redact: Callable[[Any], Any]) -> None:
        self._inner = inner
        self._redact = redact
        self._pending: dict[str, str] = {}

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        self._pending.pop(call.id, None)
        self._pending[call.id] = prepare_arguments(call.arguments, self._redact)
        while len(self._pending) > MAX_PENDING:
            del self._pending[next(iter(self._pending))]
        return self._inner.evaluate(call)

    def take(self, call_id: str) -> str:
        """The remembered arguments of the call, once; ``NO_DATA`` if there are none."""
        return self._pending.pop(call_id, NO_DATA)


def _text(value: Any) -> str | None:
    """A text of the payload, or ``None`` when it is missing or not a text."""
    return value if isinstance(value, str) and value else None


class AuditRecorder:
    """Subscriber of the bus: one row per decision, completed when the question is answered.

    Args:
        log: Where the rows go. A failure of the log is not caught: it reaches the bus.
        tap: The wrapper of the policy that remembers the arguments.
        redact: Cleans every text that comes from the payload (names and identifiers).
    """

    def __init__(self, log: AuditLog, tap: ArgumentsTap, redact: Callable[[Any], Any]) -> None:
        self._log = log
        self._tap = tap
        self._redact = redact

    def _clean(self, value: Any) -> str:
        text = _text(value)
        if text is None:
            return NO_DATA
        return str(self._redact(text[:MAX_NAME_CHARS]))

    def on_decided(self, event: Event) -> None:
        """Write the row of a ``permission_decided`` event."""
        payload = event.payload
        raw_id = _text(payload.get("call_id"))
        decision = self._clean(payload.get("decision"))
        reason = _text(payload.get("reason"))
        self._log.record_decision(
            AuditEntry(
                session_id=event.session_id,
                call_id=self._clean(raw_id),
                tool=self._clean(payload.get("name")),
                arguments=NO_DATA if raw_id is None else self._tap.take(raw_id),
                decision=decision,
                resolution=resolution_of(decision, self._clean(payload.get("resolved_as"))),
                reason=None if reason is None else self._clean(reason),
                origin=origin_of(raw_id or ""),
                decided_at=event.timestamp,
            )
        )

    def on_resolved(self, event: Event) -> None:
        """Complete the row with the answer of an ``approval_resolved`` event.

        ``aprobada`` if the person approved, ``rechazada`` if they chose to reject, and ``fallida``
        when there is no action at all (the approver failed and the request was denied).
        """
        payload = event.payload
        action = _text(payload.get("action"))
        source = _text(payload.get("source"))
        if payload.get("approved") is True:
            resolution = "aprobada"
        elif action is None:
            resolution = "fallida"
        else:
            resolution = "rechazada"
        self._log.record_resolution(
            event.session_id,
            self._clean(payload.get("call_id")),
            resolution,
            None if action is None else self._clean(action),
            None if source is None else self._clean(source),
            event.timestamp,
        )


def _plain(text: str) -> str:
    """The text on one line, with what is not printable (control, hidden, direction) as ``?``."""
    return "".join(char if char.isprintable() else "?" for char in text)


def _argument_column(text: str) -> str:
    plain = _plain(text)
    if len(plain) <= ARGUMENT_COLUMN_CHARS:
        return plain
    return plain[: ARGUMENT_COLUMN_CHARS - 3] + "..."


def format_audit(rows: list[AuditRow], *, total: int, session_id: str) -> str:
    """The short table behind ``/auditoria``; it only returns text."""
    if not rows:
        return NO_AUDIT_ROWS
    shown = len(rows)
    if total > shown:
        counted = f"{shown} de {total} registros; últimos mostrados"
    else:
        counted = f"{total} registro" if total == 1 else f"{total} registros"
    cells = [("hora", "quién", "herramienta", "argumentos", "resolución")]
    for row in rows:
        asking = _ORIGIN_NAMES.get(row.origin, _plain(row.origin))
        if row.parent_id is not None:
            asking = requester_label(row.session_id)
        cells.append(
            (
                row.decided_at.strftime("%H:%M:%S"),
                _plain(asking),
                _plain(row.tool),
                _argument_column(row.arguments),
                _plain(row.resolution),
            )
        )
    widths = [max(len(line[column]) for line in cells) for column in range(4)]
    lines = [f"Auditoría de la sesión {_plain(session_id)} ({counted})."]
    for line in cells:
        padded = [line[column].ljust(widths[column]) for column in range(4)]
        lines.append("  ".join([*padded, line[4]]))
    return "\n".join(lines)
