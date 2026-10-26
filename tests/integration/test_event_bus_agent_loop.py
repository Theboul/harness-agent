"""AC-01 of HU-01-05: the real agent loop of A emits to the real in-memory bus (T003).

AC-01 (literal): "Dado un turno completo, cuando corre, entonces el núcleo emite eventos de
mensaje, herramienta solicitada, herramienta terminada, aprobación pedida y error."

The loop (``core/loop.py``) is wired to ``InMemoryEventBus`` and a scripted provider. One
subscriber per event type records what arrives. Since HU-05-03 the loop emits
``APPROVAL_REQUESTED`` and ``APPROVAL_RESOLVED`` when the policy asks and an approver is
configured; without an approver it still does not (the Sprint 1 behavior).
"""

from __future__ import annotations

import pytest

from harness_agent.core.events import Event, EventType
from harness_agent.core.in_memory_event_bus import EventDeliveryError, InMemoryEventBus
from harness_agent.core.interfaces.provider import ProviderResponse
from harness_agent.core.interfaces.security import PermissionDecision
from harness_agent.core.loop import AgentLoop, TurnStatus
from tests.core.support import Rig, call, make_rig, response
from tests.doubles import DummyApprover, RecordingTool

ET = EventType
PER_CALL = [ET.TOOL_REQUESTED, ET.PERMISSION_DECIDED, ET.TOOL_FINISHED]


def subscribe_to_every_type(bus: InMemoryEventBus) -> list[Event]:
    """One subscriber per event type; all of them append to the returned list."""
    received: list[Event] = []
    for event_type in EventType:
        bus.subscribe(event_type, received.append)
    return received


def types_of(events: list[Event]) -> list[EventType]:
    return [event.type for event in events]


def tool_turn_rig(bus: InMemoryEventBus) -> Rig:
    script: list[ProviderResponse | BaseException] = [
        response(call("c1", "step_1", n=1)),
        ProviderResponse(content="all done"),
    ]
    return make_rig(script, [RecordingTool("step_1", content="r1")], bus=bus)


