"""ShellTool: runs a command through the ``Shell`` port (HU-01-04, ``shell``).

The tool has high risk and no ``path`` argument, so the permission policy always asks before it
runs; this module neither applies nor replaces that policy. It turns every outcome into a
``ToolResult`` with a labelled message and never repeats the command or the text of an exception.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from harness_agent.adapters.tools._limits import (
    DEFAULT_SHELL_TIMEOUT_SECONDS,
    MAX_COMMAND_CHARS,
    MAX_SHELL_TIMEOUT_SECONDS,
)
from harness_agent.adapters.tools._paths import bounded_text, error_result
from harness_agent.core import AuthorizedArea, RiskLevel, Shell, Tool, ToolResult

_NO_OUTPUT = "(sin salida)"
# Names of the arguments; the composition root uses them to allow the commands of a task exactly
# (HU-11-03).
COMMAND_ARGUMENT = "command"
TIMEOUT_ARGUMENT = "timeout_seconds"


class ShellTool(Tool):
    """Run one command and report its exit code and bounded output."""

    def __init__(
        self,
        shell: Shell | None,
        area: AuthorizedArea | None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        """Create the tool.

        Args:
            shell: Where commands run; ``None`` when there is no workspace to start them in.
            area: The authorized area; without it nothing runs.
            on_cancel: Called once if the call is cancelled while the command runs, so the
                process tree can be ended instead of waiting for the time limit.
        """
        self._shell = shell
        self._area = area
        self._on_cancel = on_cancel

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        interpreter = (
            "el intérprete del sistema" if self._shell is None else self._shell.interpreter_name
        )
        return (
            f"Ejecuta un comando con {interpreter}, empezando en la raíz del área de trabajo. "
            "Cada llamada es independiente: no se conservan la carpeta actual ni las variables. "
            "Devuelve el código de salida y la salida (estándar y de errores juntas, recortada si "
            "es muy larga). Si supera el tiempo máximo, el comando se termina."
        )

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                COMMAND_ARGUMENT: {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_COMMAND_CHARS,
                    "description": "Comando a ejecutar, con la sintaxis del intérprete.",
                },
                TIMEOUT_ARGUMENT: {
                    "type": "number",
                    "minimum": 1,
                    "maximum": MAX_SHELL_TIMEOUT_SECONDS,
                    "description": (
                        f"Tiempo máximo en segundos (por defecto {DEFAULT_SHELL_TIMEOUT_SECONDS})."
                    ),
                },
            },
            "required": [COMMAND_ARGUMENT],
            "additionalProperties": False,
        }

    @property
    def risk(self) -> RiskLevel:
        return RiskLevel.HIGH

    async def run(self, args: dict[str, Any]) -> ToolResult:
        shell = self._shell
        if self._area is None or shell is None:
            return error_result(
                "sin_area",
                "No hay un área de trabajo configurada, así que no se puede ejecutar el comando. "
                "Configura 'workspace_root' en config.toml.",
            )
        command = args.get(COMMAND_ARGUMENT)
        timeout = _timeout(args.get(TIMEOUT_ARGUMENT))
        if not isinstance(command, str) or not command.strip() or timeout is None:
            return error_result(
                "argumentos_invalidos",
                "Indica 'command' con texto y, si quieres, 'timeout_seconds' entre 1 y "
                f"{MAX_SHELL_TIMEOUT_SECONDS}.",
            )
        try:
            result = await asyncio.to_thread(shell.execute, command, timeout)
        except asyncio.CancelledError:
            self._notify_cancel()
            raise
        except OSError:
            return error_result(
                "interprete_no_disponible",
                f"No se pudo iniciar el intérprete ({shell.interpreter_name}). "
                "Revisa que esté instalado.",
            )
        except Exception:
            return error_result("error_de_shell", "El comando no se pudo ejecutar.")
        output = bounded_text(result.output) if result.output.strip() else _NO_OUTPUT
        if result.timed_out:
            return ToolResult(
                call_id="",
                content=(
                    f"[tiempo_agotado] El comando superó los {timeout:g} s y se terminó "
                    f"(junto con sus procesos hijos).\n{output}"
                ),
                is_error=True,
            )
        if result.exit_code != 0:
            return ToolResult(
                call_id="",
                content=f"[codigo_de_salida={result.exit_code}] El comando terminó con error.\n"
                f"{output}",
                is_error=True,
            )
        return ToolResult(call_id="", content=f"Código de salida: 0\n{output}", is_error=False)

    def _notify_cancel(self) -> None:
        if self._on_cancel is None:
            return
        try:
            self._on_cancel()
        except Exception:
            # Cancelling must go on even if the hook fails.
            pass


def _timeout(raw: object) -> float | None:
    """The time to apply: the default if absent, the maximum if above it, ``None`` if invalid."""
    if raw is None:
        return float(DEFAULT_SHELL_TIMEOUT_SECONDS)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not raw >= 1:
        return None
    return float(min(raw, MAX_SHELL_TIMEOUT_SECONDS))
