"""Errors of the task sources (HU-11-01).

Messages are fixed Spanish texts chosen by ``code``: they never reproduce a path, the content of a
file or what ``gh`` printed.
"""

from __future__ import annotations

_MESSAGES = {
    "archivo_ilegible": "No se pudo leer el archivo de la tarea.",
    "archivo_no_utf8": "El archivo de la tarea no es texto UTF-8.",
    "archivo_demasiado_grande": "El archivo de la tarea es demasiado grande.",
    "issue_invalido": "El número de issue o el repositorio indicado no es válido.",
    "gh_no_disponible": (
        "No se pudo ejecutar la CLI de GitHub (gh). Revisa que esté instalada y con sesión "
        "iniciada."
    ),
    "gh_tiempo": "La CLI de GitHub (gh) tardó demasiado y se canceló.",
    "gh_fallo": "La CLI de GitHub (gh) no pudo leer el issue. Revisa el número y tus permisos.",
    "gh_respuesta_invalida": "La respuesta de la CLI de GitHub (gh) no tiene el formato esperado.",
}


class TaskSourceError(Exception):
    """The text of a task could not be obtained; ``code`` identifies the reason."""

    def __init__(self, code: str) -> None:
        super().__init__(_MESSAGES[code])
        self.code = code
