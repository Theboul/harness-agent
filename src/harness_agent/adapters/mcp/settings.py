"""How to reach one MCP server (HU-08-01).

``bootstrap.py`` builds this from the configuration; the adapter does not import ``config``.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_STARTUP_TIMEOUT_S = 15.0
DEFAULT_CALL_TIMEOUT_S = 60.0
DEFAULT_CLOSE_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class McpServerSettings:
    """The launch parameters and timeouts of one stdio server.

    Attributes:
        name: Name of the server in the configuration (shown in the notices).
        command: Executable to start.
        args: Arguments of the command.
        env_names: Names of the variables of the parent environment the server receives; it
            receives nothing else but the safe base the SDK adds (``PATH``, ``HOME``...).
        startup_timeout_s: Longest wait for the capability negotiation.
        call_timeout_s: Longest wait for one tool call.
        close_timeout_s: Longest wait for the server to stop before it is cancelled.
    """

    name: str
    command: str
    args: tuple[str, ...] = ()
    env_names: tuple[str, ...] = ()
    startup_timeout_s: float = DEFAULT_STARTUP_TIMEOUT_S
    call_timeout_s: float = DEFAULT_CALL_TIMEOUT_S
    close_timeout_s: float = DEFAULT_CLOSE_TIMEOUT_S