class TestTurnoCompletoConHerramienta:
    async def test_the_events_reach_the_subscribers_once_and_in_the_order_of_emission(
        self,
    ) -> None:
        bus = InMemoryEventBus()
        received = subscribe_to_every_type(bus)
        rig = tool_turn_rig(bus)

        result = await rig.run("start")

        assert result.status is TurnStatus.COMPLETED
        assert types_of(received) == [ET.USER_MESSAGE, *PER_CALL, ET.ASSISTANT_MESSAGE]
        assert len({event.id for event in received}) == len(received)

    async def test_each_type_reaches_only_the_subscribers_of_that_type(self) -> None:
        bus = InMemoryEventBus()
        by_type: dict[EventType, list[Event]] = {t: [] for t in EventType}
        for event_type in EventType:
            bus.subscribe(event_type, by_type[event_type].append)
        rig = tool_turn_rig(bus)

        await rig.run("start")

        for event_type, events in by_type.items():
            assert all(event.type is event_type for event in events), event_type
        assert len(by_type[ET.TOOL_REQUESTED]) == 1
        assert len(by_type[ET.TOOL_FINISHED]) == 1
        assert len(by_type[ET.USER_MESSAGE]) == 1
        assert len(by_type[ET.ASSISTANT_MESSAGE]) == 1

    async def test_a_three_step_turn_keeps_the_order_of_emission(self) -> None:
        bus = InMemoryEventBus()
        received = subscribe_to_every_type(bus)
        tools = [RecordingTool(f"step_{i}", content=f"r{i}") for i in (1, 2, 3)]
        script: list[ProviderResponse | BaseException] = [
            response(call("c1", "step_1")),
            response(call("c2", "step_2")),
            response(call("c3", "step_3")),
            ProviderResponse(content="all done"),
        ]
        rig = make_rig(script, list(tools), bus=bus)

        await rig.run("start")

        assert types_of(received) == [
            ET.USER_MESSAGE,
            *PER_CALL,
            *PER_CALL,
            *PER_CALL,
            ET.ASSISTANT_MESSAGE,
        ]

    async def test_the_core_prints_nothing_while_the_events_are_delivered(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bus = InMemoryEventBus()
        subscribe_to_every_type(bus)
        rig = tool_turn_rig(bus)

        await rig.run("start")

        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestErrorDelProveedor:
    async def test_a_provider_failure_is_delivered_as_a_provider_error_event(self) -> None:
        bus = InMemoryEventBus()
        received = subscribe_to_every_type(bus)
        rig = make_rig([RuntimeError("provider down")], [RecordingTool("t")], bus=bus)

        result = await rig.run("task")

        assert result.status is TurnStatus.PROVIDER_FAILED
        assert types_of(received) == [ET.USER_MESSAGE, ET.PROVIDER_ERROR]
        assert received[1].payload["error_type"] == "RuntimeError"


class TestQ4SuscriptorQueFalla:
    """Q4 of A: the loop never hides what ``emit`` raises; here a subscriber fails (US2)."""

    async def test_a_failing_subscriber_of_tool_requested_stops_the_turn_and_the_tool_does_not_run(
        self,
    ) -> None:
        bus = InMemoryEventBus()
        failure = RuntimeError("el suscriptor falló")

        def fail(_event: Event) -> None:
            raise failure

        bus.subscribe(ET.TOOL_REQUESTED, fail)
        tool = RecordingTool("step_1", content="r1")
        script: list[ProviderResponse | BaseException] = [
            response(call("c1", "step_1")),
            ProviderResponse(content="all done"),
        ]
        rig = make_rig(script, [tool], bus=bus)

        with pytest.raises(EventDeliveryError) as raised:
            await rig.run("start")

        assert raised.value.exceptions == (failure,)  # arrives unchanged, not wrapped again
        assert tool.executions == []
        assert rig.provider.call_count == 1

    async def test_a_failing_subscriber_does_not_leave_the_others_without_the_event(self) -> None:
        bus = InMemoryEventBus()
        received: list[Event] = []

        def fail(_event: Event) -> None:
            raise RuntimeError("el suscriptor falló")

        bus.subscribe(ET.USER_MESSAGE, fail)
        bus.subscribe(ET.USER_MESSAGE, received.append)
        rig = tool_turn_rig(bus)

        with pytest.raises(EventDeliveryError):
            await rig.run("start")

        assert types_of(received) == [ET.USER_MESSAGE]


class TestCriterioAC01:
    async def test_the_turns_cover_the_types_that_the_loop_emits_today(self) -> None:
        tool_bus, error_bus = InMemoryEventBus(), InMemoryEventBus()
        tool_events = subscribe_to_every_type(tool_bus)
        error_events = subscribe_to_every_type(error_bus)
        await tool_turn_rig(tool_bus).run("start")
        failing = make_rig([RuntimeError("provider down")], [RecordingTool("t")], bus=error_bus)
        await failing.run("task")

        seen = set(types_of(tool_events)) | set(types_of(error_events))

        assert {
            ET.USER_MESSAGE,
            ET.ASSISTANT_MESSAGE,
            ET.TOOL_REQUESTED,
            ET.TOOL_FINISHED,
            ET.PROVIDER_ERROR,
        } <= seen

    async def test_the_loop_emits_approval_requested_when_the_policy_asks_with_an_approver(
        self,
    ) -> None:
        bus = InMemoryEventBus()
        received = subscribe_to_every_type(bus)
        script: list[ProviderResponse | BaseException] = [
            response(call("c1", "step_1", n=1)),
            ProviderResponse(content="all done"),
        ]
        rig = make_rig(
            script,
            [RecordingTool("step_1")],
            decisions={"step_1": PermissionDecision.ASK},
            bus=bus,
        )
        rig.loop = AgentLoop(rig.provider, rig.registry, rig.policy, bus, approver=DummyApprover())

        await rig.run("start")

        assert types_of(received) == [
            ET.USER_MESSAGE,
            ET.TOOL_REQUESTED,
            ET.PERMISSION_DECIDED,
            ET.APPROVAL_REQUESTED,
            ET.APPROVAL_RESOLVED,
            ET.TOOL_FINISHED,
            ET.ASSISTANT_MESSAGE,
        ]

    async def test_the_loop_does_not_emit_approval_requested_without_an_approver(self) -> None:
        bus = InMemoryEventBus()
        received = subscribe_to_every_type(bus)
        await tool_turn_rig(bus).run("start")
        failing = make_rig([RuntimeError("provider down")], [RecordingTool("t")], bus=bus)
        await failing.run("task")

        assert ET.APPROVAL_REQUESTED not in types_of(received)

    def test_the_bus_delivers_approval_requested_when_somebody_emits_it(self) -> None:
        bus = InMemoryEventBus()
        received = subscribe_to_every_type(bus)
        event = Event.create("session-1", ET.APPROVAL_REQUESTED, {"tool": "write_file"})

        bus.emit(event)

        assert received == [event]
