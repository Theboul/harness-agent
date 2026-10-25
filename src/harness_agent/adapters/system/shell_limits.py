"""Fixed limits of the shell adapters (HU-01-04): bounded output and bounded waits."""

from __future__ import annotations

MAX_OUTPUT_CHARS = 20_000
"""Longest output a shell returns; as the file tools until HU-02-02 sets a general bound."""

NOTICE_RESERVE_CHARS = 160
"""Room kept inside the maximum for the notice that marks a cut output."""

GRACE_SECONDS = 1.5
"""Time between the polite stop request and the forced one."""

READER_JOIN_SECONDS = 1.0
"""Longest wait for the output reader once the process tree has been stopped."""
