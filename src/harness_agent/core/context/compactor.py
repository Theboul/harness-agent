"""Compaction of the context when it grows past the threshold of the model (HU-02-03).

``ContextCompactor.before_turn`` is called by the composition root before each request of the
person reaches the loop. When the estimate is above the threshold it summarises the old part of
the history with a separate model call (no tools), saves the summary and marks the events it
covers in one step, and only then replaces the history in memory. The loop is not touched.

Nothing here reads a file, the environment or the terminal: the collaborators come by constructor.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from harness_agent.core.context.cut import (
    choose_cut,
    is_real,
    rebuild_history,
    split_history,
)
from harness_agent.core.context.errors import CompactionError
from harness_agent.core.context.estimator import estimate_messages, estimate_tool_definition
from harness_agent.core.context.settings import (
    ContextSettings,
    recent_budget_tokens,
    summary_cap_tokens,
    threshold_tokens,
)
from harness_agent.core.context.store import CompactionCommit, CompactionStore, MessageEvent
from harness_agent.core.context.summary import (
    build_summary_request,
    check_summary,
    frame_summary,
    summary_text,
)
from harness_agent.core.entities import Message, Role
from harness_agent.core.events import Event, EventType
from harness_agent.core.interfaces.provider import Provider, ToolDefinition

_MAPPING_MISMATCH = (
    "Los mensajes del historial no coinciden con los eventos guardados de la sesión."
)
# Fixed texts (contracts/compaction_events.md): they never carry the summary, the history or the
# message of an exception.
_FAILURE_PAYLOAD = {
    "reason": "compaction_failed",
    "error_type": "CompactionFailed",
    "message": "No se pudo compactar el contexto; el turno continúa sin compactar.",
}
_PUBLISH_NOTICE = (
    "Aviso: la compactación se guardó, pero no se pudo avisar a todos los suscriptores del "
    "evento; el turno continúa con el contexto compactado."
)
_ABOVE_NOTICE = (
    "Aviso: el contexto sigue por encima del umbral tras compactar (~{estimated} de {threshold} "
    "tokens); el turno continúa sin reintentar."
)


@dataclass(frozen=True)
class CompactionResult:
    """What a compaction did: the range of events it covered and the estimates around it."""

    desde: int
    hasta: int
    eventos: int
    estimated_before: int
    estimated_after: int


def _event_kind(message: Message) -> str | None:
    """The kind of event that a real message leaves in the store, or ``None`` if it leaves none.

    The loop publishes ``assistant_message`` only when the model wrote some text, so an assistant
    message that just asks for tools has no event.
    """
    if message.role is Role.USER:
        return "user"
    if message.role is Role.TOOL:
        return "tool"
    return "assistant" if message.content else None


def _pair_events(history: Sequence[Message], events: Sequence[MessageEvent]) -> dict[int, int]:
    """Link each message that has an event to the ``seq`` of that event (index -> seq).

    The real messages and the events that are not covered yet must agree one by one, in order and
    in kind; otherwise the link is not trustworthy and ``CompactionError`` is raised.
    """
    expected = [
        (index, kind)
        for index, message in enumerate(history)
        if is_real(message) and (kind := _event_kind(message)) is not None
    ]
    pending = [event for event in events if not event.covered]
    if [kind for _, kind in expected] != [event.kind for event in pending]:
        raise CompactionError(_MAPPING_MISMATCH)
    return {index: event.seq for (index, _), event in zip(expected, pending, strict=True)}


class ContextCompactor:
    """Summarises the old part of the history when the context passes the threshold."""

    def __init__(
        self,
        provider: Provider,
        store: CompactionStore,
        settings: ContextSettings,
        *,
        session_id: str,
        model: Callable[[], str],
        definitions: Callable[[], Sequence[ToolDefinition]],
        emit: Callable[[EventType, dict[str, Any]], None],
        publish: Callable[[Event], None],
        warn: Callable[[str], None],
        new_id: Callable[[], str],
    ) -> None:
        self._provider = provider
        self._store = store
        self._settings = settings
        self._session_id = session_id
        self._model = model
        self._definitions = definitions
        self._emit = emit
        self._publish = publish
        self._warn = warn
        self._new_id = new_id

    def _tools_estimate(self) -> int:
        return sum(estimate_tool_definition(d) for d in self._definitions())

    async def before_turn(self, history: list[Message]) -> CompactionResult | None:
        """Compact ``history`` in place if it is above the threshold; return what was covered.

        Returns ``None`` when there is nothing to do or when the compaction failed: a failure
        before the view changes leaves everything as it was, is reported with a fixed
        ``provider_error`` and lets the turn go on. At most one compaction happens per call, and
        a cancellation is never caught.
        """
        try:
            model = self._model()
            threshold = threshold_tokens(self._settings, model)
            tools = self._tools_estimate()
            before = estimate_messages(history) + tools
            if before <= threshold:
                return None
            parts = split_history(history)
            if parts is None:
                return None
            cut = choose_cut(
                history,
                parts.region_start,
                recent_budget_tokens(self._settings, model),
                self._settings.min_recent_messages,
            )
            if cut is None:
                return None
            paired = _pair_events(history, self._store.message_events(self._session_id))
            old = [seq for index, seq in paired.items() if parts.region_start <= index < cut]
            if not old:
                return None
            previous = (
                summary_text(history[parts.summary_index])
                if parts.summary_index is not None
                else None
            )
            request = build_summary_request(
                previous, history[parts.region_start : cut], self._settings.summary_tokens
            )
            response = await self._provider.complete(request)
            text = check_summary(response.content, summary_cap_tokens(self._settings))
            receipt = self._store.commit_compaction(
                CompactionCommit(
                    session_id=self._session_id,
                    protected_seq=paired[parts.head_end - 1],
                    through_seq=old[-1],
                    summary=text,
                    summary_id=self._new_id(),
                    event_id=self._new_id(),
                )
            )
        except Exception:
            self._emit(EventType.PROVIDER_ERROR, dict(_FAILURE_PAYLOAD))
            return None
        if receipt is None:
            return None
        # No await from here on: the saved summary and the view in memory change together.
        history[:] = rebuild_history(history, parts.region_start, cut, frame_summary(text))
        try:
            self._publish(receipt.event)
        except Exception:
            # The summary is saved and the view is compacted: this is not a failed compaction.
            self._warn(_PUBLISH_NOTICE)
        after = estimate_messages(history) + tools
        if after > threshold:
            self._warn(_ABOVE_NOTICE.format(estimated=after, threshold=threshold))
        return CompactionResult(receipt.desde, receipt.hasta, receipt.eventos, before, after)
