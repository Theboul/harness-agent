"""Commands the shell must never run, per interpreter (HU-01-04 data, applied by HU-05-02).

This is data only: the permission policy of the core (``CommandPolicy``) applies it after the
composition root compiles each entry with the rules of the core. A ``pattern`` is written as the
real command (``rm -rf /``, ``shutdown``, ``dd if=``, ``> /dev/sd``); the kind of rule follows from
its words (see ``harness_agent.core.compile_rule``). The list is conservative and pending review by
the Product Owner. The two tables help the parser compare commands: the aliases of PowerShell
programs and, per bash program, the long options and the short one they stand for.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class DeniedCommand:
    """A command written as the real one, and why it is dangerous."""

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
    DeniedCommand("halt", "Detiene el equipo."),
    DeniedCommand("poweroff", "Apaga el equipo."),
    DeniedCommand("init 0", "Apaga el equipo."),
    DeniedCommand("init 6", "Reinicia el equipo."),
    DeniedCommand("wipefs", "Borra las firmas de un dispositivo y lo deja ilegible."),
    DeniedCommand("shred", "Sobrescribe archivos o dispositivos sin posibilidad de recuperarlos."),
    DeniedCommand("fdisk", "Modifica la tabla de particiones de un disco."),
    DeniedCommand("parted", "Modifica la tabla de particiones de un disco."),
    DeniedCommand("> /dev/sd", "Escribe directamente en un disco."),
    DeniedCommand("> /dev/nvme", "Escribe directamente en un disco."),
    DeniedCommand("> /dev/hd", "Escribe directamente en un disco."),
    DeniedCommand("chown -R root /", "Cambia el dueño de todo el sistema de archivos."),
)

_POWERSHELL = (
    DeniedCommand("Remove-Item -Recurse -Force C:\\", "Borra la raíz de una unidad."),
    DeniedCommand("Format-Volume", "Formatea un volumen y destruye sus datos."),
    DeniedCommand("Clear-Disk", "Borra todas las particiones de un disco."),
    DeniedCommand("Stop-Computer", "Apaga el equipo."),
    DeniedCommand("Restart-Computer", "Reinicia el equipo."),
    DeniedCommand("Set-ExecutionPolicy", "Cambia la política de ejecución de scripts."),
    DeniedCommand("reg delete", "Borra claves del registro de Windows."),
    DeniedCommand("shutdown", "Apaga o reinicia el equipo."),
    DeniedCommand("Remove-Item -Recurse -Force ~", "Borra la carpeta personal completa."),
    DeniedCommand("format", "Formatea una unidad y destruye sus datos."),
    DeniedCommand("Initialize-Disk", "Prepara un disco y puede destruir sus datos."),
    DeniedCommand("Remove-Partition", "Borra una partición."),
    DeniedCommand("Disable-ComputerRestore", "Desactiva los puntos de restauración del sistema."),
    DeniedCommand("bcdedit", "Modifica la configuración de arranque del sistema."),
    DeniedCommand("vssadmin delete shadows", "Borra las copias de seguridad de volumen."),
)

DEFAULT_DENIED_COMMANDS: MappingProxyType[str, tuple[DeniedCommand, ...]] = MappingProxyType(
    {"bash": _BASH, "powershell": _POWERSHELL}
)
"""The default list per ``interpreter_name``; read-only."""

_NO_ALIASES: MappingProxyType[str, str] = MappingProxyType({})
_NO_SYNONYMS: MappingProxyType[str, MappingProxyType[str, str]] = MappingProxyType({})

PROGRAM_ALIASES: MappingProxyType[str, MappingProxyType[str, str]] = MappingProxyType(
    {
        "powershell": MappingProxyType(
            {alias: "remove-item" for alias in ("rm", "ri", "del", "erase", "rd", "rmdir")}
        ),
    }
)
"""Per interpreter, program aliases (lower case) and the program they stand for; read-only."""

OPTION_SYNONYMS: MappingProxyType[str, MappingProxyType[str, MappingProxyType[str, str]]] = (
    MappingProxyType(
        {
            "bash": MappingProxyType(
                {
                    "rm": MappingProxyType({"--recursive": "-r", "--force": "-f", "-R": "-r"}),
                    "chmod": MappingProxyType({"--recursive": "-R"}),
                    "chown": MappingProxyType({"--recursive": "-R"}),
                }
            ),
        }
    )
)
"""Per interpreter and program, options and the one they stand for; read-only."""


def denied_commands_for(interpreter: str) -> tuple[DeniedCommand, ...]:
    """The default denied commands of ``interpreter``; empty if it is not known."""
    return DEFAULT_DENIED_COMMANDS.get(interpreter, ())


def program_aliases_for(interpreter: str) -> MappingProxyType[str, str]:
    """The program aliases of ``interpreter``; empty if it has none."""
    return PROGRAM_ALIASES.get(interpreter, _NO_ALIASES)


def option_synonyms_for(interpreter: str) -> MappingProxyType[str, MappingProxyType[str, str]]:
    """The option synonyms of ``interpreter``, per program; empty if it has none."""
    return OPTION_SYNONYMS.get(interpreter, _NO_SYNONYMS)
