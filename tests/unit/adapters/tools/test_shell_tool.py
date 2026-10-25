"""ShellTool: schema, risk, result format and cancellation (HU-01-04 / T012)."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.tools import ShellTool
from harness_agent.core import (
    AuthorizedArea,
    InMemoryToolRegistry,
    RiskLevel,
    Shell,
    ShellResult,
    ToolValidationError,
)
from harness_agent.core.tools import check_schema

SENTINEL = "VALOR-DE-PRUEBA-123"


class ScriptedShell(Shell):
    """Returns a scripted result (or raises), and remembers how it was called."""

    def __init__(self, result: ShellResult | Exception | None = None) -> None:
        self.result = result if result is not None else ShellResult(0, "hola\n")
        self.calls: list[tuple[str, float]] = []
        self.thread_ids: list[int] = []

    @property
    def interpreter_name(self) -> str:
        return "bash"

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        self.calls.append((command, timeout_seconds))
        self.thread_ids.append(threading.get_ident())
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeArea(AuthorizedArea):
    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def contains(self, path: Path | str) -> bool:
        return True


@pytest.fixture
def area(tmp_path: Path) -> FakeArea:
    return FakeArea(tmp_path)


def tool_for(shell: Shell, area: AuthorizedArea | None, on_cancel: Any = None) -> ShellTool:
    return ShellTool(shell, area, on_cancel)


class TestDefinition:
    def test_name_and_risk(self, area: FakeArea) -> None:
        tool = tool_for(ScriptedShell(), area)
        assert tool.name == "shell"
        assert tool.risk is RiskLevel.HIGH

    def test_the_description_names_the_interpreter_and_says_each_call_is_independent(
        self, area: FakeArea
    ) -> None:
        text = tool_for(ScriptedShell(), area).description
        assert "bash" in text
        assert "independiente" in text

    def test_the_description_without_a_shell_is_generic(self, area: FakeArea) -> None:
        assert "intérprete del sistema" in ShellTool(None, area).description

    def test_the_schema_is_valid_and_has_no_path(self, area: FakeArea) -> None:
        schema = tool_for(ScriptedShell(), area).schema
        check_schema(schema)
        assert set(schema["properties"]) == {"command", "timeout_seconds"}
        assert schema["required"] == ["command"]
        assert schema["additionalProperties"] is False

    def test_the_real_registry_accepts_it(self, area: FakeArea) -> None:
        registry = InMemoryToolRegistry()
        registry.register(tool_for(ScriptedShell(), area))
        assert registry.get("shell") is not None

    @pytest.mark.parametrize(
        "args",
        [
            {},
            {"command": ""},
            {"command": 5},
            {"command": "ls", "extra": 1},
            {"command": "ls", "timeout_seconds": 0},
            {"command": "ls", "timeout_seconds": 601},
            {"command": "ls", "timeout_seconds": "10"},
            {"command": "x" * 8001},
        ],
    )
    def test_the_registry_rejects_bad_arguments(self, area: FakeArea, args: dict[str, Any]) -> None:
        registry = InMemoryToolRegistry()
        registry.register(tool_for(ScriptedShell(), area))
        with pytest.raises(ToolValidationError):
            registry.validate_args("shell", args)

    def test_the_registry_accepts_good_arguments(self, area: FakeArea) -> None:
        registry = InMemoryToolRegistry()
        registry.register(tool_for(ScriptedShell(), area))
        registry.validate_args("shell", {"command": "ls", "timeout_seconds": 30})
        registry.validate_args("shell", {"command": "ls"})


class TestResults:
    async def test_success(self, area: FakeArea) -> None:
        result = await tool_for(ScriptedShell(ShellResult(0, "hola\n")), area).run(
            {"command": "echo hola"}
        )
        assert result.is_error is False
        assert result.content == "Código de salida: 0\nhola\n"

    async def test_empty_output(self, area: FakeArea) -> None:
        result = await tool_for(ScriptedShell(ShellResult(0, "")), area).run({"command": "true"})
        assert result.content == "Código de salida: 0\n(sin salida)"

    async def test_non_zero_exit_code(self, area: FakeArea) -> None:
        result = await tool_for(ScriptedShell(ShellResult(3, "fallo\n")), area).run(
            {"command": "exit 3"}
        )
        assert result.is_error is True
        assert result.content.startswith("[codigo_de_salida=3] El comando terminó con error.")
        assert "fallo" in result.content

    async def test_timeout_names_the_limit_and_keeps_the_partial_output(
        self, area: FakeArea
    ) -> None:
        shell = ScriptedShell(ShellResult(-9, "parcial\n", timed_out=True))
        result = await tool_for(shell, area).run({"command": "sleep 99", "timeout_seconds": 7})
        assert result.is_error is True
        assert result.content.startswith("[tiempo_agotado] El comando superó los 7 s")
        assert "parcial" in result.content

    async def test_start_failure_names_the_interpreter_only(self, area: FakeArea) -> None:
        shell = ScriptedShell(OSError(f"no se pudo {SENTINEL} /ruta/secreta"))
        result = await tool_for(shell, area).run({"command": "ls"})
        assert result.is_error is True
        assert result.content.startswith("[interprete_no_disponible]")
        assert "bash" in result.content
        assert SENTINEL not in result.content
        assert "/ruta/secreta" not in result.content

    async def test_any_other_exception_never_shows_its_text(self, area: FakeArea) -> None:
        shell = ScriptedShell(RuntimeError(SENTINEL))
        result = await tool_for(shell, area).run({"command": "ls"})
        assert result.is_error is True
        assert result.content.startswith("[error_de_shell]")
        assert SENTINEL not in result.content

    async def test_the_result_does_not_repeat_the_command(self, area: FakeArea) -> None:
        shell = ScriptedShell(ShellResult(0, "ok"))
        result = await tool_for(shell, area).run({"command": f"echo {SENTINEL}"})
        assert SENTINEL not in result.content

    async def test_an_output_over_the_limit_is_cut_again(self, area: FakeArea) -> None:
        shell = ScriptedShell(ShellResult(0, "x" * 50_000))
        result = await tool_for(shell, area).run({"command": "ls"})
        assert len(result.content) < 21_000

    @pytest.mark.parametrize(
        "args",
        [
            {},
            {"command": ""},
            {"command": "   "},
            {"command": 5},
            {"command": "ls", "timeout_seconds": 0},
        ],
    )
    async def test_arguments_the_registry_would_have_rejected_do_not_run(
        self, area: FakeArea, args: dict[str, Any]
    ) -> None:
        shell = ScriptedShell()
        result = await tool_for(shell, area).run(args)
        assert result.is_error is True
        assert result.content.startswith("[argumentos_invalidos]")
        assert shell.calls == []


class TestWithoutArea:
    async def test_no_area_means_no_command(self) -> None:
        shell = ScriptedShell()
        result = await tool_for(shell, None).run({"command": "ls"})
        assert result.is_error is True
        assert result.content.startswith("[sin_area]")
        assert shell.calls == []

    async def test_no_shell_means_no_command(self, area: FakeArea) -> None:
        result = await ShellTool(None, area).run({"command": "ls"})
        assert result.content.startswith("[sin_area]")


class TestTimeoutArgument:
    async def test_default_is_120(self, area: FakeArea) -> None:
        shell = ScriptedShell()
        await tool_for(shell, area).run({"command": "ls"})
        assert shell.calls == [("ls", 120.0)]

    async def test_it_is_capped_at_600(self, area: FakeArea) -> None:
        shell = ScriptedShell()
        await tool_for(shell, area).run({"command": "ls", "timeout_seconds": 5000})
        assert shell.calls == [("ls", 600.0)]

    async def test_a_given_value_is_used(self, area: FakeArea) -> None:
        shell = ScriptedShell()
        await tool_for(shell, area).run({"command": "ls", "timeout_seconds": 2.5})
        assert shell.calls == [("ls", 2.5)]


class TestThreadAndCancellation:
    async def test_the_command_runs_outside_the_loop_thread(self, area: FakeArea) -> None:
        shell = ScriptedShell()
        await tool_for(shell, area).run({"command": "ls"})
        assert shell.thread_ids[0] != threading.get_ident()

    async def test_cancelling_calls_the_hook_once_and_propagates(self, area: FakeArea) -> None:
        release = threading.Event()
        started = threading.Event()

        class Blocking(ScriptedShell):
            def execute(self, command: str, timeout_seconds: float) -> ShellResult:
                started.set()
                release.wait(10)
                return ShellResult(0, "")

        hooks: list[int] = []
        tool = tool_for(Blocking(), area, on_cancel=lambda: hooks.append(1))
        task = asyncio.create_task(tool.run({"command": "sleep 60"}))
        while not started.is_set():
            await asyncio.sleep(0.01)
        task.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
        assert hooks == [1]

    async def test_cancelling_without_a_hook_does_not_fail(self, area: FakeArea) -> None:
        release = threading.Event()
        started = threading.Event()

        class Blocking(ScriptedShell):
            def execute(self, command: str, timeout_seconds: float) -> ShellResult:
                started.set()
                release.wait(10)
                return ShellResult(0, "")

        task = asyncio.create_task(tool_for(Blocking(), area).run({"command": "sleep 60"}))
        while not started.is_set():
            await asyncio.sleep(0.01)
        task.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()

    async def test_a_failing_hook_does_not_replace_the_cancellation(self, area: FakeArea) -> None:
        release = threading.Event()
        started = threading.Event()

        class Blocking(ScriptedShell):
            def execute(self, command: str, timeout_seconds: float) -> ShellResult:
                started.set()
                release.wait(10)
                return ShellResult(0, "")

        def broken() -> None:
            raise RuntimeError(SENTINEL)

        task = asyncio.create_task(
            tool_for(Blocking(), area, on_cancel=broken).run({"command": "sleep 60"})
        )
        while not started.is_set():
            await asyncio.sleep(0.01)
        task.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            release.set()
