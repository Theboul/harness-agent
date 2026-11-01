"""General redaction of secrets before anything is written to disk (HU-10-02).

``redact_secrets`` replaces with ``HIDDEN_SECRET`` what looks like a secret:

1. **known values** passed by the caller (the key of the provider, the values of the environment
   variables named like keys), compared literally;
2. keys with a **well-known prefix** (``sk-``, ``gsk_``, ``AIza``, ``ghp_``, ``github_pat_``,
   ``xoxb-``, ``AKIA``…) and JWTs;
3. ``Authorization``/``Bearer``/``Basic`` credentials;
4. the value of ``NAME=value`` / ``"name": "value"`` pairs whose name holds *key*, *secret*,
   *token*, *password* or *credential*;
5. the credentials of URLs (``hide_url_credentials``, HU-11-02, absorbed here).

**It is a heuristic, not a guarantee** (business rule 1 of HU-10-02). False negatives: a key with
no known prefix and no secret-like name, a key split or encoded, a known value shorter than
``MIN_KNOWN_LENGTH``. False positives: a pair such as ``monkey=banana1`` or ``keyboard=layout-us``
(any name that holds a marker). The function is pure, idempotent (the marker matches no pattern)
and of linear cost: the pair detection does not backtrack (it looks 64 characters behind each
``=``/``:``) and the expressions are possessive or have no trailing requirement.

The module only uses the standard library; it reads no file and no environment: the caller hands
the known values (``SecretRedactor.from_environment`` takes a ``Mapping``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from harness_agent.core.redaction import HIDDEN_SECRET, hide_url_credentials

MIN_KNOWN_LENGTH = 8
"""Known values shorter than this are ignored, so ordinary words are not destroyed."""

_NAME_LOOKBEHIND = 64
_MIN_PAIR_VALUE = 6
_NAME_MARKERS = re.compile(r"key|secret|token(?!s)|passw(?:or)?d|credential")
_NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-")
_BEFORE_SEPARATOR = frozenset(" \t\"'")
_VALUE_END = frozenset(" \t\r\n\"',;&)}]<")
_SEPARATORS = re.compile(r"[=:]")

_PREFIXED = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    r"sk-[A-Za-z0-9_\-]{20,}"
    r"|gsk_[A-Za-z0-9]{20,}"
    r"|AIza[A-Za-z0-9_\-]{30,}"
    r"|gh[pousr]_[A-Za-z0-9]{30,}"
    r"|github_pat_[A-Za-z0-9_]{30,}"
    r"|xox[abprs]-[A-Za-z0-9\-]{10,}"
    r"|(?:AKIA|ASIA)[0-9A-Z]{16}"
    r"|eyJ[A-Za-z0-9_\-]{8,2000}+\.[A-Za-z0-9_\-]{8,2000}+\.[A-Za-z0-9_\-]{8,2000}+"
    r")"
)
_AUTHORIZATION = re.compile(
    r"(?<![A-Za-z0-9])(authorization[ \t]*[:=][ \t]*(?:(?:bearer|basic|token)[ \t]+)?)"
    r"([^\s\"',;]{8,})",
    re.IGNORECASE,
)
_BEARER = re.compile(
    r"(?<![A-Za-z0-9])((?:bearer|basic)[ \t]+)([A-Za-z0-9._~+/=\-]{8,})", re.IGNORECASE
)
_LONG_TOKEN = 32


def _hide_authorization(match: re.Match[str]) -> str:
    if match.string.startswith(HIDDEN_SECRET, match.start(2)) or match.group(2).startswith("<"):
        return match.group(0)
    return match.group(1) + HIDDEN_SECRET


def _hide_bearer(match: re.Match[str]) -> str:
    token = match.group(2)
    # Prose such as "Bearer authentication" has neither digits nor the length of a token.
    if not (any(char.isdigit() for char in token) or len(token) >= _LONG_TOKEN):
        return match.group(0)
    return match.group(1) + HIDDEN_SECRET


def is_secret_name(name: str) -> bool:
    """Whether a variable or field name suggests a secret (``API_KEY``, ``token``, ``password``).

    ``tokens`` (plural, as in ``max_tokens``) is a count, not a secret.
    """
    return _NAME_MARKERS.search(name.lower()) is not None


def _hide_known(text: str, known: Iterable[str]) -> str:
    values = sorted({value for value in known if len(value) >= MIN_KNOWN_LENGTH}, key=len)
    for value in reversed(values):  # longest first: a value never leaves its tail behind
        text = text.replace(value, HIDDEN_SECRET)
    return text


def _hide_pairs(text: str) -> str:
    """Hide the value of every ``name=value`` / ``name: value`` whose name looks like a secret."""
    pieces: list[str] = []
    copied = 0  # text[:copied] is already in ``pieces``
    size = len(text)
    for separator in _SEPARATORS.finditer(text):
        at = separator.start()
        if at < copied:
            continue
        end = at
        while end > 0 and text[end - 1] in _BEFORE_SEPARATOR and at - end < 8:
            end -= 1
        start = end
        while start > 0 and end - start < _NAME_LOOKBEHIND and text[start - 1] in _NAME_CHARS:
            start -= 1
        if start == end or not is_secret_name(text[start:end]):
            continue
        value = at + 1
        while value < size and text[value] in " \t" and value - at < 8:
            value += 1
        if value < size and text[value] in "\"'":
            value += 1
        if text.startswith(HIDDEN_SECRET, value):
            continue
        stop = value
        while stop < size and text[stop] not in _VALUE_END:
            stop += 1
        if stop - value < _MIN_PAIR_VALUE or text[value:stop].isdigit():
            continue
        pieces.append(text[copied:value])
        pieces.append(HIDDEN_SECRET)
        copied = stop
    if not pieces:
        return text
    pieces.append(text[copied:])
    return "".join(pieces)


def redact_secrets(text: str, *, known: Iterable[str] = ()) -> str:
    """``text`` with everything that looks like a secret replaced by ``HIDDEN_SECRET``.

    Args:
        text: The text to clean; it is never changed in place.
        known: Secret values to hide literally (ignored when shorter than ``MIN_KNOWN_LENGTH``).

    Returns:
        The cleaned text; the same text when nothing was found. Redacting the result again
        gives the same result.

    Raises:
        TypeError: ``text`` is not a text.
    """
    if not isinstance(text, str):
        raise TypeError("El texto debe ser un str.")
    text = _hide_known(text, known)
    text = hide_url_credentials(text)
    text = _PREFIXED.sub(HIDDEN_SECRET, text)
    text = _AUTHORIZATION.sub(_hide_authorization, text)
    text = _BEARER.sub(_hide_bearer, text)
    return _hide_pairs(text)


class SecretRedactor:
    """A redactor that knows the secret values of this run.

    Calling it with a text gives ``redact_secrets(text, known=…)``; ``value`` cleans every text
    inside a structure (an event payload, the arguments of a tool call). The known values never
    appear in its representation.

    Args:
        known: Secret values to hide literally (those shorter than ``MIN_KNOWN_LENGTH`` are
            dropped).
    """

    def __init__(self, known: Iterable[str] = ()) -> None:
        self._known = tuple(
            sorted({value for value in known if len(value) >= MIN_KNOWN_LENGTH}, key=len)
        )

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str], extra: Iterable[str] = ()
    ) -> SecretRedactor:
        """A redactor for the values of the variables named like keys, plus ``extra``.

        The caller hands the environment (the core never reads it): the merged one with the
        ``.env`` file in the real run.
        """
        values = [value for name, value in environ.items() if is_secret_name(name)]
        return cls([*values, *extra])

    def __call__(self, text: str) -> str:
        return redact_secrets(text, known=self._known)

    def value(self, value: Any) -> Any:
        """``value`` with every text redacted at any depth (keys and non-texts stay as they are)."""
        if isinstance(value, str):
            return self(value)
        if isinstance(value, list):
            return [self.value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.value(item) for item in value)
        if isinstance(value, Mapping):
            return {key: self.value(item) for key, item in value.items()}
        return value

    def __repr__(self) -> str:
        return f"SecretRedactor(known={len(self._known)})"
