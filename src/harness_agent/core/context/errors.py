"""Domain errors of the context subsystem (HU-02-01).

Messages are fixed Spanish sentences that never reproduce the offending value, so they are
safe to show to the user and to publish in events.
"""

from __future__ import annotations


class ContextConfigError(ValueError):
    """The prefix, compaction or tool configuration is invalid; nothing was built."""


class SummaryRejected(ValueError):
    """The text that came back as a summary cannot be used; nothing was changed.

    The messages are fixed sentences: they never repeat the text of the summary.
    """


class CompactionError(RuntimeError):
    """The history could not be compacted safely; nothing was changed.

    The messages are fixed sentences: they never repeat the history or the summary.
    """


class EssentialContextError(ValueError):
    """The essential context of a task cannot be built or used; nothing was sent or changed.

    The messages are fixed sentences: they name an element and a cap, never a value.
    """


class EssentialContextTooLarge(EssentialContextError):
    """An element or the whole block is over its cap (it is never truncated).

    Attributes:
        element: The element (objetivo, reglas, ticket, criterios) or ``bloque completo``.
        limit: The cap.
        unit: ``caracteres`` or ``tokens``.
    """

    def __init__(self, element: str, limit: int, unit: str) -> None:
        self.element = element
        self.limit = limit
        self.unit = unit
        super().__init__(
            f"El elemento «{element}» del contexto esencial supera el tope de {limit} {unit}."
        )


class EssentialContextUnavailable(EssentialContextError):
    """The essential context of a task cannot be read or is incomplete: the request is not sent.

    Attributes:
        missing: ``True`` when elements the task needs are not there; ``False`` when a source
            could not be read.
    """

    def __init__(self, missing: bool = False) -> None:
        self.missing = missing
        if missing:
            text = "Faltan elementos del contexto esencial de la tarea; la petición no se envía."
        else:
            text = "No se pudo leer el contexto esencial de la tarea; la petición no se envía."
        super().__init__(text)


class ConversationSaveError(Exception):
    """A message of the conversation could not be saved: the session could not be resumed later.

    The message is fixed: it never carries the text of the message or of the original failure.
    """

    def __init__(self) -> None:
        super().__init__(
            "No se pudo guardar un mensaje de la conversación; la sesión no podrá reanudarse."
        )


class ResumeError(Exception):
    """A session cannot be resumed. Every subclass has a fixed message that never repeats the
    identifier the person wrote, the history of the session or the text of an exception."""


class InvalidSessionId(ResumeError):
    """The identifier is empty (``usage``) or is not an identifier at all."""

    def __init__(self, usage: bool = False) -> None:
        if usage:
            super().__init__("Uso: /reanudar <identificador de la sesión>.")
        else:
            super().__init__("El identificador de sesión no es válido.")


class AlreadyCurrentSession(ResumeError):
    """The identifier is the one of the session that is already running."""

    def __init__(self) -> None:
        super().__init__("Esa ya es la sesión actual.")


class UnknownSession(ResumeError):
    """No session has that identifier."""

    def __init__(self) -> None:
        super().__init__("No existe una sesión con ese identificador.")


class TaskSessionNotResumable(ResumeError):
    """The session has a task (criteria or essential context): it is not resumed (Q3 = A)."""

    def __init__(self) -> None:
        super().__init__("Las sesiones de tarea no se pueden reanudar todavía.")


class SessionDetailMissing(ResumeError):
    """The session has message events whose messages were not saved: it cannot be rebuilt."""

    def __init__(self) -> None:
        super().__init__(
            "Esa sesión se guardó sin el detalle de sus mensajes y no se puede reanudar."
        )


class ConversationInconsistent(ResumeError):
    """The stored messages do not form a coherent conversation: nothing is rebuilt."""

    def __init__(self) -> None:
        super().__init__(
            "Los mensajes guardados de la sesión no son coherentes y no se puede reanudar."
        )
