"""Test doubles package for HARNESS contracts.

In-memory stub implementations of core interfaces (Provider, Tool,
Approver, Storage, EventBus) for isolated and rapid testing.
"""

from tests.doubles.bounded import run_bounded
from tests.doubles.dummy_approver import DummyApprover
from tests.doubles.dummy_provider import DummyProvider
from tests.doubles.dummy_tool import DummyTool
from tests.doubles.failing_bus import FailingEventBus
from tests.doubles.in_memory_registry import InMemoryToolRegistry
from tests.doubles.in_memory_store import InMemoryMemoryStore, InMemorySessionStore
from tests.doubles.recording_bus import RecordingEventBus
from tests.doubles.scripted_policy import ScriptedPolicy
from tests.doubles.scripted_provider import ScriptedProvider, ScriptExhausted
from tests.doubles.scripted_tools import BlockingTool, FailingTool, RaisingTool, RecordingTool

__all__ = [
    "DummyProvider",
    "DummyTool",
    "DummyApprover",
    "InMemorySessionStore",
    "InMemoryMemoryStore",
    "RecordingEventBus",
    "ScriptedProvider",
    "ScriptExhausted",
    "run_bounded",
    "InMemoryToolRegistry",
    "ScriptedPolicy",
    "RecordingTool",
    "FailingTool",
    "RaisingTool",
    "BlockingTool",
    "FailingEventBus",
]
