"""Basic agentic loop for HARNESS (HU-01-01).

This module materializes the ``core/agent`` subsystem named in the project constitution
(Area A, "Nucleo"): it lives in ``core/loop.py`` per the agreed folder tree. It depends only
on the standard library and on existing ``harness_agent.core`` contracts (no adapters, no
CLI, no provider SDKs) and never writes to the console: every relevant fact leaves through
the injected ``EventBus``.

One call to ``AgentLoop.run_turn`` runs one turn: reason -> act -> observe, until the
provider answers without tool calls.
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Any

from harness_agent.core.entities import Message, Role, ToolCall, ToolResult
from harness_agent.core.events import Event, EventType
from harness_agent.core.interfaces.event_bus import EventBus
from harness_agent.core.interfaces.provider import Provider, ProviderResponse, ToolDefinition
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy
from harness_agent.core.interfaces.tool import Tool, ToolRegistry

MAX_MESSAGE_CHARS = 500


class TurnStatus(str, Enum):
    """Terminal status of a turn that did not end in an exception."""

    COMPLETED = "completed"
    PROVIDER_FAILED = "provider_failed"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"


@dataclass(frozen=True)
class TurnResult:
    """Outcome of one turn.

    Attributes:
        status: Terminal status of the turn.
        final_response: Final assistant text (may be empty); only set when COMPLETED.
        history: Immutable snapshot of the history at the end of the turn.
        error: Short description of the failure; only set on failures.
    """

    status: TurnStatus
    final_response: str | None
    history: tuple[Message, ...]
    error: str | None = None


class MissingDependencyError(ValueError):
    """A required collaborator was not provided; the loop fails closed before acting."""


class InvalidHistoryError(ValueError):
    """The initial history violates the canonical rules; nothing was added or published."""


@dataclass(frozen=True)
class _Outcome:
    """Result of processing one tool call, before it is appended to the history."""

    result: ToolResult
    category: str
    external: bool


@dataclass
class _Progress:
    """Where the turn currently is, so a cancellation can report its phase (FR-026)."""

    phase: str = "provider_call"
    call_id: str | None = None


@dataclass(frozen=True)
class _Verdict:
    """What the policy decided and, unless ALLOW, the structured rejection to return."""

    decision: str
    resolved_as: str
    reason: str | None
    rejection: _Outcome | None


def _rejection(call: ToolCall, category: str, content: str) -> _Outcome:
    """Build a loop-authored rejection: structured error, not external content."""
    return _Outcome(ToolResult(call_id=call.id, content=content, is_error=True), category, False)


def _bounded(text: str) -> str:
    """Bound free text placed in model-facing results and event payloads."""
    return text if len(text) <= MAX_MESSAGE_CHARS else text[: MAX_MESSAGE_CHARS - 3] + "..."


class AgentLoop:
    """Runs agentic turns against injected collaborators (dependency injection)."""

    def __init__(
        self,
        provider: Provider,
        registry: ToolRegistry,
        policy: PermissionPolicy,
        bus: EventBus,
    ) -> None:
        for name, collaborator in (
            ("provider", provider),
            ("registry", registry),
            ("policy", policy),
            ("bus", bus),
        ):
            if collaborator is None:
                raise MissingDependencyError(
                    f"Required collaborator '{name}' was not provided; refusing to run."
                )
        self._provider = provider
        self._registry = registry
        self._policy = policy
        self._bus = bus

    async def run_turn(
        self,
        *,
        session_id: str,
        task: str,
        history: list[Message],
    ) -> TurnResult:
        """Run one turn for ``task``, appending new messages to the caller-owned ``history``.

        Returns a ``TurnResult`` for completed turns and provider failures. Everything else
        propagates: ``InvalidHistoryError``/``MissingDependencyError`` before any effect, any
        exception raised by ``EventBus.emit`` (Q4) and ``asyncio.CancelledError``.
        """
        progress = _Progress()
        try:
            return await self._run(session_id, task, history, progress)
        except asyncio.CancelledError as cancelled:
            self._publish_interruption(session_id, progress, cancelled)
            raise

    def _publish_interruption(
        self, session_id: str, progress: _Progress, cancelled: asyncio.CancelledError
    ) -> None:
        """Publish INTERRUPTED once; the cancellation prevails over a failing publication (R-08).

        If the bus fails here, only that failure is caught and its diagnostic is attached to
        the original ``CancelledError`` as a note (``__context__`` is not relied upon). The
        caller re-raises the original cancellation; nothing is retried or converted.
        """
        try:
            self._emit(
                session_id,
                EventType.INTERRUPTED,
                _interrupted_payload(progress.phase, progress.call_id),
            )
        except Exception as bus_error:
            cancelled.add_note(
                "INTERRUPTED could not be published: "
                f"{type(bus_error).__name__}: {_bounded(str(bus_error))}"
            )

    async def _run(
        self,
        session_id: str,
        task: str,
        history: list[Message],
        progress: _Progress,
    ) -> TurnResult:
        self._check_history(history)
        history.append(Message(Role.USER, task))
        self._emit(session_id, EventType.USER_MESSAGE, _user_message_payload(task))
        while True:
            progress.phase, progress.call_id = "provider_call", None
            # Built before the try: a registry/tool-declaration failure is structural, not a
            # provider failure (T033). It propagates; the provider is not queried and no
            # PROVIDER_ERROR is published.
            definitions = self._tool_definitions()
            try:
                response = await self._provider.complete(copy.deepcopy(history), definitions)
            except Exception as exc:
                # Published while handling the provider error so a failing bus chains to it.
                self._emit(
                    session_id,
                    EventType.PROVIDER_ERROR,
                    _provider_error_payload("provider_exception", type(exc).__name__, str(exc)),
                )
                return TurnResult(
                    TurnStatus.PROVIDER_FAILED,
                    None,
                    tuple(history),
                    f"{type(exc).__name__}: {_bounded(str(exc))}",
                )
            invalid = self._invalid_response_reason(response, history)
            if invalid is not None:
                self._emit(
                    session_id,
                    EventType.PROVIDER_ERROR,
                    _provider_error_payload("invalid_response", "InvalidProviderResponse", invalid),
                )
                return TurnResult(
                    TurnStatus.INVALID_PROVIDER_RESPONSE, None, tuple(history), invalid
                )
            # Own copies: the provider keeps no live reference to the arguments recorded in
            # the caller's history (T034).
            calls = tuple(copy.deepcopy(response.tool_calls))
            history.append(Message(Role.ASSISTANT, response.content, calls, usage=response.usage))
            if response.content:
                self._emit(
                    session_id,
                    EventType.ASSISTANT_MESSAGE,
                    _assistant_message_payload(response.content, len(calls), not calls),
                )
            if not calls:
                return TurnResult(TurnStatus.COMPLETED, response.content, tuple(history))
            for call in calls:
                outcome = await self._process_call(session_id, call, progress)
                history.append(
                    Message(
                        Role.TOOL,
                        outcome.result.content,
                        tool_result=outcome.result,
                        is_external=outcome.external,
                    )
                )
                # Published after the TOOL message is in the history: if emit fails the
                # executed call is neither repeated nor lost (Q4).
                self._emit(
                    session_id,
                    EventType.TOOL_FINISHED,
                    _tool_finished_payload(call, outcome.result.is_error, outcome.category),
                )

    # ----------------------------------------------------------------- history

    @staticmethod
    def _check_history(history: list[Message]) -> None:
        """Minimal structural precondition on the caller's history (FR-020, D-PLAN-05).

        It mirrors the canonical rules of HU-07-01 without importing the adapters: SYSTEM
        messages only as a contiguous prefix, non-empty and unique tool call ids, and every
        group of tool calls fully answered (in any order) before anything else follows.
        A history left mid-calls by a cancellation or a failed publication is rejected here,
        before anything is added or published.
        """
        pending: set[str] = set()
        seen: set[str] = set()
        for position, message in enumerate(history):
            where = f"history[{position}] ({message.role.value})"
            if (
                message.role is Role.SYSTEM
                and position > 0
                and history[position - 1].role is not Role.SYSTEM
            ):
                raise InvalidHistoryError(f"{where}: SYSTEM is only valid as a contiguous prefix.")
            if pending and message.role is not Role.TOOL:
                raise InvalidHistoryError(
                    f"{where}: tool calls {sorted(pending)} are still waiting for results."
                )
            if message.tool_calls and message.role is not Role.ASSISTANT:
                raise InvalidHistoryError(f"{where}: tool_calls are only valid on ASSISTANT.")
            if message.tool_result is not None and message.role is not Role.TOOL:
                raise InvalidHistoryError(f"{where}: tool_result is only valid on TOOL.")
            if message.role is Role.TOOL:
                if message.tool_result is None:
                    raise InvalidHistoryError(f"{where}: a TOOL message needs a tool_result.")
                if message.tool_result.call_id not in pending:
                    raise InvalidHistoryError(
                        f"{where}: result for unknown or already answered call "
                        f"'{message.tool_result.call_id}'."
                    )
                pending.discard(message.tool_result.call_id)
            for tool_call in message.tool_calls:
                if not tool_call.id or tool_call.id in seen:
                    raise InvalidHistoryError(
                        f"{where}: tool call id '{tool_call.id}' is empty or repeated."
                    )
                seen.add(tool_call.id)
                pending.add(tool_call.id)
        if pending:
            raise InvalidHistoryError(
                f"history ends with tool calls {sorted(pending)} that have no result."
            )

    # ------------------------------------------------------------ provider side

    def _tool_definitions(self) -> list[ToolDefinition]:
        """Recompute the tool declarations from the registry on every query (FR-002)."""
        return [
            ToolDefinition(name=tool.name, description=tool.description, parameters=tool.schema)
            for tool in self._registry.list()
        ]

    @staticmethod
    def _invalid_response_reason(response: object, history: list[Message]) -> str | None:
        """Return why a provider response is unusable, or None when it is valid (FR-024).

        Tool call ids must be non-empty and unique within the response and with respect to
        the calls already in the history (the uniqueness rule of the canonical validation
        of HU-07-01, D-02 section 4.7).
        """
        if not isinstance(response, ProviderResponse):
            return f"Provider returned {type(response).__name__}, not a ProviderResponse."
        seen = {call.id for message in history for call in message.tool_calls}
        for call in response.tool_calls:
            if not isinstance(call, ToolCall):
                return f"Provider returned a tool call of type {type(call).__name__}."
            if not call.id:
                return "Provider returned a tool call with an empty id."
            if call.id in seen:
                return f"Provider returned a duplicate tool call id '{call.id}'."
            seen.add(call.id)
        return None

    # -------------------------------------------------------------- tool pipeline

    def _lookup(self, name: str) -> Tool | None:
        try:
            return self._registry.get(name)
        except Exception:
            return None

    async def _process_call(self, session_id: str, call: ToolCall, progress: _Progress) -> _Outcome:
        """Resolve, validate, authorize and execute one call (R-07), in that order."""
        self._emit(session_id, EventType.TOOL_REQUESTED, _tool_requested_payload(call))
        tool = self._lookup(call.name)
        if tool is None:
            return _rejection(
                call, "unknown_tool", f"[unknown_tool] Tool '{call.name}' is not registered."
            )
        try:
            validated = self._registry.validate_args(call.name, copy.deepcopy(call.arguments))
            if not isinstance(validated, dict):
                raise TypeError("validate_args did not return a dict")
            effective = copy.deepcopy(validated)
        except Exception as exc:
            return _rejection(
                call,
                "invalid_arguments",
                f"[invalid_arguments] Arguments for tool '{call.name}' were rejected: "
                f"{_bounded(str(exc))}",
            )
        evaluated_call = dataclasses.replace(call, arguments=copy.deepcopy(effective))
        verdict = self._decide(call, evaluated_call)
        # Published before any execution: if emit fails the tool does not run (Q4).
        self._emit(
            session_id,
            EventType.PERMISSION_DECIDED,
            _permission_decided_payload(
                call, verdict.decision, verdict.resolved_as, verdict.reason
            ),
        )
        if verdict.rejection is not None:
            return verdict.rejection
        progress.phase, progress.call_id = "tool_execution", call.id
        return await self._execute(tool, call, copy.deepcopy(effective))

    def _decide(self, call: ToolCall, evaluated_call: ToolCall) -> _Verdict:
        """Ask the policy; the call may only run when the decision is exactly ALLOW.

        The loop is the last barrier (fail closed): DENY, ASK (no approver in Sprint 1),
        an exception or any unexpected value all mean "do not execute". The policy returns
        only an enum, so the rejection text is written here.
        """
        try:
            decision: object = self._policy.evaluate(evaluated_call)
        except Exception:
            decision = None
        if decision is PermissionDecision.ALLOW:
            return _Verdict("allow", "allow", None, None)
        if decision is PermissionDecision.DENY:
            return _Verdict(
                "deny",
                "deny",
                None,
                _rejection(
                    call,
                    "permission_denied",
                    f"[permission_denied] Tool '{call.name}' was denied by the permission policy.",
                ),
            )
        if decision is PermissionDecision.ASK:
            return _Verdict(
                "ask",
                "deny",
                None,
                _rejection(
                    call,
                    "approval_required_unavailable",
                    f"[approval_required_unavailable] Tool '{call.name}' requires approval, "
                    "which is not available in this session; the request was resolved as "
                    "denied.",
                ),
            )
        return _Verdict(
            "deny",
            "deny",
            "policy_error",
            _rejection(
                call,
                "permission_denied",
                f"[permission_denied] Tool '{call.name}' could not be evaluated and was "
                "denied (fail closed).",
            ),
        )

    @staticmethod
    async def _execute(tool: Tool, call: ToolCall, authorized: dict[str, Any]) -> _Outcome:
        """Run the tool with exactly the authorized arguments and normalize the outcome.

        Only ordinary exceptions are converted into a structured result: cancellation
        (``CancelledError``, a ``BaseException``) always propagates.
        """
        try:
            result = await tool.run(authorized)
        except Exception as exc:
            content = (
                f"[tool_exception] Tool '{call.name}' raised {type(exc).__name__}: "
                f"{_bounded(str(exc))}"
            )
            return _Outcome(ToolResult(call.id, content, True), "tool_exception", True)
        if not isinstance(result, ToolResult) or not isinstance(result.content, str):
            content = (
                f"[tool_exception] Tool '{call.name}' returned an invalid result "
                f"({type(result).__name__})."
            )
            return _Outcome(ToolResult(call.id, content, True), "invalid_tool_result", True)
        if result.call_id != call.id:
            result = dataclasses.replace(result, call_id=call.id)
        return _Outcome(result, "tool_error" if result.is_error else "ok", True)

    # ------------------------------------------------------------------ events

    def _emit(self, session_id: str, event_type: EventType, payload: dict[str, Any]) -> None:
        """Publish one event. Exceptions from the bus are never caught here (Q4)."""
        self._bus.emit(Event.create(session_id, event_type, payload))


# ---------------------------------------------------------------------- payloads
# Small dictionaries without tool arguments or file contents (FR-029).


def _user_message_payload(task: str) -> dict[str, Any]:
    return {"content": task}


def _assistant_message_payload(text: str, tool_call_count: int, final: bool) -> dict[str, Any]:
    return {"content": text, "tool_call_count": tool_call_count, "final": final}


def _tool_requested_payload(call: ToolCall) -> dict[str, Any]:
    return {"call_id": call.id, "name": call.name}


def _permission_decided_payload(
    call: ToolCall,
    decision: str,
    resolved_as: str,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "call_id": call.id,
        "name": call.name,
        "decision": decision,
        "resolved_as": resolved_as,
        "reason": reason,
    }


def _tool_finished_payload(call: ToolCall, is_error: bool, category: str) -> dict[str, Any]:
    return {"call_id": call.id, "name": call.name, "is_error": is_error, "category": category}


def _provider_error_payload(reason: str, error_type: str, message: str) -> dict[str, Any]:
    return {"reason": reason, "error_type": error_type, "message": _bounded(message)}


def _interrupted_payload(phase: str, call_id: str | None) -> dict[str, Any]:
    return {"phase": phase, "call_id": call_id}
