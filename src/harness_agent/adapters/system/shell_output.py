"""OutputCollector: keeps the head and the tail of a command's output (HU-01-04).

The output is decoded as it arrives (UTF-8, invalid bytes replaced) and only the first and the
last characters are retained, so memory stays bounded whatever the command prints. When the total
exceeds the maximum, the text is ``head + notice + tail`` and never longer than the maximum.
"""

from __future__ import annotations

import codecs

from harness_agent.adapters.system.shell_limits import MAX_OUTPUT_CHARS, NOTICE_RESERVE_CHARS


def _notice(omitted: int) -> str:
    return f"\n[salida recortada: se omitieron {omitted} caracteres]\n"


class OutputCollector:
    """Collect bytes into a bounded text. Feed it chunks, then call ``finish`` once."""

    def __init__(self, max_chars: int = MAX_OUTPUT_CHARS) -> None:
        """Create a collector.

        Args:
            max_chars: Longest text ``finish`` returns; it must leave room for the notice.

        Raises:
            ValueError: ``max_chars`` cannot hold the notice.
        """
        if max_chars <= NOTICE_RESERVE_CHARS:
            raise ValueError(
                f"El máximo de salida debe ser mayor que {NOTICE_RESERVE_CHARS} caracteres."
            )
        self._max = max_chars
        self._head_cap = max_chars // 2
        self._tail_cap = max_chars - self._head_cap
        self._head = ""
        self._tail = ""
        self._total = 0
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._result: str | None = None

    @property
    def total_chars(self) -> int:
        """Characters seen so far, retained or not."""
        return self._total

    @property
    def retained_chars(self) -> int:
        """Characters held in memory."""
        return len(self._head) + len(self._tail)

    def feed(self, chunk: bytes) -> None:
        """Decode ``chunk`` and keep what fits in the head and in the tail."""
        self._append(self._decoder.decode(chunk))

    def finish(self) -> str:
        """The bounded text, marked when something was left out."""
        if self._result is None:
            self._append(self._decoder.decode(b"", final=True))
            self._result = self._build()
        return self._result

    def _append(self, text: str) -> None:
        self._total += len(text)
        room = self._head_cap - len(self._head)
        if room > 0:
            self._head += text[:room]
            text = text[room:]
        if text:
            self._tail = (self._tail + text)[-self._tail_cap :]

    def _build(self) -> str:
        if self._total <= self._max:
            return self._head + self._tail
        available = self._max - NOTICE_RESERVE_CHARS
        head_size = available // 2
        tail_size = available - head_size
        omitted = self._total - head_size - tail_size
        return self._head[:head_size] + _notice(omitted) + self._tail[-tail_size:]
