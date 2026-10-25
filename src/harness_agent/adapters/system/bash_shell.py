"""BashShell: runs commands with bash (HU-01-04)."""

from __future__ import annotations

from harness_agent.adapters.system.subprocess_shell import SubprocessShell


class BashShell(SubprocessShell):
    """bash without profiles or interactive mode, so the result does not depend on the user."""

    @property
    def interpreter_name(self) -> str:
        return "bash"

    @property
    def _executable_names(self) -> tuple[str, ...]:
        return ("bash",)

    def _argv(self, executable: str, command: str) -> list[str]:
        return [executable, "--noprofile", "--norc", "-c", command]
