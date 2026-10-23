"""AC-01 to AC-04 of HU-01-03 with the real loop, the real policy, the real registry and the area.

The system is composed by hand (``bootstrap.py`` does not exist yet): a ``WorkspaceArea`` over a
temporary folder, the four file tools registered in the real ``InMemoryToolRegistry``, the real
``DefaultPermissionPolicy`` over that registry and area, a recording bus and a scripted provider.
Nothing touches the network or anything outside ``tmp_path``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools.list_files import ListFilesTool
from harness_agent.adapters.tools.read_file import ReadFileTool
from harness_agent.adapters.tools.search_text import SearchTextTool
from harness_agent.adapters.tools.write_file import WriteFileTool
from harness_agent.core import (
    DefaultPermissionPolicy,
    EventType,
    InMemoryToolRegistry,
    Message,
    PermissionRules,
    ProviderResponse,
    Role,
    Tool,
    ToolCall,
)
from harness_agent.core.loop import AgentLoop, TurnResult, TurnStatus
from tests.doubles import RecordingEventBus, ScriptedProvider, run_bounded

SENTINEL = "VALOR-DE-PRUEBA-123"


def call(call_id: str, name: str, **arguments: Any) -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=dict(arguments))


def script(*calls: ToolCall) -> list[ProviderResponse | BaseException]:
    steps: list[ProviderResponse | BaseException] = [
        ProviderResponse(tool_calls=[one]) for one in calls
    ]
    steps.append(ProviderResponse(content="listo"))
    return steps


class Rig:
    """The composed system: what ``bootstrap.py`` will connect."""

    def __init__(
        self,
        workspace_root: Path | None,
        steps: list[ProviderResponse | BaseException],
        *,
        allow_reads_in_area: bool = True,
    ) -> None:
        area = WorkspaceArea(workspace_root) if workspace_root is not None else None
        tools: Sequence[Tool] = (
            ReadFileTool(area),
            WriteFileTool(area),
            ListFilesTool(area),
            SearchTextTool(area),
        )
        self.registry = InMemoryToolRegistry()
        for tool in tools:
            self.registry.register(tool)
        policy = DefaultPermissionPolicy(
            self.registry, area, PermissionRules(), allow_reads_in_area=allow_reads_in_area
        )
        self.bus = RecordingEventBus()
        self.provider = ScriptedProvider(steps)
        self.loop = AgentLoop(self.provider, self.registry, policy, self.bus)

    async def go(self, task: str = "haz la tarea") -> TurnResult:
        return await run_bounded(
            self.loop.run_turn(session_id="s1", task=task, history=[]), provider=self.provider
        )

    def decisions(self) -> list[tuple[str, str, str]]:
        return [
            (e.payload["name"], e.payload["decision"], e.payload["resolved_as"])
            for e in self.bus.emitted_events
            if e.type is EventType.PERMISSION_DECIDED
        ]


def tool_messages(result: TurnResult) -> list[Message]:
    return [m for m in result.history if m.role is Role.TOOL]


@pytest.fixture
def area_dir(tmp_path: Path) -> Path:
    area = tmp_path / "area"
    (area / "src").mkdir(parents=True)
    (area / "src" / "pago.py").write_text("def cobrar(monto):\n    return monto\n", "utf-8")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.txt").write_text(SENTINEL, encoding="utf-8")
    return area


class TestTheComposedSystem:
    def test_the_four_tools_register_and_the_policy_sees_their_risk(self, area_dir: Path) -> None:
        rig = Rig(area_dir, script())

        names = sorted(tool.name for tool in rig.registry.list())

        assert names == ["buscar_texto", "escribir_archivo", "leer_archivo", "listar_archivos"]


class TestRead:
    async def test_read_a_file_inside_the_area(self, area_dir: Path) -> None:
        rig = Rig(area_dir, script(call("c1", "leer_archivo", path="src/pago.py")))

        result = await rig.go()

        assert result.status is TurnStatus.COMPLETED
        (message,) = tool_messages(result)
        assert message.content == "def cobrar(monto):\n    return monto\n"
        assert message.tool_result is not None
        assert message.tool_result.is_error is False
        assert message.is_external is True
        assert rig.decisions() == [("leer_archivo", "allow", "allow")]

    async def test_read_a_missing_path_gets_a_clear_error_not_an_exception(
        self, area_dir: Path
    ) -> None:
        rig = Rig(area_dir, script(call("c1", "leer_archivo", path="src/no-existe.py")))

        result = await rig.go()

        assert result.status is TurnStatus.COMPLETED
        (message,) = tool_messages(result)
        assert message.tool_result is not None
        assert message.tool_result.is_error is True
        assert message.content.startswith("[no_existe] ")
        assert "listar_archivos" in message.content
        assert "Traceback" not in message.content

    async def test_list_and_search_inside_the_area(self, area_dir: Path) -> None:
        rig = Rig(
            area_dir,
            script(
                call("c1", "listar_archivos", path="."),
                call("c2", "buscar_texto", path=".", query="cobrar"),
            ),
        )

        result = await rig.go()

        first, second = tool_messages(result)
        assert first.content == "[carpeta] src"
        assert second.content == "src/pago.py:1: def cobrar(monto):"
        assert [d[1:] for d in rig.decisions()] == [("allow", "allow"), ("allow", "allow")]

    async def test_without_the_read_rule_of_hu_05_01_reads_are_asked_and_denied(
        self, area_dir: Path
    ) -> None:
        rig = Rig(
            area_dir,
            script(call("c1", "leer_archivo", path="src/pago.py")),
            allow_reads_in_area=False,
        )

        result = await rig.go()

        (message,) = tool_messages(result)
        assert message.content.startswith("[approval_required_unavailable]")
        assert rig.decisions() == [("leer_archivo", "ask", "deny")]


class TestWriteInside:
    async def test_write_inside_the_area_runs_and_the_decision_is_recorded(
        self, area_dir: Path
    ) -> None:
        rig = Rig(
            area_dir, script(call("c1", "escribir_archivo", path="notas.txt", content="hola"))
        )

        result = await rig.go()

        assert result.status is TurnStatus.COMPLETED
        assert (area_dir / "notas.txt").read_text(encoding="utf-8") == "hola"
        (message,) = tool_messages(result)
        assert message.tool_result is not None
        assert message.tool_result.is_error is False
        assert rig.decisions() == [("escribir_archivo", "allow", "allow")]

    async def test_a_three_step_task_reads_writes_and_rereads_the_same_every_time(
        self, area_dir: Path
    ) -> None:
        def steps() -> list[ProviderResponse | BaseException]:
            return script(
                call("c1", "leer_archivo", path="src/pago.py"),
                call(
                    "c2",
                    "escribir_archivo",
                    path="src/pago.py",
                    content="def cobrar():\n    pass\n",
                ),
                call("c3", "leer_archivo", path="src/pago.py"),
            )

        outcomes = []
        for _ in range(3):
            (area_dir / "src" / "pago.py").write_text(
                "def cobrar(monto):\n    return monto\n", "utf-8"
            )
            rig = Rig(area_dir, steps())
            result = await rig.go()
            outcomes.append(([m.content for m in tool_messages(result)], rig.decisions()))

        assert outcomes[0] == outcomes[1] == outcomes[2]
        contents, decisions = outcomes[0]
        assert contents[0] == "def cobrar(monto):\n    return monto\n"
        assert contents[2] == "def cobrar():\n    pass\n"
        assert [d[1:] for d in decisions] == [("allow", "allow")] * 3


class TestWriteOutside:
    @pytest.mark.parametrize("path", ["../outside/nuevo.txt", "../nuevo.txt"])
    async def test_dot_dot_that_leaves_the_area_is_asked_and_denied(
        self, area_dir: Path, path: str
    ) -> None:
        rig = Rig(area_dir, script(call("c1", "escribir_archivo", path=path, content="x")))

        result = await rig.go()

        (message,) = tool_messages(result)
        assert message.content.startswith("[approval_required_unavailable]")
        assert rig.decisions() == [("escribir_archivo", "ask", "deny")]
        assert not (area_dir.parent / "nuevo.txt").exists()
        assert not (area_dir.parent / "outside" / "nuevo.txt").exists()

    async def test_an_absolute_path_outside_is_asked_and_denied(self, area_dir: Path) -> None:
        target = area_dir.parent / "outside" / "nuevo.txt"
        rig = Rig(area_dir, script(call("c1", "escribir_archivo", path=str(target), content="x")))

        await rig.go()

        assert rig.decisions() == [("escribir_archivo", "ask", "deny")]
        assert not target.exists()
        assert (area_dir.parent / "outside" / "secret.txt").read_text("utf-8") == SENTINEL

    async def test_the_model_message_does_not_reveal_files_outside(self, area_dir: Path) -> None:
        rig = Rig(area_dir, script(call("c1", "leer_archivo", path="../outside/secret.txt")))

        result = await rig.go()

        (message,) = tool_messages(result)
        assert SENTINEL not in message.content
        assert rig.decisions() == [("leer_archivo", "ask", "deny")]


class TestNoArea:
    async def test_without_a_configured_area_nothing_runs(self, area_dir: Path) -> None:
        rig = Rig(
            None,
            script(
                call("c1", "escribir_archivo", path=str(area_dir / "x.txt"), content="x"),
                call("c2", "leer_archivo", path=str(area_dir / "src" / "pago.py")),
                call("c3", "listar_archivos", path=str(area_dir)),
                call("c4", "buscar_texto", path=str(area_dir), query="cobrar"),
            ),
        )

        result = await rig.go()

        assert result.status is TurnStatus.COMPLETED
        assert all(
            m.content.startswith("[approval_required_unavailable]") for m in tool_messages(result)
        )
        assert [d[1:] for d in rig.decisions()] == [("ask", "deny")] * 4
        assert not (area_dir / "x.txt").exists()
