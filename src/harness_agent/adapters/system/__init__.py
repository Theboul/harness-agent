"""System adapters: the authorized area (HU-01-03), the shells (HU-01-04), protected paths.

``select_shell`` returns the shell that fits the operating system; ``environment_notice`` is the
text that tells the model which one it is talking to. The rest of the modules are internal.
"""

from harness_agent.adapters.system.bash_shell import BashShell
from harness_agent.adapters.system.denied_commands import (
    DEFAULT_DENIED_COMMANDS,
    OPTION_SYNONYMS,
    PROGRAM_ALIASES,
    DeniedCommand,
    denied_commands_for,
    option_synonyms_for,
    program_aliases_for,
)
from harness_agent.adapters.system.dotenv import (
    MAX_DOTENV_BYTES,
    DotenvResult,
    merge_environment,
    parse_dotenv,
    read_dotenv,
)
from harness_agent.adapters.system.environment_notice import environment_notice
from harness_agent.adapters.system.git_changes import GitChanges
from harness_agent.adapters.system.github_pull_requests import GitHubPullRequests, ProcessResult
from harness_agent.adapters.system.powershell_shell import PowerShellShell
from harness_agent.adapters.system.protected_paths import ProtectedPaths
from harness_agent.adapters.system.shell_errors import ShellStartError
from harness_agent.adapters.system.shell_selection import interpreter_for, select_shell
from harness_agent.adapters.system.subprocess_shell import SubprocessShell
from harness_agent.adapters.system.workspace_area import WorkspaceArea, windows_path_problem

__all__ = [
    "BashShell",
    "DEFAULT_DENIED_COMMANDS",
    "DeniedCommand",
    "DotenvResult",
    "GitChanges",
    "GitHubPullRequests",
    "ProcessResult",
    "MAX_DOTENV_BYTES",
    "OPTION_SYNONYMS",
    "PROGRAM_ALIASES",
    "PowerShellShell",
    "ProtectedPaths",
    "ShellStartError",
    "SubprocessShell",
    "WorkspaceArea",
    "denied_commands_for",
    "environment_notice",
    "interpreter_for",
    "merge_environment",
    "option_synonyms_for",
    "parse_dotenv",
    "program_aliases_for",
    "read_dotenv",
    "select_shell",
    "windows_path_problem",
]
