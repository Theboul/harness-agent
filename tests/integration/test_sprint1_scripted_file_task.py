"""Sprint 1 demo criterion 1 (HU-00-03 + HU-01-01 + HU-01-03 + HU-05-01), converge task T019.

"With the simulated provider, a scripted three-step task (read, write and re-read a file) inside
the authorized area ends the same in every run, also in continuous integration."

``FakeProvider`` (HU-00-03) drives the real ``AgentLoop`` (HU-01-01) over the four file tools and
the real ``WorkspaceArea`` (HU-01-03), with the real registry and the real
``DefaultPermissionPolicy`` (HU-05-01). External network access is blocked for the whole
module (the guard fixture of the ``FakeProvider`` integration tests is reused, not copied).
No production code is involved.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools import ListFilesTool, ReadFileTool, SearchTextTool, WriteFileTool
from harness_agent.core import (
    DefaultPermissionPolicy,
    EventType,
    InMemoryToolRegistry,
    Message,
    PermissionRules,
    ProviderError,
    ProviderResponse,
    QuotaExceeded,
    Role,
    ToolCall,
)
from harness_agent.core.loop import AgentLoop, TurnResult, TurnStatus
from tests.doubles import FakeProvider, RecordingEventBus
from tests.integration.test_fake_provider_agent_loop import blocked_network  # noqa: F401

TASK = "lee, escribe y vuelve a leer notas.txt"
RUNS = 20


def call(call_id: str, name: str, **arguments: Any) -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=dict(arguments))


def three_steps() -> list[ProviderResponse | ProviderError]:
    return [
        ProviderResponse(tool_calls=[call("c1", "leer_archivo", path="notas.txt")]),
        ProviderResponse(
            tool_calls=[call("c2", "escribir_archivo", path="notas.txt", content="nuevo")]
        ),
        ProviderResponse(tool_calls=[call("c3", "leer_archivo", path="notas.txt")]),
        ProviderResponse(content="listo"),
    ]


class Rig:
    """The system composed by hand, as ``bootstrap.py`` will do it."""

    def __init__(self, area_dir: Path, script: list[ProviderResponse | ProviderError]) -> None:
        area = WorkspaceArea(area_dir)
        self.registry = InMemoryToolRegistry()
        for tool in (
            ReadFileTool(area),
            WriteFileTool(area),
            ListFilesTool(area),
            SearchTextTool(area),
        ):
            self.registry.register(tool)
        policy = DefaultPermissionPolicy(self.registry, area, PermissionRules())
        self.bus = RecordingEventBus()
        self.provider = FakeProvider(script)
        self.loop = AgentLoop(self.provider, self.registry, policy, self.bus)

    async def go(self) -> TurnResult:
        async with asyncio.timeout(5.0):
            return await self.loop.run_turn(session_id="s1", task=TASK, history=[])

    def decisions(self) -> list[tuple[str, str, str]]:
        return [
            (e.payload["name"], e.payload["decision"], e.payload["resolved_as"])
            for e in self.bus.emitted_events
            if e.type is EventType.PERMISSION_DECIDED
        ]

    def signature(self, result: TurnResult, area_dir: Path) -> tuple[Any, ...]:
        """Everything a run decides; event ids and timestamps are excluded (random and clock)."""
        return (
            result.status,
            result.final_response,
            result.history,
            [(e.type, e.payload) for e in self.bus.emitted_events],
            self.provider.received,
            self.provider.call_count,
            (area_dir / "notas.txt").read_text(encoding="utf-8"),
        )


def fresh_area(tmp_path: Path, name: str) -> Path:
    area = tmp_path / name
    area.mkdir()
    (area / "notas.txt").write_text("viejo", encoding="utf-8", newline="")
    return area


def tool_messages(result: TurnResult) -> list[Message]:
    return [m for m in result.history if m.role is Role.TOOL]


class TestTheThreeStepTask:
    async def test_it_reads_writes_and_rereads_inside_the_area(self, tmp_path: Path) -> None:
        area = fresh_area(tmp_path, "area")
        rig = Rig(area, three_steps())

        result = await rig.go()

        assert result.status is TurnStatus.COMPLETED
        assert result.final_response == "listo"
        assert [m.content for m in tool_messages(result)] == [
            "viejo",
            "Archivo reemplazado: 'notas.txt' (5 bytes).",
            "nuevo",
        ]
        assert (area / "notas.txt").read_text(encoding="utf-8") == "nuevo"
        assert rig.decisions() == [
            ("leer_archivo", "allow", "allow"),
            ("escribir_archivo", "allow", "allow"),
            ("leer_archivo", "allow", "allow"),
        ]
        assert rig.provider.exhausted is False

    async def test_each_call_to_the_provider_receives_the_history_built_so_far(
        self, tmp_path: Path
    ) -> None:
        rig = Rig(fresh_area(tmp_path, "area"), three_steps())

        await rig.go()

        assert [len(messages) for messages in rig.provider.received] == [1, 3, 5, 7]
        assert rig.provider.received[0] == [Message(role=Role.USER, content=TASK)]

    async def test_twenty_runs_end_exactly_the_same(self, tmp_path: Path) -> None:
        signatures = []
        for number in range(RUNS):
            area = fresh_area(tmp_path, f"area-{number}")
            rig = Rig(area, three_steps())
            result = await rig.go()
            signatures.append(rig.signature(result, area))

        assert all(signature == signatures[0] for signature in signatures)

    async def test_the_whole_task_makes_no_external_network_attempt(
        self,
        tmp_path: Path,
        blocked_network: list[str],  # noqa: F811
    ) -> None:
        for number in range(5):
            await Rig(fresh_area(tmp_path, f"area-{number}"), three_steps()).go()

        assert blocked_network == []


class TestTheAreaStillProtectsTheDisk:
    async def test_a_write_outside_the_area_is_asked_denied_and_creates_nothing(
        self, tmp_path: Path
    ) -> None:
        area = fresh_area(tmp_path, "area")
        script: list[ProviderResponse | ProviderError] = [
            ProviderResponse(
                tool_calls=[call("c1", "escribir_archivo", path="../fuera.txt", content="x")]
            ),
            ProviderResponse(content="listo"),
        ]
        rig = Rig(area, script)

        result = await rig.go()

        (message,) = tool_messages(result)
        assert message.content.startswith("[approval_required_unavailable]")
        assert rig.decisions() == [("escribir_archivo", "ask", "deny")]
        assert not (tmp_path / "fuera.txt").exists()
        assert (area / "notas.txt").read_text(encoding="utf-8") == "viejo"


class TestAProviderFailureHalfWay:
    async def test_a_quota_error_after_the_first_step_ends_the_turn_and_keeps_the_work(
        self, tmp_path: Path
    ) -> None:
        area = fresh_area(tmp_path, "area")
        script: list[ProviderResponse | ProviderError] = [
            ProviderResponse(tool_calls=[call("c1", "leer_archivo", path="notas.txt")]),
            QuotaExceeded("cuota agotada"),
        ]
        rig = Rig(area, script)

        result = await rig.go()

        assert result.status is TurnStatus.PROVIDER_FAILED
        assert [m.content for m in tool_messages(result)] == ["viejo"]
        errors = [e for e in rig.bus.emitted_events if e.type is EventType.PROVIDER_ERROR]
        assert [e.payload["error_type"] for e in errors] == ["QuotaExceeded"]
        assert (area / "notas.txt").read_text(encoding="utf-8") == "viejo"
