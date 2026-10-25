"""General limit for tool output with the real loop and the real tools (HU-02-02 / T007, T008).

The registry serves every tool bounded; the loop, which only calls ``registry.get`` and ``run``,
brings the cut result into the history. The tools keep their own bounds: the worst result they
produce today must go through the registry untouched, with a single notice.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.system.shell_output import OutputCollector
from harness_agent.adapters.tools import ListFilesTool, ReadFileTool, SearchTextTool, ShellTool
from harness_agent.adapters.tools._limits import MAX_RESULT_CHARS
from harness_agent.adapters.tools._paths import bounded_text
from harness_agent.core import (
    DEFAULT_MAX_OUTPUT_CHARS,
    Event,
    EventType,
    InMemoryEventBus,
    InMemoryToolRegistry,
    Message,
    PermissionDecision,
    ProviderResponse,
    Role,
    Shell,
    ShellResult,
    ToolCall,
    ToolResult,
    omission_notice,
)
from harness_agent.core.interfaces.tool import RiskLevel
from harness_agent.core.loop import AgentLoop
from tests.doubles import FakeProvider
from tests.doubles.dummy_tool import DummyTool
from tests.doubles.scripted_policy import ScriptedPolicy

NOTICE_PATTERN = re.compile(r"\[salida recortada: se omitieron (\d+) caracteres\]")
SHELL_BODY = 20_000  # MAX_OUTPUT_CHARS of the shell adapter


class FixedShell(Shell):
    def __init__(self, result: ShellResult) -> None:
        self._result = result

    @property
    def interpreter_name(self) -> str:
        return "bash"

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        return self._result


def shell_bounded(size: int) -> str:
    """What the shell adapter hands over for ``size`` characters of output."""
    collector = OutputCollector()
    collector.feed(("0123456789" * (size // 10 + 1))[:size].encode())
    return collector.finish()


def notices_in(text: str) -> list[int]:
    return [int(found) for found in NOTICE_PATTERN.findall(text)]


def assert_exact_cut(cut: str, original: str, maximum: int) -> None:
    """``cut`` keeps the beginning and the end of ``original`` and announces what is missing."""
    (omitted,) = notices_in(cut)
    head, tail = cut.split(omission_notice(omitted))
    assert original.startswith(head)
    assert original.endswith(tail)
    assert len(original) - len(head) - len(tail) == omitted
    assert len(cut) <= maximum


async def serve(registry: InMemoryToolRegistry, name: str, args: dict[str, Any]) -> ToolResult:
    tool = registry.get(name)
    assert tool is not None
    return await tool.run(args)


# ----------------------------------------------------------------- T007: coexistence


async def pass_through_registry(result: ShellResult) -> tuple[ToolResult, ToolResult]:
    """The result of the shell tool alone and the one served by a registry with the default."""
    area = WorkspaceArea(Path.cwd())
    direct = await ShellTool(FixedShell(result), area).run({"command": "x"})
    registry = InMemoryToolRegistry(max_output_chars=DEFAULT_MAX_OUTPUT_CHARS)
    registry.register(ShellTool(FixedShell(result), area))
    return direct, await serve(registry, "shell", {"command": "x"})


@pytest.mark.parametrize(
    "result_of",
    [
        lambda body: ShellResult(0, body),
        lambda body: ShellResult(137, body),
        lambda body: ShellResult(0, body, timed_out=True),
    ],
    ids=["exito", "error", "tiempo_agotado"],
)
async def test_the_longest_body_plus_the_header_of_the_shell_fits_the_default_untouched(
    result_of: Any,
) -> None:
    body = "a" * SHELL_BODY  # the longest output the shell adapter lets through uncut

    direct, served = await pass_through_registry(result_of(body))

    assert len(direct.content) > SHELL_BODY  # the header goes on top of the bounded body
    assert served.content == direct.content
    assert served.is_error == direct.is_error
    assert "salida recortada" not in served.content


async def test_an_output_already_cut_by_the_shell_keeps_its_single_notice() -> None:
    raw = shell_bounded(500_000)
    assert len(notices_in(raw)) == 1

    direct, served = await pass_through_registry(ShellResult(1, raw))

    assert served.content == direct.content
    assert len(notices_in(served.content)) == 1


async def test_the_worst_result_of_the_file_tools_goes_through_untouched() -> None:
    text = bounded_text("línea\n" * 10_000)
    assert len(text) == MAX_RESULT_CHARS
    registry = InMemoryToolRegistry(max_output_chars=DEFAULT_MAX_OUTPUT_CHARS)
    registry.register(DummyTool(name="tope", canned_result=ToolResult("c1", text)))

    served = await serve(registry, "tope", {})

    assert served.content == text
    assert "salida recortada" not in served.content


async def test_a_lower_maximum_cuts_again_and_the_new_notice_is_exact() -> None:
    raw = shell_bounded(500_000)
    area = WorkspaceArea(Path.cwd())
    registry = InMemoryToolRegistry(max_output_chars=1_000)
    registry.register(ShellTool(FixedShell(ShellResult(1, raw)), area))
    direct = await ShellTool(FixedShell(ShellResult(1, raw)), area).run({"command": "x"})

    served = await serve(registry, "shell", {"command": "x"})

    assert len(served.content) <= 1_000
    assert served.is_error is True
    assert served.content.startswith("[codigo_de_salida=1]")
    # The newest notice is the last one; the count refers to the text the registry received.
    assert notices_in(served.content)[-1] == len(direct.content) - (
        len(served.content) - len(omission_notice(notices_in(served.content)[-1]))
    )


async def test_the_read_tool_is_bounded_by_the_registry(tmp_path: Path) -> None:
    (tmp_path / "grande.txt").write_text("a" * 100_000 + "FIN", encoding="utf-8", newline="")
    area = WorkspaceArea(tmp_path)
    registry = InMemoryToolRegistry(max_output_chars=DEFAULT_MAX_OUTPUT_CHARS)
    registry.register(ReadFileTool(area))
    registry.register(ListFilesTool(area))
    registry.register(SearchTextTool(area))

    read = await serve(registry, "leer_archivo", {"path": "grande.txt"})
    listing = await serve(registry, "listar_archivos", {"path": "."})

    assert len(read.content) <= DEFAULT_MAX_OUTPUT_CHARS
    assert read.content.endswith("FIN")
    assert len(notices_in(read.content)) == 1
    assert "salida recortada" not in listing.content


# ----------------------------------------------------- T008: a huge output, real loop


class Rig:
    def __init__(self, tools: list[DummyTool], maximum: int, calls: list[ToolCall]) -> None:
        self.registry = InMemoryToolRegistry(max_output_chars=maximum)
        for tool in tools:
            self.registry.register(tool)
        self.provider = FakeProvider(
            [ProviderResponse(tool_calls=calls), ProviderResponse(content="listo")]
        )
        self.bus = InMemoryEventBus()
        self.events: list[Event] = []
        for event_type in EventType:
            self.bus.subscribe(event_type, self.events.append)
        policy = ScriptedPolicy({tool.name: PermissionDecision.ALLOW for tool in tools})
        self.loop = AgentLoop(self.provider, self.registry, policy, self.bus)

    async def turn(self) -> list[Message]:
        result = await self.loop.run_turn(session_id="sesion", task="haz algo", history=[])
        return [m for m in result.history if m.role is Role.TOOL]


def huge_tool(name: str, content: str, *, is_error: bool = False) -> DummyTool:
    return DummyTool(
        name=name,
        risk=RiskLevel.LOW,
        canned_result=ToolResult(call_id="otro", content=content, is_error=is_error),
    )


async def test_ten_times_the_maximum_enters_the_history_cut_and_with_an_exact_notice() -> None:
    maximum = 2_000
    original = "INICIO" + "m" * (10 * maximum) + "FINAL"
    rig = Rig([huge_tool("enorme", original)], maximum, [ToolCall("c1", "enorme", {})])

    (message,) = await rig.turn()

    assert message.tool_result is not None
    assert message.tool_result.call_id == "c1"
    assert message.content == message.tool_result.content
    assert message.content.startswith("INICIO")
    assert message.content.endswith("FINAL")
    assert_exact_cut(message.content, original, maximum)


async def test_the_events_of_the_loop_do_not_carry_the_output() -> None:
    original = "VALOR-DE-PRUEBA-123" + "z" * 50_000
    rig = Rig([huge_tool("enorme", original)], 1_000, [ToolCall("c1", "enorme", {})])

    await rig.turn()

    assert rig.events
    assert "VALOR-DE-PRUEBA-123" not in repr([event.payload for event in rig.events])


async def test_an_error_result_stays_an_error_after_the_cut() -> None:
    original = "[fallo] " + "e" * 20_000
    rig = Rig([huge_tool("falla", original, is_error=True)], 1_000, [ToolCall("c1", "falla", {})])

    (message,) = await rig.turn()

    assert message.tool_result is not None
    assert message.tool_result.is_error is True
    assert message.content.startswith("[fallo] ")
    assert_exact_cut(message.content, original, 1_000)


async def test_a_short_output_enters_the_history_identical() -> None:
    rig = Rig([huge_tool("corta", "listo y breve")], 1_000, [ToolCall("c1", "corta", {})])

    (message,) = await rig.turn()

    assert message.content == "listo y breve"


async def test_two_calls_in_one_turn_are_cut_separately() -> None:
    first = "A" * 9_000 + "fin-a"
    second = "B" * 7_000 + "fin-b"
    rig = Rig(
        [huge_tool("uno", first), huge_tool("dos", second)],
        1_000,
        [ToolCall("c1", "uno", {}), ToolCall("c2", "dos", {})],
    )

    messages = await rig.turn()

    by_id = {m.tool_result.call_id: m.content for m in messages if m.tool_result is not None}
    assert_exact_cut(by_id["c1"], first, 1_000)
    assert_exact_cut(by_id["c2"], second, 1_000)


@pytest.mark.parametrize("maximum", [256, 24_000])
async def test_the_cut_never_exceeds_the_maximum(maximum: int) -> None:
    original = "x" * (10 * maximum)
    rig = Rig([huge_tool("enorme", original)], maximum, [ToolCall("c1", "enorme", {})])

    (message,) = await rig.turn()

    assert_exact_cut(message.content, original, maximum)
