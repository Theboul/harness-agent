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
