"""Domain error of the task format (HU-11-01).

``TaskFormatError`` derives from ``ValueError``. Its message is a fixed Spanish text chosen by
``code``: it says what is missing or wrong and never reproduces the text that was received.
"""

from __future__ import annotations

_MESSAGES = {
    "vacia": "La tarea está vacía: escribe el objetivo y los criterios de aceptación.",
    "demasiado_grande": "La tarea es demasiado grande.",
    "contenido_no_valido": "La tarea contiene caracteres de control que no se admiten.",
    "formato_no_valido": (
        "La tarea no sigue el formato: usa las secciones '## Objetivo' y "
        "'## Criterios de aceptación' con criterios como elementos de lista."
    ),
    "sin_objetivo": "A la tarea le falta el objetivo: añade la sección '## Objetivo' con texto.",
    "sin_criterios": (
        "A la tarea le faltan los criterios de aceptación: añade la sección "
        "'## Criterios de aceptación' con al menos un criterio."
    ),
    "seccion_repetida": "La tarea repite una sección.",
    "seccion_desconocida": (
        "La tarea tiene una sección desconocida: solo se admiten Objetivo, Contexto, Reglas y "
        "Criterios de aceptación."
    ),
    "criterio_incompleto": (
        "Un criterio está incompleto: 'comando:' y 'espera:' van juntos, con texto, una sola vez."
    ),
    "demasiados_criterios": "La tarea tiene más criterios de los permitidos.",
    "texto_demasiado_largo": "Un texto de la tarea supera la longitud permitida.",
}


class TaskFormatError(ValueError):
    """The text of a task does not meet the task format; ``code`` identifies the reason."""

    def __init__(self, code: str) -> None:
        super().__init__(_MESSAGES[code])
        self.code = code
