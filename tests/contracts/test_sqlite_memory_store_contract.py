"""The ``MemoryStore`` contract (HU-00-01) against the real SQLite implementation (HU-04-01).

The same assertions that ``test_contracts.py`` runs against the in-memory double run here against
``SqliteMemoryStore`` on a real file, so the double and the implementation cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from harness_agent.adapters.storage import SqliteMemoryStore, SqliteSessionStore
from harness_agent.core import MemoryStore
from tests.doubles import InMemoryMemoryStore


@pytest.fixture(params=["double", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[MemoryStore]:
    if request.param == "double":
        yield InMemoryMemoryStore()
        return
    sessions = SqliteSessionStore(tmp_path / "sessions.db")
    try:
        yield SqliteMemoryStore(sessions)
    finally:
        sessions.close()


def test_the_implementation_is_a_memory_store(store: MemoryStore) -> None:
    assert isinstance(store, MemoryStore)


def test_save_search_and_delete_follow_the_contract(store: MemoryStore) -> None:
    store.save("pref.theme", "dark")

    items = store.search(token_budget=50)
    assert [(item.key, item.content) for item in items] == [("pref.theme", "dark")]

    assert store.delete("pref.theme") is True
    assert store.delete("pref.theme") is False
    assert store.search(token_budget=50) == []


def test_saving_the_same_key_updates_it_instead_of_adding_another(store: MemoryStore) -> None:
    store.save("k", "uno")
    store.save("k", "dos")

    assert [(item.key, item.content) for item in store.search(token_budget=50)] == [("k", "dos")]


def test_search_never_returns_more_than_the_budget_allows(store: MemoryStore) -> None:
    store.save("a", "x" * 40)
    store.save("b", "y" * 40)

    found: Callable[[int], int] = lambda budget: len(store.search(token_budget=budget))  # noqa: E731

    assert found(1_000) == 2
    assert found(15) == 1
    assert found(0) == 0
