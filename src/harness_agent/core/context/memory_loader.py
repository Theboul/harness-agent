"""Loading of the persistent memory at the start of a new session (HU-04-02).

``MemoryLoader.load_into`` reads the entries, picks the most recent ones that fit the budget of the
active model and puts one block in the history, in place. The composition root calls it when a
session starts (and for ``/nueva``) and nowhere else: a resumed session is rebuilt from what was
stored and gets no block. The loop and the compactor do not know it.

A memory that cannot be read is a fixed warning and a session without memory: the block can only
add data, never authority, so leaving it out is the safe direction. A cancellation goes through.
"""

from __future__ import annotations

from collections.abc import Callable

from harness_agent.core.context.memory import (
    MemoryBlock,
    MemoryLog,
    MemorySettings,
    build_block,
    memory_budget,
    place_memory_block,
)
from harness_agent.core.context.settings import ContextSettings
from harness_agent.core.entities import Message

UNREADABLE_NOTICE = "No se pudo leer la memoria; la sesión empieza sin ella."


def omitted_notice(loaded: int, omitted: int) -> str:
    """The line for the person when entries did not fit (counts only, never a text)."""
    return (
        f"Memoria: se cargaron {loaded} entradas y se omitieron {omitted} más antiguas "
        "por el presupuesto."
    )


class MemoryLoader:
    """Puts the memory block in the history of a new session."""

    def __init__(
        self,
        log: MemoryLog,
        settings: MemorySettings,
        context: ContextSettings,
        *,
        model: Callable[[], str],
        warn: Callable[[str], None],
    ) -> None:
        self._log = log
        self._settings = settings
        self._context = context
        self._model = model
        self._warn = warn

    def load_into(self, history: list[Message]) -> MemoryBlock:
        """Add the block to ``history`` unless it is already there; say what was left out."""
        unreadable = False
        try:
            items = list(self._log.recent())
        except Exception:
            unreadable = True
        if unreadable:
            self._warn(UNREADABLE_NOTICE)  # outside the handler: nothing of the error is kept
            return MemoryBlock(None, 0, 0)
        budget = memory_budget(self._settings, self._context, self._model())
        block = build_block(items, budget)
        if place_memory_block(history, block) and block.omitted:
            self._warn(omitted_notice(block.loaded, block.omitted))
        return block
