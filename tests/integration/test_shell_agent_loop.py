"""The ``shell`` tool with the real loop, registry, policy and the native shell (HU-01-04 / T015).

Commands are valid in bash and in PowerShell (``echo``, redirection, a sleep), so the same tests run
on Linux and on Windows. The provider is a ``FakeProvider``; nothing touches the network.
"""

from __future__ import annotations

import asyncio
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.system import (
    WorkspaceArea,
    environment_notice,
    interpreter_for,
    select_shell,
)
from harness_agent.adapters.tools import ShellTool
from harness_agent.config import process_environment
from harness_agent.core import (
    DefaultPermissionPolicy,
    InMemoryEventBus,
    InMemoryToolRegistry,
    Message,
    PermissionDecision,
    ProviderResponse,
    Role,
    ToolCall,
)
from harness_agent.core.loop import AgentLoop
from tests.doubles import FakeProvider
from tests.doubles.scripted_policy import ScriptedPolicy

SYSTEM = platform.system()
HANG = "Start-Sleep -Seconds 60" if SYSTEM == "Windows" else "sleep 60"


def shell_call(call_id: str, **arguments: Any) -> ToolCall:
    return ToolCall(id=call_id, name="shell", arguments=arguments)


class Rig:
    def __init__(self, tmp_path: Path, policy: Any, script: list[ProviderResponse]) -> None:
        self.area = WorkspaceArea(tmp_path)
        self.shell = select_shell(SYSTEM, cwd=self.area.root, environ=process_environment())
        self.tool = ShellTool(self.shell, self.area, on_cancel=self.shell.terminate_running)
        self.registry = InMemoryToolRegistry()
        self.registry.register(self.tool)
        self.provider = FakeProvider(script)
        chosen = policy(self.registry, self.area) if callable(policy) else policy
        self.loop = AgentLoop(self.provider, self.registry, chosen, InMemoryEventBus())

    def tool_answers(self) -> list[str]:
        return [m.content for m in self.provider.received[-1] if m.role is Role.TOOL]

    async def turn(self, history: list[Message] | None = None) -> None:
        await self.loop.run_turn(
            session_id="sesion", task="haz algo", history=history if history is not None else []
        )


def allowing() -> ScriptedPolicy:
    return ScriptedPolicy({"shell": PermissionDecision.ALLOW})


def real_policy(registry: InMemoryToolRegistry, area: WorkspaceArea) -> DefaultPermissionPolicy:
    return DefaultPermissionPolicy(registry, area)


async def test_with_the_real_policy_and_no_approver_the_call_is_denied_and_nothing_runs(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "marcador.txt"
    script = [
        ProviderResponse(tool_calls=[shell_call("c1", command=f"echo creado > {marker.name}")]),
        ProviderResponse(content="listo"),
    ]
    rig = Rig(tmp_path, real_policy, script)

    await rig.turn()

    assert any("approval_required_unavailable" in answer for answer in rig.tool_answers())
    assert not marker.exists()


async def test_an_allowed_echo_returns_its_output_and_code_zero(tmp_path: Path) -> None:
    script = [
        ProviderResponse(tool_calls=[shell_call("c1", command="echo hola-desde-el-shell")]),
        ProviderResponse(content="listo"),
    ]
    rig = Rig(tmp_path, allowing(), script)

    await rig.turn()

    (answer,) = rig.tool_answers()
    assert answer.startswith("Código de salida: 0")
    assert "hola-desde-el-shell" in answer


async def test_a_failing_command_comes_back_marked(tmp_path: Path) -> None:
    script = [
        ProviderResponse(tool_calls=[shell_call("c1", command="exit 3")]),
        ProviderResponse(content="listo"),
    ]
    rig = Rig(tmp_path, allowing(), script)

    await rig.turn()

    (answer,) = rig.tool_answers()
    assert answer.startswith("[codigo_de_salida=3]")


async def test_a_command_that_hangs_comes_back_as_a_timeout(tmp_path: Path) -> None:
    script = [
        ProviderResponse(tool_calls=[shell_call("c1", command=HANG, timeout_seconds=1)]),
        ProviderResponse(content="listo"),
    ]
    rig = Rig(tmp_path, allowing(), script)
    started = time.monotonic()

    await rig.turn()

    (answer,) = rig.tool_answers()
    assert answer.startswith("[tiempo_agotado]")
    assert time.monotonic() - started < 30


async def test_the_environment_notice_is_a_valid_start_of_the_history(tmp_path: Path) -> None:
    notice = Message(role=Role.SYSTEM, content=environment_notice(SYSTEM, interpreter_for(SYSTEM)))
    rig = Rig(tmp_path, allowing(), [ProviderResponse(content="hola")])

    await rig.turn(history=[notice])

    first_call = rig.provider.received[0]
    assert first_call[0] == notice
    assert first_call[-1].role is Role.USER


async def test_the_shell_starts_in_the_work_folder(tmp_path: Path) -> None:
    (tmp_path / "presente.txt").write_text("x", encoding="utf-8")
    listing = "Get-ChildItem -Name" if SYSTEM == "Windows" else "ls"
    script = [
        ProviderResponse(tool_calls=[shell_call("c1", command=listing)]),
        ProviderResponse(content="listo"),
    ]
    rig = Rig(tmp_path, allowing(), script)

    await rig.turn()

    assert "presente.txt" in rig.tool_answers()[0]


async def test_cancelling_the_turn_ends_the_running_command_quickly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[subprocess.Popen[bytes]] = []
    real_popen = subprocess.Popen

    def spy(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        process: subprocess.Popen[bytes] = real_popen(*args, **kwargs)
        started.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", spy)
    script = [
        ProviderResponse(tool_calls=[shell_call("c1", command=HANG, timeout_seconds=600)]),
        ProviderResponse(content="no se llega"),
    ]
    rig = Rig(tmp_path, allowing(), script)
    task = asyncio.create_task(rig.turn())
    deadline = time.monotonic() + 30
    while not started and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    assert started, "the command never started"
    await asyncio.sleep(0.5)
    begin = time.monotonic()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert time.monotonic() - begin < 10
    deadline = time.monotonic() + 15
    while started[0].poll() is None and time.monotonic() < deadline:
        await asyncio.sleep(0.1)
    assert started[0].poll() is not None, "the command survived the cancellation"
