"""HU-05-03 with the real loop, registry, tools, protective policy and the terminal approver.

Every `escribir_archivo` call is asked about (`ask` rule); the user's answers are typed into an
in-memory stream. Nothing touches the network or anything outside `tmp_path`.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from harness_agent.adapters.system import ProtectedPaths, WorkspaceArea
from harness_agent.adapters.tools.write_file import WriteFileTool
from harness_agent.cli import ConsoleApprover
from harness_agent.core import (
    DefaultPermissionPolicy,
    EventType,
    InMemoryToolRegistry,
    PermissionDecision,
    PermissionPolicy,
    PermissionRules,
    ProtectedPolicy,
    ProviderResponse,
    Role,
    ToolCall,
)
from harness_agent.core.loop import AgentLoop, TurnResult
from tests.doubles import RecordingEventBus, ScriptedProvider, run_bounded

PROTECTED_NAME = "sesiones.db"


def write(call_id: str, path: str, content: str = "x") -> ToolCall:
    return ToolCall(
        id=call_id, name="escribir_archivo", arguments={"path": path, "content": content}
    )


class Flip(PermissionPolicy):
    """Asks the first time and denies afterwards (a rule that tightens during the session)."""

    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        self.calls += 1
        return PermissionDecision.ASK if self.calls == 1 else PermissionDecision.DENY


class Rig:
    def __init__(
        self, root: Path, typed: str, calls: list[ToolCall], policy: PermissionPolicy | None = None
    ) -> None:
        area = WorkspaceArea(root)
        self.registry = InMemoryToolRegistry()
        self.registry.register(WriteFileTool(area))
        if policy is None:
            inner = DefaultPermissionPolicy(
                self.registry, area, PermissionRules(ask=("escribir_archivo",))
            )
            protected = ProtectedPaths(root, files=(root / PROTECTED_NAME,), directories=())
            policy = ProtectedPolicy(inner, protected, (PROTECTED_NAME,))
        steps: list[ProviderResponse | BaseException] = [
            ProviderResponse(tool_calls=[one]) for one in calls
        ]
        steps.append(ProviderResponse(content="listo"))
        self.provider = ScriptedProvider(steps)
        self.bus = RecordingEventBus()
        self.output = io.StringIO()
        approver = ConsoleApprover(io.StringIO(typed), self.output)
        self.loop = AgentLoop(self.provider, self.registry, policy, self.bus, approver=approver)

    async def run(self) -> TurnResult:
        return await run_bounded(
            self.loop.run_turn(session_id="s1", task="escribe", history=[]),
            provider=self.provider,
        )

    def answers(self, result: TurnResult) -> list[str]:
        return [m.content for m in result.history if m.role is Role.TOOL]

    def events(self, event_type: EventType) -> list[dict[str, Any]]:
        return [e.payload for e in self.bus.emitted_events if e.type is event_type]


async def test_approving_once_writes_and_asks_again_for_the_same_call(tmp_path: Path) -> None:
    rig = Rig(tmp_path, "1\n1\n", [write("c1", "a.txt"), write("c2", "a.txt")])

    result = await rig.run()

    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "x"
    assert rig.output.getvalue().count("El agente quiere ejecutar: escribir_archivo") == 2
    assert [p["source"] for p in rig.events(EventType.APPROVAL_RESOLVED)] == ["user", "user"]
    assert all(not a.startswith("[approval") for a in rig.answers(result))


async def test_session_approval_covers_only_the_same_arguments(tmp_path: Path) -> None:
    calls = [
        write("c1", "a.txt", "uno"),
        write("c2", "a.txt", "uno"),
        write("c3", "a.txt", "otro"),
    ]
    rig = Rig(tmp_path, "2\n3\n", calls)

    result = await rig.run()

    resolved = rig.events(EventType.APPROVAL_RESOLVED)
    assert [p["source"] for p in resolved] == ["user", "session_grant", "user"]
    assert [p["approved"] for p in resolved] == [True, True, False]
    assert rig.output.getvalue().count("El agente quiere ejecutar") == 2
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "uno"
    assert rig.answers(result)[2].startswith("[approval_rejected]")


async def test_the_protected_area_stays_denied_and_is_never_asked(tmp_path: Path) -> None:
    rig = Rig(tmp_path, "2\n2\n", [write("c1", "a.txt"), write("c2", PROTECTED_NAME)])

    result = await rig.run()

    assert not (tmp_path / PROTECTED_NAME).exists()
    assert rig.answers(result)[1].startswith("[permission_denied]")
    assert len(rig.events(EventType.APPROVAL_REQUESTED)) == 1


async def test_a_session_approval_does_not_override_a_later_denial(tmp_path: Path) -> None:
    rig = Rig(tmp_path, "2\n", [write("c1", "a.txt"), write("c2", "a.txt")], policy=Flip())

    result = await rig.run()

    assert rig.answers(result)[1].startswith("[permission_denied]")
    assert len(rig.events(EventType.APPROVAL_RESOLVED)) == 1


async def test_no_answer_at_all_means_nothing_is_written(tmp_path: Path) -> None:
    rig = Rig(tmp_path, "", [write("c1", "a.txt")])

    result = await rig.run()

    assert not (tmp_path / "a.txt").exists()
    assert rig.answers(result)[0].startswith("[approval_rejected]")
