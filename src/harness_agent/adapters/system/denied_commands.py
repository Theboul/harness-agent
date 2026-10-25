"""Commands the shell should never run without a human deciding, per interpreter (HU-01-04).

This is data only. Nothing in the shell or the tool applies it: the permission rules of HU-05-02
consume it. A ``pattern`` is a literal fragment of command text; how it is matched (case, compound
commands) is decided there. The list is conservative and pending review by the Product Owner, and
it does not replace the approval that every ``shell`` call needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class DeniedCommand:
    """A fragment of command text and why it is dangerous."""

    pattern: str
    reason: str


_BASH = (
    DeniedCommand("rm -rf /", "Borra el sistema de archivos desde la raíz."),
    DeniedCommand("rm -rf ~", "Borra la carpeta personal completa."),
    DeniedCommand("mkfs", "Formatea un dispositivo y destruye sus datos."),
    DeniedCommand("dd if=", "Escribe bloques en bruto y puede sobrescribir un disco."),
    DeniedCommand(":(){ :|:& };:", "Bomba de procesos que agota el sistema."),
    DeniedCommand("shutdown", "Apaga el equipo."),
    DeniedCommand("reboot", "Reinicia el equipo."),
    DeniedCommand("chmod -R 777 /", "Abre los permisos de todo el sistema de archivos."),
)

_POWERSHELL = (
    DeniedCommand("Remove-Item -Recurse -Force C:\\", "Borra la raíz de una unidad."),
    DeniedCommand("Format-Volume", "Formatea un volumen y destruye sus datos."),
    DeniedCommand("Clear-Disk", "Borra todas las particiones de un disco."),
    DeniedCommand("Stop-Computer", "Apaga el equipo."),
    DeniedCommand("Restart-Computer", "Reinicia el equipo."),
    DeniedCommand("Set-ExecutionPolicy", "Cambia la política de ejecución de scripts."),
    DeniedCommand("reg delete", "Borra claves del registro de Windows."),
)

DEFAULT_DENIED_COMMANDS: MappingProxyType[str, tuple[DeniedCommand, ...]] = MappingProxyType(
    {"bash": _BASH, "powershell": _POWERSHELL}
)
"""The default list per ``interpreter_name``; read-only."""


def denied_commands_for(interpreter: str) -> tuple[DeniedCommand, ...]:
    """The default denied commands of ``interpreter``; empty if it is not known."""
    return DEFAULT_DENIED_COMMANDS.get(interpreter, ())
