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
    - USER_MESSAGE: New message received from the user.
    - ASSISTANT_MESSAGE: Textual response emitted by the assistant/model.
    - TOOL_REQUESTED: Model requests execution of a tool.
    - TOOL_FINISHED: Tool execution finished with result or error.
    - APPROVAL_REQUESTED: Permission policy requests user approval.
    - APPROVAL_RESOLVED: User resolved approval request (approved/rejected).
    - CONTEXT_COMPACTED: History compacted after exceeding token threshold.
    - PERMISSION_DECIDED: Policy decision evaluated (deny, ask, allow).
    - CRITERIA_TAMPERED: Attempted modification or tampering in task criteria.
    - LIMIT_REACHED: Turn, time, or cost budget exceeded.
    - PROVIDER_ERROR: Provider API error or timeout encountered.
    - PROVIDER_SWITCHED: Fallback provider switched after primary failure.
    - SUBAGENT_STARTED: Subagent child session spawned.
    - SUBAGENT_FINISHED: Subagent completed execution with result.
    - INTERRUPTED: Clean cancellation on user interrupt signal (Ctrl+C).
    - SESSION_STARTED: Session started or resumed with startup routine.
    - CRITERION_VERIFIED: Verification result for a task acceptance criterion.
    """

    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_REQUESTED = "tool_requested"
    TOOL_FINISHED = "tool_finished"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    CONTEXT_COMPACTED = "context_compacted"
    PERMISSION_DECIDED = "permission_decided"
    CRITERIA_TAMPERED = "criteria_tampered"
    LIMIT_REACHED = "limit_reached"
    PROVIDER_ERROR = "provider_error"
    PROVIDER_SWITCHED = "provider_switched"
    SUBAGENT_STARTED = "subagent_started"
    SUBAGENT_FINISHED = "subagent_finished"
    INTERRUPTED = "interrupted"
    SESSION_STARTED = "session_started"
    CRITERION_VERIFIED = "criterion_verified"


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
