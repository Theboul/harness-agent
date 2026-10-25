"""PowerShellShell: runs commands with PowerShell (HU-01-04).

The command is wrapped in a small script. The prelude makes the output UTF-8 and silences progress
bars; the epilogue turns a failed last step into a non-zero exit code, because ``-Command`` alone
would report 0 for a failed cmdlet. ``-EncodedCommand`` is avoided on purpose: it makes PowerShell
write CLIXML on the error stream.
"""

from __future__ import annotations

from harness_agent.adapters.system.subprocess_shell import SubprocessShell

_PRELUDE = (
    "$ProgressPreference = 'SilentlyContinue'; "
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
    "$OutputEncoding = [System.Text.Encoding]::UTF8"
)
_EPILOGUE = "if (-not $?) { if ($LASTEXITCODE) { exit $LASTEXITCODE } else { exit 1 } }"


def build_script(command: str) -> str:
    """The script that runs ``command``; the command stays intact on its own lines."""
    return f"{_PRELUDE}\n{command}\n{_EPILOGUE}"


class PowerShellShell(SubprocessShell):
    """PowerShell 7 (``pwsh``) when present, Windows PowerShell otherwise."""

    @property
    def interpreter_name(self) -> str:
        return "powershell"

    @property
    def _executable_names(self) -> tuple[str, ...]:
        return ("pwsh", "powershell")

    def _argv(self, executable: str, command: str) -> list[str]:
        return [
            executable,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            build_script(command),
        ]
