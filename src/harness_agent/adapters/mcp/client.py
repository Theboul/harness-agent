"""The MCP client over stdio (HU-08-01): one server, one connection, one owner task.

The SDK opens ``stdio_client`` and ``ClientSession`` with cancel scopes that **must be left in the
same task that entered them** (SPK-04, section 5.3: leaving from another task raised
``RuntimeError`` after 98.8 s). The port ``McpClient`` has no ``close()``, so a background task
owns the connection: it opens everything, tells ``connect()`` it is ready, waits for a stop signal
and leaves everything itself. ``close()`` (a method of this class, not of the port) sets the
signal and awaits the task; if the server does not stop in time the task is cancelled, which also
leaves the contexts from the owner. No path leaves a server process behind.

Failures of the SDK arrive as exception groups: they are flattened and translated to domain
errors with fixed texts. Errors of a call are returned as results marked as errors and never carry
the text of the server (it can repeat the arguments it received).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from harness_agent.adapters.mcp.environment import server_environment
from harness_agent.adapters.mcp.errors import McpConnectError, McpError
from harness_agent.adapters.mcp.sdk import McpSdk, load_sdk
from harness_agent.adapters.mcp.settings import McpServerSettings
from harness_agent.adapters.mcp.stderr_log import open_stderr_log
from harness_agent.adapters.mcp.translate import CallFailure, classify_call, connect_error
from harness_agent.core import McpClient, Tool, ToolResult

SdkLoader = Callable[[str], McpSdk]

_STARTUP_GRACE_S = 5.0
_NO_CALL_ID = ""

_FAILURE_TEXTS = {
    CallFailure.TIMEOUT: "[mcp_timeout] El servidor MCP no respondió a tiempo a la llamada.",
    CallFailure.SERVER_DOWN: "[mcp_server_down] El servidor MCP dejó de responder.",
    CallFailure.ERROR: "[mcp_error] El servidor MCP devolvió un error al ejecutar la herramienta.",
}
_NOT_CONNECTED = "[mcp_not_connected] El servidor MCP no está conectado."

_CREATED = "created"
_CONNECTING = "connecting"
_CONNECTED = "connected"
_CLOSING = "closing"
_CLOSED = "closed"
_FAILED = "failed"


class McpStdioClient(McpClient):
    """An MCP server started as a subprocess and talked to over stdio.

    Args:
        settings: How to launch the server and the timeouts.
        environ: The environment of the parent; only the variables ``settings.env_names`` lists
            are passed on. Injected: this module does not read ``os.environ``.
        log_path: File that receives the stderr of the server; ``None`` or an unusable path sends
            it to the null device. It is never the terminal of the user.
        sdk_loader: Loads the SDK when ``connect`` runs; replaced by a double in the tests.
        startup_grace_s: Extra wait beyond ``startup_timeout_s`` before the start is given up,
            for a server that never gets to answer.
    """

    def __init__(
        self,
        settings: McpServerSettings,
        *,
        environ: Mapping[str, str],
        log_path: Path | None = None,
        sdk_loader: SdkLoader = load_sdk,
        startup_grace_s: float = _STARTUP_GRACE_S,
    ) -> None:
        self._settings = settings
        self._environ = environ
        self._log_path = log_path
        self._sdk_loader = sdk_loader
        self._startup_grace_s = startup_grace_s
        self._state = _CREATED
        self._task: asyncio.Task[None] | None = None
        self._ready: asyncio.Future[None] | None = None
        self._stop: asyncio.Event | None = None
        self._session: Any = None
        self._server_name: str | None = None
        self._has_tools = False
        self._text_content: Any = None

    @property
    def log_path(self) -> Path | None:
        """File that receives the stderr of the server (``None``: the null device)."""
        return self._log_path

    def environment_for_server(self) -> dict[str, str]:
        """The variables the server receives on top of the safe base of the SDK."""
        return server_environment(self._environ, self._settings.env_names)

    @property
    def connected(self) -> bool:
        """Whether the negotiation finished and the connection has not been closed."""
        return self._state == _CONNECTED

    @property
    def server_name(self) -> str | None:
        """Name the server announced when it negotiated; ``None`` until it is connected."""
        return self._server_name

    @property
    def has_tools(self) -> bool:
        """Whether the server announced the ``tools`` capability."""
        return self._has_tools

    async def connect(self) -> None:
        """Start the server, negotiate and return when the connection is ready.

        Raises:
            McpDependencyError: The ``mcp`` library is not installed.
            McpConnectError: The server could not be started or negotiated, or this client was
                already closed or has already failed (it does not reconnect by itself).
            asyncio.CancelledError: The caller was cancelled; the owner task is cancelled too.
        """
        if self._state == _CONNECTED:
            return
        if self._state != _CREATED:
            raise McpConnectError(self._settings.name, "fallo")
        try:
            sdk = self._sdk_loader(self._settings.name)
        except McpError:
            self._state = _FAILED
            raise
        loop = asyncio.get_running_loop()
        self._ready = loop.create_future()
        self._stop = asyncio.Event()
        self._state = _CONNECTING
        self._task = asyncio.create_task(self._own(sdk), name=f"mcp-{self._settings.name}")
        wait = self._settings.startup_timeout_s + self._startup_grace_s
        try:
            await asyncio.wait({self._ready}, timeout=wait)
        except asyncio.CancelledError:
            self._state = _CLOSED
            await self._stop_task(cancel=True)
            raise
        if not self._ready.done():
            self._state = _FAILED
            await self._stop_task(cancel=True)
            raise McpConnectError(self._settings.name, "sin_respuesta")
        failure = None if self._ready.cancelled() else self._ready.exception()
        if self._ready.cancelled() or failure is not None:
            self._state = _FAILED
            await self._stop_task(cancel=False)
            if failure is None:
                raise McpConnectError(self._settings.name, "fallo")
            raise failure

    async def close(self) -> None:
        """Stop the server and wait until its process is gone; safe to call more than once."""
        if self._state in (_CLOSED, _CLOSING):
            return
        was_connected = self._state == _CONNECTED
        self._state = _CLOSING
        if self._task is not None:
            await self._stop_task(cancel=not was_connected)
        self._state = _CLOSED

    async def list_tools(self) -> list[Tool]:
        """Seam for HU-08-02 (discover and translate the tools): nothing is registered yet."""
        return []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Run a tool; failures come back as results with ``is_error`` and a fixed text."""
        session = self._session
        if self._state != _CONNECTED or session is None:
            return ToolResult(_NO_CALL_ID, _NOT_CONNECTED, is_error=True)
        try:
            outcome = await session.call_tool(
                name, dict(arguments), read_timeout_seconds=self._settings.call_timeout_s
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            return ToolResult(_NO_CALL_ID, _FAILURE_TEXTS[classify_call(error)], is_error=True)
        blocks = getattr(outcome, "content", None)
        if blocks is None or getattr(outcome, "is_error", False):
            return ToolResult(_NO_CALL_ID, _FAILURE_TEXTS[CallFailure.ERROR], is_error=True)
        text = "\n".join(block.text for block in blocks if isinstance(block, self._text_content))
        return ToolResult(_NO_CALL_ID, text)

    async def _own(self, sdk: McpSdk) -> None:
        """The owner task: open, announce, wait for the stop signal, leave; all in this task."""
        assert self._ready is not None and self._stop is not None
        errlog = open_stderr_log(self._log_path)
        try:
            parameters = sdk.server_parameters(
                command=self._settings.command,
                args=list(self._settings.args),
                env=self.environment_for_server(),
            )
            async with sdk.stdio_client(parameters, errlog=errlog) as (read, write):
                async with sdk.client_session(
                    read, write, read_timeout_seconds=self._settings.startup_timeout_s
                ) as session:
                    negotiated = await session.initialize()
                    self._text_content = sdk.text_content
                    self._server_name = negotiated.server_info.name
                    self._has_tools = negotiated.capabilities.tools is not None
                    self._session = session
                    self._state = _CONNECTED
                    self._ready.set_result(None)
                    await self._stop.wait()
        except asyncio.CancelledError:
            if not self._ready.done():
                self._ready.cancel()
            raise
        except Exception as error:
            if not self._ready.done():
                self._ready.set_exception(connect_error(self._settings.name, error))
            # After the negotiation a failure is the server going away: close() does not report
            # it (HU-08-04 decides what to do with a server that is lost).
        finally:
            self._session = None
            errlog.close()

    async def _stop_task(self, *, cancel: bool) -> None:
        """Make the owner task finish, escalating to a cancellation after the close timeout."""
        task, stop = self._task, self._stop
        if task is None or stop is None:
            return
        timeout = self._settings.close_timeout_s
        try:
            if cancel and not task.done():
                task.cancel()
            else:
                stop.set()
            await asyncio.wait({task}, timeout=timeout)
            if not task.done():
                task.cancel()
                await asyncio.wait({task}, timeout=timeout)
        except asyncio.CancelledError:
            task.cancel()
            raise
        finally:
            if task.done() and not task.cancelled():
                task.exception()  # mark it as retrieved: a late failure is not reported twice
