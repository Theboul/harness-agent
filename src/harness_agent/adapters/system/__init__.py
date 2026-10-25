"""System adapters: the authorized area on disk (HU-01-03) and the shells (HU-01-04).

``select_shell`` returns the shell that fits the operating system; ``environment_notice`` is the
text that tells the model which one it is talking to. The rest of the modules are internal.
"""

from harness_agent.adapters.system.bash_shell import BashShell
from harness_agent.adapters.system.denied_commands import (
    DEFAULT_DENIED_COMMANDS,
    DeniedCommand,
    denied_commands_for,
)
from harness_agent.adapters.system.environment_notice import environment_notice
from harness_agent.adapters.system.powershell_shell import PowerShellShell
from harness_agent.adapters.system.shell_errors import ShellStartError
from harness_agent.adapters.system.shell_selection import interpreter_for, select_shell
from harness_agent.adapters.system.subprocess_shell import SubprocessShell
from harness_agent.adapters.system.workspace_area import WorkspaceArea, windows_path_problem

__all__ = [
    "BashShell",
    "DEFAULT_DENIED_COMMANDS",
    "DeniedCommand",
    "PowerShellShell",
    "ShellStartError",
    "SubprocessShell",
    "WorkspaceArea",
    "denied_commands_for",
    "environment_notice",
    "interpreter_for",
    "select_shell",
    "windows_path_problem",
]
