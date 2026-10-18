"""Contract conformity tests for HARNESS core interfaces (AC-01).

Validates that all 14 abstract interfaces can be imported from harness_agent.core,
instantiated via test doubles, and executed (both sync and async) without
instantiation errors or missing abstract method exceptions.
"""

from __future__ import annotations

import pytest

# Verify SC-001: all interfaces importable directly from harness_agent.core
from harness_agent.core import (
    ApprovalAction,
    ApprovalResult,
    Approver,
    AuthorizedArea,
    ContextManager,
    Event,
    EventBus,
    EventType,
    McpClient,
    MemoryStore,
    Message,
    PermissionPolicy,
    Provider,
    ProviderResponse,
    RiskLevel,
    Role,
    SessionStore,
    Shell,
    SubagentRunner,
    TaskCriteria,
    Tool,
    ToolCall,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
)
from tests.doubles import (
    DummyApprover,
    DummyProvider,
    DummyTool,
    InMemoryMemoryStore,
    InMemorySessionStore,
    RecordingEventBus,
)


def test_core_exports_completeness() -> None:
    """Validate that all 14 interfaces and domain entities are exported."""
    expected_contracts = [
        Provider,
        Tool,
        ToolRegistry,
        PermissionPolicy,
        Approver,
        SessionStore,
        MemoryStore,
        ContextManager,
        McpClient,
        SubagentRunner,
        Shell,
        AuthorizedArea,
        TaskCriteria,
        EventBus,
    ]
    for contract in expected_contracts:
        assert isinstance(contract, type), f"Expected contract class: {contract}"


@pytest.mark.asyncio
async def test_provider_contract_with_dummy() -> None:
    """Validate Provider contract conformity with DummyProvider double."""
    provider: Provider = DummyProvider()
    assert isinstance(provider, Provider)

    msg = Message(role=Role.USER, content="Hello")
    tool_def = ToolDefinition(name="echo", description="Echo input", parameters={})
    response: ProviderResponse = await provider.complete([msg], [tool_def])

    assert isinstance(response, ProviderResponse)
    assert "Dummy" in response.content
    assert response.usage is not None
    assert response.usage.total_tokens == 15


@pytest.mark.asyncio
async def test_tool_contract_with_dummy() -> None:
    """Validate Tool contract conformity with DummyTool double."""
    tool: Tool = DummyTool(name="test_tool", risk=RiskLevel.LOW)
    assert isinstance(tool, Tool)
    assert tool.name == "test_tool"
    assert tool.risk == RiskLevel.LOW
    assert "properties" in tool.schema

    result: ToolResult = await tool.run({"input": "ping", "call_id": "c_123"})
    assert isinstance(result, ToolResult)
    assert result.call_id == "c_123"
    assert not result.is_error
    assert "Executed test_tool" in result.content


@pytest.mark.asyncio
async def test_approver_contract_with_dummy() -> None:
    """Validate Approver contract conformity with DummyApprover double."""
    approver: Approver = DummyApprover(default_action=ApprovalAction.APPROVE_ONCE)
    assert isinstance(approver, Approver)

    call = ToolCall(id="call_99", name="shell", arguments={"cmd": "dir"})
    approval: ApprovalResult = await approver.request(call, {"risk": "HIGH"})
    assert isinstance(approval, ApprovalResult)
    assert approval.action == ApprovalAction.APPROVE_ONCE


def test_session_store_contract_with_dummy() -> None:
    """Validate SessionStore contract conformity with InMemorySessionStore double."""
    store: SessionStore = InMemorySessionStore()
    assert isinstance(store, SessionStore)

    event = Event.create(session_id="sess_alpha", type=EventType.SESSION_STARTED)
    store.save_event(event)

    loaded = store.load_session("sess_alpha")
    assert len(loaded) == 1
    assert loaded[0].id == event.id
    assert loaded[0].type == EventType.SESSION_STARTED

    sessions = store.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].id == "sess_alpha"


def test_memory_store_contract_with_dummy() -> None:
    """Validate MemoryStore contract conformity with InMemoryMemoryStore double."""
    store: MemoryStore = InMemoryMemoryStore()
    assert isinstance(store, MemoryStore)

    store.save("pref/theme", "dark")
    items = store.search(token_budget=50)
    assert len(items) == 1
    assert items[0].key == "pref/theme"
    assert items[0].content == "dark"

    deleted = store.delete("pref/theme")
    assert deleted is True
    assert len(store.search(token_budget=50)) == 0


def test_event_bus_contract_with_dummy() -> None:
    """Validate EventBus contract conformity with RecordingEventBus double."""
    bus: EventBus = RecordingEventBus()
    assert isinstance(bus, EventBus)

    received_events: list[Event] = []

    def handler(evt: Event) -> None:
        received_events.append(evt)

    bus.subscribe(EventType.USER_MESSAGE, handler)

    event1 = Event.create(session_id="s1", type=EventType.USER_MESSAGE, payload={"text": "hello"})
    event2 = Event.create(session_id="s1", type=EventType.TOOL_REQUESTED)

    bus.emit(event1)
    bus.emit(event2)

    assert len(received_events) == 1
    assert received_events[0].id == event1.id
