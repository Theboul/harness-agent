"""Renewal of the essential block in the history of a session (HU-02-06.1).

``EssentialRenewer.renew`` reads the elements of the task and the state of its criteria and puts
the block in the history, in place: it inserts it after the system messages of the prefix, replaces
it where it is, or leaves it alone if the text did not change. There is never more than one block,
and the same data always give the same text.

It is called by the composition root and nowhere else: before each request (before the
compaction, so its estimate sees the block) and before each verification round. The loop is not
involved. Everything it reads comes in by constructor and through read-only protocols.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import Enum
from typing import Protocol

from harness_agent.core.context.errors import EssentialContextError, EssentialContextUnavailable
from harness_agent.core.context.essential import (
    KEY_CRITERIA_REF,
    KEY_INSTRUCTIONS,
    KEY_OBJECTIVE,
    EssentialItem,
    block_message,
    check_block,
    find_blocks,
)
from harness_agent.core.context.settings import ContextSettings
from harness_agent.core.entities import Message, Role
from harness_agent.core.interfaces.system import TaskCriteriaItem


class EssentialSource(Protocol):
    """Where the elements of a session are read from (read only)."""

    def items(self, session_id: str) -> Sequence[EssentialItem]:
        """The stored elements of the session."""
        ...


class CriteriaReader(Protocol):
    """Where the protected criteria are read from (read only)."""

    def load_criteria(self, session_id: str) -> Sequence[TaskCriteriaItem]:
        """The criteria of ``session_id`` with their state, in order."""
        ...


class RenewalOutcome(Enum):
    """What a renewal did to the history."""

    INSERTED = "inserted"
    REPLACED = "replaced"
    UNCHANGED = "unchanged"


def _prefix_length(history: Sequence[Message]) -> int:
    length = 0
    while length < len(history) and history[length].role is Role.SYSTEM:
        length += 1
    return length


class EssentialRenewer:
    """Keeps exactly one up-to-date essential block in the history of one session."""

    def __init__(
        self,
        source: EssentialSource,
        criteria: CriteriaReader,
        settings: ContextSettings,
        *,
        session_id: str,
        model: Callable[[], str],
    ) -> None:
        self._source = source
        self._criteria = criteria
        self._settings = settings
        self._session_id = session_id
        self._model = model

    def _text(self) -> str:
        """The text of the block now, from the stored elements and the state of the criteria."""
        items = self._source.items(self._session_id)
        keys = {item.key for item in items}
        if not {KEY_OBJECTIVE, KEY_CRITERIA_REF, KEY_INSTRUCTIONS} <= keys:
            # A task with no elements is never a session without a task (that one has no renewer).
            raise EssentialContextUnavailable(missing=True)
        reference = next(item for item in items if item.key == KEY_CRITERIA_REF)
        criteria = self._criteria.load_criteria(reference.value)
        return check_block(items, criteria, self._settings, self._model())

    def renew(self, history: list[Message]) -> RenewalOutcome:
        """Put the current block in ``history`` (in place) and say what was done.

        Fails closed and leaves ``history`` as it was: ``EssentialContextUnavailable`` if the
        elements are missing (with ``missing=True``) or a source cannot be read, and
        ``EssentialContextTooLarge`` if the block does not fit. Only ordinary exceptions of a source
        are turned into the fixed message, which keeps nothing of them; a cancellation or an
        interrupt goes through.
        """
        unreadable = False
        try:
            text = self._text()
        except EssentialContextError:
            raise
        except Exception:
            unreadable = True
        if unreadable:
            # Raised outside the handler so that the original error is not kept as its context.
            raise EssentialContextUnavailable()
        found = find_blocks(history)
        if not found:
            history.insert(_prefix_length(history), block_message(text))
            return RenewalOutcome.INSERTED
        first, extra = found[0], found[1:]
        for position in reversed(extra):
            del history[position]
        if history[first].content == text:
            return RenewalOutcome.REPLACED if extra else RenewalOutcome.UNCHANGED
        history[first] = block_message(text)
        return RenewalOutcome.REPLACED
