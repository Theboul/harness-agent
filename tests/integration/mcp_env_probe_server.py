"""A tiny MCP server for the integration tests of HU-08-01 (test support, not production code).

It reports what the client gave it: the names of its environment, and its process id. Through
two environment variables it can also leave its pid in a file as soon as it starts and wait
before it begins to serve, so a test can act while the negotiation is still pending.
"""

from __future__ import annotations

import os
import sys
import time

from mcp.server.mcpserver import MCPServer

STARTED_MARK = "mcp-env-probe-started"

server = MCPServer("harness-env-probe")


@server.tool()
def env_names() -> str:
    """The names of the environment variables of the server process, comma separated."""
    return ",".join(sorted(os.environ))


@server.tool()
def pid() -> int:
    """The process id of the server."""
    return os.getpid()


if __name__ == "__main__":
    sys.stderr.write(STARTED_MARK + "\n")
    sys.stderr.flush()
    pid_file = os.environ.get("PROBE_PID_FILE")
    if pid_file:
        with open(pid_file, "w", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
    delay = os.environ.get("PROBE_STARTUP_DELAY")
    if delay:
        time.sleep(float(delay))
    server.run("stdio")
