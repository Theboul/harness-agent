"""Domain errors of the context subsystem (HU-02-01).

Messages are fixed Spanish sentences that never reproduce the offending value, so they are
safe to show to the user and to publish in events.
"""

from __future__ import annotations


class ContextConfigError(ValueError):
    """The prefix configuration or a tool declaration is invalid; nothing was built."""
