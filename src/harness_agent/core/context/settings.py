"""Settings of the automatic compaction and the threshold of each model (HU-02-03).

The core does not read the configuration file: ``config.py`` validates the optional ``[context]``
section and hands an already built ``ContextSettings`` to the composition root. The values are
checked here too, so a bad value never reaches the compactor whoever builds the object. Error
messages name the field and never repeat the value or the model name.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from harness_agent.core.context.errors import ContextConfigError

DEFAULT_WINDOW_TOKENS = 32_000
DEFAULT_THRESHOLD_PERCENT = 80
DEFAULT_RECENT_PERCENT = 30
DEFAULT_MIN_RECENT_MESSAGES = 4
DEFAULT_SUMMARY_TOKENS = 2_000

# Field -> inclusive range of its valid integers; ``windows`` uses the range of the window size.
CONTEXT_FIELD_RANGES: Mapping[str, tuple[int, int]] = MappingProxyType(
    {
        "window_tokens": (1_000, 10_000_000),
        "windows": (1_000, 10_000_000),
        "threshold_percent": (10, 95),
        "recent_percent": (5, 60),
        "min_recent_messages": (1, 50),
        "summary_tokens": (100, 8_000),
    }
)


def requirement_of(field: str) -> str:
    """The fixed sentence that says what a valid value of ``field`` is (no value, no model)."""
    low, high = CONTEXT_FIELD_RANGES[field]
    if field == "windows":
        return f"debe ser una tabla de modelo y tamaño de ventana (enteros entre {low} y {high})."
    return f"debe ser un entero entre {low} y {high}."


def _is_valid_integer(field: str, value: object) -> bool:
    low, high = CONTEXT_FIELD_RANGES[field]
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _is_valid_window_entry(entry: object) -> bool:
    if not isinstance(entry, tuple) or len(entry) != 2:
        return False
    name, size = entry
    return isinstance(name, str) and bool(name) and _is_valid_integer("windows", size)


@dataclass(frozen=True, slots=True)
class ContextSettings:
    """What the compaction needs to know about the size of the context.

    Attributes:
        window_tokens: Context window of a model that is not in ``windows``.
        windows: Window of each model by its full name, as ``(model, tokens)`` pairs.
        threshold_percent: The threshold is this percentage of the window.
        recent_percent: The recent messages kept whole add up to at most this percentage of the
            threshold...
        min_recent_messages: ...and never fewer than this many messages.
        summary_tokens: Size asked of the summary; the accepted size is twice this.
    """

    window_tokens: int = DEFAULT_WINDOW_TOKENS
    windows: tuple[tuple[str, int], ...] = ()
    threshold_percent: int = DEFAULT_THRESHOLD_PERCENT
    recent_percent: int = DEFAULT_RECENT_PERCENT
    min_recent_messages: int = DEFAULT_MIN_RECENT_MESSAGES
    summary_tokens: int = DEFAULT_SUMMARY_TOKENS

    def __post_init__(self) -> None:
        for field in CONTEXT_FIELD_RANGES:
            value = getattr(self, field)
            if field == "windows":
                valid = isinstance(value, tuple) and all(_is_valid_window_entry(e) for e in value)
            else:
                valid = _is_valid_integer(field, value)
            if not valid:
                raise ContextConfigError(
                    f"La configuración de contexto no es válida: {field} {requirement_of(field)}"
                )

    def window_for(self, model: str) -> int:
        """The window of ``model``; an unknown model gets ``window_tokens``."""
        for name, size in self.windows:
            if name == model:
                return size
        return self.window_tokens


def threshold_tokens(settings: ContextSettings, model: str) -> int:
    """Estimated tokens from which the context is compacted, for ``model``."""
    return settings.window_for(model) * settings.threshold_percent // 100


def recent_budget_tokens(settings: ContextSettings, model: str) -> int:
    """Tokens that the recent messages kept whole may add up to, for ``model``."""
    return threshold_tokens(settings, model) * settings.recent_percent // 100


def summary_cap_tokens(settings: ContextSettings) -> int:
    """The largest summary that is accepted, in tokens: twice the size that was asked."""
    return settings.summary_tokens * 2
