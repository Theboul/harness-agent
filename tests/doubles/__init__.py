"""Test doubles package for HARNESS contracts.

In-memory stub implementations of core interfaces (Provider, Tool,
Approver, Storage, EventBus) for isolated and rapid testing.
"""

from tests.doubles.dummy_approver import DummyApprover
from tests.doubles.dummy_provider import DummyProvider
from tests.doubles.dummy_tool import DummyTool
from tests.doubles.in_memory_store import InMemoryMemoryStore, InMemorySessionStore
from tests.doubles.recording_bus import RecordingEventBus

__all__ = [
    "DummyProvider",
    "DummyTool",
    "DummyApprover",
    "InMemorySessionStore",
    "InMemoryMemoryStore",
    "RecordingEventBus",
]
