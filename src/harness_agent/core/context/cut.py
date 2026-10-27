"""Split of the history, recent window and safe cut for the compaction (HU-02-03).

Pure and total functions: they never raise, whatever the history, so a compaction that cannot be
done simply does not happen. The order of the context after compacting is in
``specs/030-automatic-context-compaction/contracts/context_order.md``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from harness_agent.core.context.estimator import estimate_message
from harness_agent.core.context.summary import is_summary
from harness_agent.core.entities import Message, Role


@dataclass(frozen=True, slots=True)
class HistoryParts:
    """Where the protected head ends and where the part that can be summarised starts.

    Attributes:
        head_end: Index of the first message that is not protected head (right after the request).
        summary_index: Index of the previous summary (always ``head_end``), or ``None``.
        region_start: Index of the first message of the part that can be summarised.
    """

    head_end: int
    summary_index: int | None
    region_start: int


def is_real(message: Message) -> bool:
    """Whether ``message`` was produced by the conversation itself.

    The system messages and the external ``USER`` messages (the summary, the output of a
    verification) are injected by the harness and have no event of their own.
    """
    return message.role is not Role.SYSTEM and not (
        message.role is Role.USER and message.is_external
    )


def split_history(history: Sequence[Message]) -> HistoryParts | None:
    """Locate the protected head (system prefix and first request) and the previous summary.

    Returns ``None`` while there is no initial request: the first message after the leading
    system messages must be a ``USER`` message that is not external.
    """
    index = 0
    while index < len(history) and history[index].role is Role.SYSTEM:
        index += 1
    if index >= len(history):
        return None
    request = history[index]
    if request.role is not Role.USER or request.is_external:
        return None
    head_end = index + 1
    if head_end < len(history) and is_summary(history[head_end]):
        return HistoryParts(head_end, head_end, head_end + 1)
    return HistoryParts(head_end, None, head_end)


def choose_cut(
    history: Sequence[Message], region_start: int, budget_tokens: int, min_messages: int
) -> int | None:
    """The index of the first recent message, or ``None`` if nothing is left to summarise.

    The recent window takes messages from the end while their estimate fits in the budget, and
    never fewer than ``min_messages``. A cut that falls on a tool result retreats to the call that
    asked for it, so a call and all its results stay together on the recent side.
    """
    total = len(history)
    taken = 0
    used = 0
    for position in range(total - 1, max(region_start, 0) - 1, -1):
        cost = estimate_message(history[position])
        if taken >= min_messages and used + cost > budget_tokens:
            break
        used += cost
        taken += 1
    cut = total - taken
    while region_start < cut < total and history[cut].role is Role.TOOL:
        cut -= 1
    if cut <= region_start or cut <= 0:
        return None
    return cut


def rebuild_history(
    history: Sequence[Message], region_start: int, cut: int, summary: Message
) -> list[Message]:
    """The context after compacting: the head, the new summary and the recent messages.

    The previous summary, if any, is replaced. Every other message is the same object as before.
    """
    head = [message for message in history[:region_start] if not is_summary(message)]
    return [*head, summary, *history[cut:]]
