"""Domain errors of the storage adapter.

Every failure of the SQLite engine is translated into one of these types. Messages are fixed
Spanish texts: they never reproduce goals, models, identifiers or file paths.
"""

from __future__ import annotations


class SessionStoreError(Exception):
    """Base class for failures of the session store."""


class SchemaVersionError(SessionStoreError):
    """The database was written with a schema version this build does not know."""


class ParentSessionNotFound(SessionStoreError):
    """A session was created with a parent that does not exist."""


class SessionNotFound(SessionStoreError):
    """An event was saved for a session that does not exist."""


class DuplicateEvent(SessionStoreError):
    """An event with the same identifier was already saved."""


class EventSerializationError(SessionStoreError):
    """The payload of an event cannot be represented as JSON."""
