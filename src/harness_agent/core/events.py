"""Canonical event catalog and event payload model for HARNESS.

Defines the 17 official event types established in HARNESS v2.5 architecture
(docs/02-arquitectura.md §3.7) and the immutable Event structure for bus
communication, completely decoupled from EventBus implementation, persistence,
and user interfaces.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """The 17 canonical event types for the HARNESS event bus.

    Lifecycle events defined in docs/02-arquitectura.md §3.7:
    - MENSAJE_USUARIO: New message received from the user.
    - MENSAJE_ASISTENTE: Textual response emitted by the assistant/model.
    - HERRAMIENTA_SOLICITADA: Model requests execution of a tool.
    - HERRAMIENTA_TERMINADA: Tool execution finished with result or error.
    - APROBACION_PEDIDA: Permission policy requests user approval.
    - APROBACION_RESUELTA: User resolved approval request (approved/rejected).
    - CONTEXTO_COMPACTADO: History compacted after exceeding token threshold.
    - PERMISO_DECIDIDO: Policy decision evaluated (deny, ask, allow).
    - CRITERIOS_ALTERADOS: Attempted modification or tampering in task criteria.
    - LIMITE_ALCANZADO: Turn, time, or cost budget exceeded.
    - ERROR_PROVEEDOR: Provider API error or timeout encountered.
    - PROVEEDOR_CONMUTADO: Fallback provider switched after primary failure.
    - SUBAGENTE_INICIADO: Subagent child session spawned.
    - SUBAGENTE_TERMINADO: Subagent completed execution with result.
    - INTERRUMPIDO: Clean cancellation on user interrupt signal (Ctrl+C).
    - SESION_ARRANCADA: Session started or resumed with startup routine.
    - CRITERIO_VERIFICADO: Verification result for a task acceptance criterion.
    """

    MENSAJE_USUARIO = "mensaje_usuario"
    MENSAJE_ASISTENTE = "mensaje_asistente"
    HERRAMIENTA_SOLICITADA = "herramienta_solicitada"
    HERRAMIENTA_TERMINADA = "herramienta_terminada"
    APROBACION_PEDIDA = "aprobacion_pedida"
    APROBACION_RESUELTA = "aprobacion_resuelta"
    CONTEXTO_COMPACTADO = "contexto_compactado"
    PERMISO_DECIDIDO = "permiso_decidido"
    CRITERIOS_ALTERADOS = "criterios_alterados"
    LIMITE_ALCANZADO = "limite_alcanzado"
    ERROR_PROVEEDOR = "error_proveedor"
    PROVEEDOR_CONMUTADO = "proveedor_conmutado"
    SUBAGENTE_INICIADO = "subagente_iniciado"
    SUBAGENTE_TERMINADO = "subagente_terminado"
    INTERRUMPIDO = "interrumpido"
    SESION_ARRANCADA = "sesion_arrancada"
    CRITERIO_VERIFICADO = "criterio_verificado"


@dataclass(frozen=True)
class Event:
    """Immutable event payload published to the EventBus and stored in history.

    Attributes:
        id: Unique identifier for this event instance (UUIDv4).
        session_id: Identifier of the active session this event belongs to.
        type: Canonical event type.
        timestamp: UTC timestamp when the event occurred.
        payload: Event-specific structured data dictionary.
    """

    id: str
    session_id: str
    type: EventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Enforce canonical types and UTC timezone normalization."""
        if isinstance(self.type, str) and not isinstance(self.type, EventType):
            object.__setattr__(self, "type", EventType(self.type))
        if self.timestamp.tzinfo is None:
            object.__setattr__(self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc))

    @classmethod
    def create(
        cls,
        session_id: str,
        type: EventType | str,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
        timestamp: datetime | None = None,
    ) -> Event:
        """Factory constructor with automatic UUID generation and UTC timestamp."""
        return cls(
            id=event_id or str(uuid.uuid4()),
            session_id=session_id,
            type=EventType(type) if isinstance(type, str) else type,
            timestamp=timestamp or datetime.now(timezone.utc),
            payload=payload if payload is not None else {},
        )
