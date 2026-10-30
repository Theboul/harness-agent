"""Connect and close of ``McpStdioClient`` with a double of the SDK (HU-08-01, FR-001 to 004)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from harness_agent.adapters.mcp import McpConnectError, McpDependencyError, McpServerSettings
from harness_agent.adapters.mcp.client import McpStdioClient
from tests.unit.adapters.mcp.fake_sdk import FakeSdk, Script

SETTINGS = McpServerSettings(
    name="demo",
    command="servidor",
    args=("--uno",),
    env_names=("EXTRA",),
    startup_timeout_s=0.2,
    close_timeout_s=0.2,
)
ENVIRON = {"EXTRA": "uno", "ANTHROPIC_API_" + "KEY": "dos"}


def make(fake: FakeSdk, **options: object) -> McpStdioClient:
    return McpStdioClient(
        SETTINGS,
        environ=ENVIRON,
        sdk_loader=fake.loader,
        **options,  # type: ignore[arg-type]
    )


class TestConnect:
    async def test_it_negotiates_and_the_client_is_connected(self) -> None:
        fake = FakeSdk()
        client = make(fake)

        await client.connect()

        assert client.connected
        assert client.server_name == "fake-server"
        assert client.has_tools is True
        assert [name for name, _ in fake.events] == ["enter-stdio", "enter-session", "initialize"]
        await client.close()

    async def test_the_server_gets_its_command_arguments_and_only_the_named_environment(
        self,
    ) -> None:
        fake = FakeSdk()
        client = make(fake)

        await client.connect()

        (params,) = fake.launched
        assert params.command == "servidor"
        assert params.args == ["--uno"]
        assert params.env == {"EXTRA": "uno"}
        await client.close()

    async def test_connecting_twice_does_nothing_the_second_time(self) -> None:
        fake = FakeSdk()
        client = make(fake)
        await client.connect()

        await client.connect()

        assert fake.names("enter-stdio") == fake.names("enter-stdio")[:1]
        assert len(fake.launched) == 1
        await client.close()

    async def test_the_stderr_goes_to_a_log_file_and_not_to_the_terminal(
        self, tmp_path: Path
    ) -> None:
        fake = FakeSdk()
        log = tmp_path / "mcp-demo.log"
        client = make(fake, log_path=log)

        await client.connect()
        await client.close()

        (errlog,) = fake.errlogs
        assert errlog.name == str(log)
        assert errlog.closed
        assert log.exists()

    async def test_without_a_usable_log_path_the_stderr_goes_to_the_null_device(
        self, tmp_path: Path
    ) -> None:
        import os

        fake = FakeSdk()
        client = make(fake, log_path=tmp_path)  # a folder: it cannot be opened as a file

        await client.connect()
        await client.close()

        assert fake.errlogs[0].name == os.devnull


class TestSameTask:
    async def test_every_context_is_entered_and_left_in_the_same_background_task(self) -> None:
        fake = FakeSdk()
        client = make(fake)
        caller = asyncio.current_task()
        assert caller is not None

        await client.connect()
        await client.close()

        owners = {task for _, task in fake.events}
        assert len(owners) == 1
        assert owners != {caller.get_name()}

    async def test_it_can_be_closed_from_another_task(self) -> None:
        fake = FakeSdk()
        client = make(fake)
        await client.connect()

        await asyncio.create_task(client.close(), name="otra-tarea")

        assert fake.names("exit-stdio") == fake.names("enter-stdio")
        assert not client.connected


class TestFailures:
    @pytest.mark.parametrize(
        ("script", "code"),
        [
            (Script(spawn_error=FileNotFoundError("no-such")), "no_se_pudo_iniciar"),
            (
                Script(
                    initialize_error=ExceptionGroup("g", [ConnectionError("Connection closed")])
                ),
                "cerro_al_arrancar",
            ),
            (Script(initialize_error=RuntimeError("otra cosa")), "fallo"),
        ],
    )
    async def test_a_failure_to_start_is_a_domain_error_and_nothing_stays_open(
        self, script: Script, code: str
    ) -> None:
        fake = FakeSdk(script)
        client = make(fake)

        with pytest.raises(McpConnectError) as raised:
            await client.connect()

        assert raised.value.code == code
        assert not client.connected
        assert fake.names("exit-stdio") == fake.names("enter-stdio") or not fake.names("exit-stdio")

    async def test_a_server_that_does_not_answer_in_time_is_a_timeout(self) -> None:
        fake = FakeSdk(Script(initialize_hang=True))
        client = make(fake, startup_grace_s=0.0)

        with pytest.raises(McpConnectError) as raised:
            await client.connect()

        assert raised.value.code == "sin_respuesta"
        assert fake.names("exit-stdio")  # the owner task was cancelled and left its contexts

    async def test_a_missing_library_is_a_dependency_error(self) -> None:
        def loader(server: str = "") -> object:
            raise McpDependencyError(server)

        client = McpStdioClient(SETTINGS, environ=ENVIRON, sdk_loader=loader)  # type: ignore[arg-type]

        with pytest.raises(McpDependencyError):
            await client.connect()

    async def test_a_failed_client_does_not_connect_again_by_itself(self) -> None:
        fake = FakeSdk(Script(spawn_error=FileNotFoundError("x")))
        client = make(fake)
        with pytest.raises(McpConnectError):
            await client.connect()

        with pytest.raises(McpConnectError):
            await client.connect()

        assert len(fake.launched) == 1

    async def test_cancelling_the_wait_cancels_the_owner_task_and_leaves_nothing_open(self) -> None:
        fake = FakeSdk(Script(initialize_hang=True))
        client = make(fake)
        waiting = asyncio.create_task(client.connect())
        for _ in range(50):
            if fake.names("initialize"):
                break
            await asyncio.sleep(0.01)
        assert fake.names("initialize")

        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting

        assert fake.names("exit-stdio")
        assert not client.connected


class TestClose:
    async def test_closing_while_connecting_fails_the_connect_and_leaves_nothing_open(self) -> None:
        fake = FakeSdk(Script(initialize_hang=True))
        client = make(fake)
        connecting = asyncio.create_task(client.connect())
        for _ in range(50):
            if fake.names("initialize"):
                break
            await asyncio.sleep(0.01)

        await client.close()

        with pytest.raises(McpConnectError):
            await connecting
        assert fake.names("exit-stdio")
        assert not client.connected

    async def test_closing_without_connecting_is_harmless_and_connect_is_then_refused(self) -> None:
        client = make(FakeSdk())

        await client.close()
        with pytest.raises(McpConnectError):
            await client.connect()

    async def test_closing_twice_is_harmless(self) -> None:
        fake = FakeSdk()
        client = make(fake)
        await client.connect()

        await client.close()
        await client.close()

        assert len(fake.names("exit-stdio")) == 1

    async def test_a_server_that_fails_while_stopping_does_not_make_close_fail(self) -> None:
        fake = FakeSdk(
            Script(exit_error=ExceptionGroup("g", [ConnectionError("Connection closed")]))
        )
        client = make(fake)
        await client.connect()

        await client.close()

        assert not client.connected

    async def test_a_server_that_never_stops_is_cancelled_after_the_close_timeout(self) -> None:
        fake = FakeSdk(Script(exit_hang=True))
        client = make(fake)
        await client.connect()

        await asyncio.wait_for(client.close(), timeout=5)

        assert not client.connected

    async def test_cancelling_a_close_in_progress_still_cancels_the_owner(self) -> None:
        fake = FakeSdk(Script(exit_hang=True))
        client = McpStdioClient(
            McpServerSettings(name="demo", command="x", close_timeout_s=30),
            environ=ENVIRON,
            sdk_loader=fake.loader,
        )
        await client.connect()
        closing = asyncio.create_task(client.close())
        await asyncio.sleep(0.05)

        closing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await closing
        await asyncio.sleep(0.05)

        assert fake.names("exit-session")
