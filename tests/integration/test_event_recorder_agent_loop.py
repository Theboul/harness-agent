"""The real agent loop persists its events through the recorder (HU-03-02 / T009)."""

from __future__ import annotations

from pathlib import Path

from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.adapters.storage.event_recorder import attach_event_recorder
from harness_agent.core import EventType, InMemoryEventBus
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.loop import TurnStatus
from tests.core.support import SESSION, call, make_rig, response
from tests.doubles import RecordingTool

ET = EventType


async def test_a_tool_turn_is_persisted_in_emission_order_and_survives_reopening(
    tmp_path: Path,
) -> None:
    db = tmp_path / "sessions.db"
    bus = InMemoryEventBus()
    emitted: list[EventType] = []
    for event_type in EventType:
        bus.subscribe(event_type, lambda event: emitted.append(event.type))

    with SqliteSessionStore(db, id_factory=lambda: SESSION) as store:
        store.create_session(goal="tarea de prueba")
        attach_event_recorder(bus, store)
        script: list[ProviderResponse | BaseException] = [
            response(call("c1", "step_1", n=1)),
            ProviderResponse(content="all done"),
        ]
        rig = make_rig(script, [RecordingTool("step_1", content="r1")], bus=bus)

        result = await rig.run("start")

        assert result.status is TurnStatus.COMPLETED
        assert [e.type for e in store.load_session(SESSION)] == emitted

    with SqliteSessionStore(db) as reopened:
        persisted = reopened.load_session(SESSION)

    assert [e.type for e in persisted] == [
        ET.USER_MESSAGE,
        ET.TOOL_REQUESTED,
        ET.PERMISSION_DECIDED,
        ET.TOOL_FINISHED,
        ET.ASSISTANT_MESSAGE,
    ]
    assert emitted == [e.type for e in persisted]
    assert len({e.id for e in persisted}) == len(persisted)
