"""The text that tells the model where its commands run (HU-01-04).

It is a pure function of the operating system and the interpreter: the same pair always gives the
same text, byte for byte, so a provider can cache it. It says nothing about the machine (user,
paths, variables).
"""

from __future__ import annotations

_DISPLAY_NAMES = {"powershell": "PowerShell", "bash": "bash"}


def environment_notice(system_name: str, interpreter: str) -> str:
    """The system message that names the operating system and the interpreter.

    Args:
        system_name: The name ``platform.system()`` returns.
        interpreter: The ``interpreter_name`` of the shell; an unknown one is named as it is.
    """
    shown = _DISPLAY_NAMES.get(interpreter, interpreter)
    return (
        f"Entorno de ejecución: sistema operativo {system_name}; "
        f"la herramienta 'shell' usa {shown}.\n"
        f"Escribe los comandos con la sintaxis de {shown}. "
        "Cada llamada a 'shell' es independiente:\n"
        "no se conservan la carpeta actual ni las variables entre llamadas. "
        "Un comando que supere el tiempo\n"
        "máximo se termina y se informa."
    )
