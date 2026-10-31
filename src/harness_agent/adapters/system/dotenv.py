"""Tolerant reader of a ``.env`` file (proposed HU-00-08.1).

The file holds ``NAME=value`` lines. Nothing is expanded or executed: ``$HOME`` is the text
``$HOME``. Quotes (single or double) are optional and removed; ``#`` starts a comment on its own
line or after whitespace in an unquoted value. An odd line is skipped and only counted, an
unreadable file gives an empty result: the reader never raises and never keeps or repeats the text
of a line, so no value can leak through a message.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

MAX_DOTENV_BYTES = 65_536
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INLINE_COMMENT = re.compile(r"\s+#")
_EXPORT = re.compile(r"^export\s+")


@dataclass(frozen=True)
class DotenvResult:
    """What a ``.env`` file gave.

    Attributes:
        values: The valid, non-empty ``name -> value`` pairs (hidden from ``repr``).
        skipped: How many lines were not valid and were ignored.
        unreadable: The file exists but could not be read (permissions, not UTF-8, too large).
    """

    values: Mapping[str, str] = field(default_factory=dict, repr=False)
    skipped: int = 0
    unreadable: bool = False


def _value_of(raw: str) -> str | None:
    """The value of the text after ``=``; ``None`` if the text is not valid."""
    raw = raw.strip()
    if raw[:1] in {'"', "'"}:
        closing = raw.find(raw[0], 1)
        if closing == -1:
            return None
        rest = raw[closing + 1 :].strip()
        if rest and not rest.startswith("#"):
            return None
        value = raw[1:closing]
    else:
        value = _INLINE_COMMENT.split(raw, maxsplit=1)[0].strip()
    if any(unicodedata.category(char) == "Cc" for char in value):
        return None
    return value


def parse_dotenv(text: str) -> DotenvResult:
    """Parse the text of a ``.env`` file; the last duplicate of a name wins."""
    values: dict[str, str] = {}
    skipped = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, raw = _EXPORT.sub("", line).partition("=")
        name = name.strip()
        value = _value_of(raw) if separator and _NAME.match(name) else None
        if value is None:
            skipped += 1
        elif value:
            values[name] = value
    return DotenvResult(values=values, skipped=skipped)


def read_dotenv(path: str | Path) -> DotenvResult:
    """Read and parse ``path``; a missing file is an empty result, an unreadable one is flagged."""
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(MAX_DOTENV_BYTES + 1)
    except FileNotFoundError:
        return DotenvResult()
    except OSError:
        return DotenvResult(unreadable=True)
    if len(data) > MAX_DOTENV_BYTES:
        return DotenvResult(unreadable=True)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return DotenvResult(unreadable=True)
    return parse_dotenv(text)


def merge_environment(environ: Mapping[str, str], values: Mapping[str, str]) -> dict[str, str]:
    """A new environment: ``environ`` plus the ``values`` whose name it does not define."""
    merged = dict(environ)
    for name, value in values.items():
        merged.setdefault(name, value)
    return merged
