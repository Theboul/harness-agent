"""Helpers to test the essential renewer without a database (HU-02-06.1).

Falsos of the two read-only protocols, a set of stored elements and the settings under which a
block of the size of the examples fits. They live next to the tests and are not part of
``tests/doubles``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from harness_agent.core import (
    ContextSettings,
    EssentialItem,
    EssentialRenewer,
    TaskCriteriaItem,
    check_block,
    criteria_reference,
    make_items,
)

MODEL = "fake/test"
# A window of 4 000 tokens at 50 % gives a threshold of 2 000: the block may weigh 400 tokens.
SETTINGS = ContextSettings(window_tokens=4_000, threshold_percent=50)
# A window of 1 000 tokens at 45 % gives 450: the block may weigh only 90 tokens (E1 weighs 115).
TINY = ContextSettings(window_tokens=1_000, threshold_percent=45)


class FakeSource:
    """An ``EssentialSource`` over a tuple; it records the sessions it was asked about."""

    def __init__(self, items: Sequence[EssentialItem]) -> None:
        self.items_found = tuple(items)
        self.asked: list[str] = []
        self.failure: BaseException | None = None

    def items(self, session_id: str) -> Sequence[EssentialItem]:
        self.asked.append(session_id)
        if self.failure is not None:
            raise self.failure
        return self.items_found


class FakeCriteria:
    """A ``CriteriaReader`` over a list; it records the references it was asked about."""

    def __init__(self, criteria: Sequence[TaskCriteriaItem]) -> None:
        self.criteria = list(criteria)
        self.asked: list[str] = []
        self.failure: BaseException | None = None

    def load_criteria(self, session_id: str) -> Sequence[TaskCriteriaItem]:
        self.asked.append(session_id)
        if self.failure is not None:
            raise self.failure
        return list(self.criteria)


def stored_items(reference: str = "referencia-1") -> tuple[EssentialItem, ...]:
    items = make_items(
        ticket="TAREA-14: Validar",
        objective="Rechazar correos sin dominio.",
        rules="No tocar el esquema.",
        instructions=[("entorno", "entorno"), ("git", "git")],
    )
    return (*items, criteria_reference(reference))


def pending() -> list[TaskCriteriaItem]:
    return [
        TaskCriteriaItem("1", "El validador rechaza a@"),
        TaskCriteriaItem("2", "Pasan las pruebas"),
    ]


def make_renewer(
    source: FakeSource | None = None,
    criteria: FakeCriteria | None = None,
    *,
    settings: ContextSettings = SETTINGS,
    model: Callable[[], str] = lambda: MODEL,
) -> tuple[EssentialRenewer, FakeSource, FakeCriteria]:
    chosen = source if source is not None else FakeSource(stored_items())
    reader = criteria if criteria is not None else FakeCriteria(pending())
    return EssentialRenewer(chosen, reader, settings, session_id="s1", model=model), chosen, reader


def expected_text(criteria: Sequence[TaskCriteriaItem] | None = None) -> str:
    return check_block(stored_items(), pending() if criteria is None else criteria, SETTINGS, MODEL)
