"""``ShellTool`` hides the credentials of URLs in the output for the model (HU-11-02 / T005).

The shell is a scripted double: nothing runs. In the three branches of ``ShellTool.run`` (exit code
0, an error code and a timeout) the ``ToolResult`` keeps neither the user nor the secret of a URL.
Through the real loop, no published event carries them either. The test secrets are built in
pieces so that no literal has the shape of a key.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.adapters.tools import ShellTool
from harness_agent.core import (
    HIDDEN_SECRET,
    InMemoryToolRegistry,
    PermissionDecision,
    ProviderResponse,
    ShellResult,
    ToolCall,
)
from harness_agent.core.loop import AgentLoop
from tests.doubles import FakeProvider, RecordingEventBus, ScriptedPolicy
from tests.unit.adapters.tools.test_shell_tool import FakeArea, ScriptedShell

USER = "usuario" + "-de-prueba"
SECRET = "secreto" + "-de-prueba"
OUTPUT = f"To https://{USER}:{SECRET}@servidor.example/repo.git\n   abc..def  main -> main\n"


@pytest.mark.parametrize(
    "result",
    [
        ShellResult(0, OUTPUT),
        ShellResult(1, OUTPUT),
        ShellResult(-1, OUTPUT, timed_out=True),
    ],
    ids=["exito", "error", "tiempo_agotado"],
)
async def test_the_result_hides_the_credentials(tmp_path: Path, result: ShellResult) -> None:
    tool = ShellTool(ScriptedShell(result), FakeArea(tmp_path))

    outcome = await tool.run({"command": "git push"})

    assert USER not in outcome.content and SECRET not in outcome.content
    assert f"https://{HIDDEN_SECRET}@servidor.example/repo.git" in outcome.content


async def test_an_output_without_credentials_does_not_change(tmp_path: Path) -> None:
    tool = ShellTool(ScriptedShell(ShellResult(0, "On branch main\n")), FakeArea(tmp_path))

    outcome = await tool.run({"command": "git status"})

    assert outcome.content == "Código de salida: 0\nOn branch main\n"


async def test_no_event_of_the_loop_carries_the_credentials(tmp_path: Path) -> None:
    registry = InMemoryToolRegistry()
    registry.register(ShellTool(ScriptedShell(ShellResult(0, OUTPUT)), FakeArea(tmp_path)))
    bus = RecordingEventBus()
    provider = FakeProvider(
        [
            ProviderResponse(
                tool_calls=[ToolCall(id="c1", name="shell", arguments={"command": "git push"})]
            ),
            ProviderResponse(content="listo"),
        ]
    )
    loop = AgentLoop(provider, registry, ScriptedPolicy({"shell": PermissionDecision.ALLOW}), bus)

    result = await loop.run_turn(session_id="s", task="sube", history=[])

    assert bus.emitted_events
    assert all(SECRET not in repr(event.payload) for event in bus.emitted_events)
    assert all(USER not in repr(event.payload) for event in bus.emitted_events)
    tool_messages = [m.content for m in result.history if m.role.value == "tool"]
    assert tool_messages and all(SECRET not in str(m) for m in tool_messages)
