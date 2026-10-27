"""Hiding of the credentials in URLs (HU-11-02).

``hide_url_credentials`` replaces what is between ``scheme://`` and ``@`` (``user:secret`` or a
token) with the marker ``<secreto oculto>``, the same text ``config.Secret`` shows. A URL without
credentials and a text without URLs do not change. It is applied to the shell output that goes
back to the model.

This is the first generic redaction of the harness and it is deliberately small. HU-10-02
(redaction of secrets) must absorb it; until then it lives in the core so that the tools can use
it (they may only import the public API of the core).
"""

from __future__ import annotations

import re

HIDDEN_SECRET = "<secreto oculto>"
_SEPARATOR = "://"
_SCHEME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+.-")
_FIRST_LETTER = re.compile("[A-Za-z]")
_CREDENTIALS = re.compile(r"[^\s/@]*")


def hide_url_credentials(text: str) -> str:
    """``text`` with the credentials of every URL replaced by ``HIDDEN_SECRET``.

    The cost is linear in the size of ``text``. A URL is a scheme (a letter followed by letters,
    digits, ``+``, ``.`` or ``-``), ``://`` and one or more characters that are not blanks, ``/``
    or ``@``, closed by ``@``; the scheme starts at the first letter of the run of scheme
    characters that ends at ``://``. Instead of trying a match from every position, each ``://``
    is looked at once: the run before it (the runs before two ``://`` never overlap) and the run
    after it.

    Raises:
        TypeError: ``text`` is not a text.
    """
    if not isinstance(text, str):
        raise TypeError("El texto debe ser un str.")
    pieces: list[str] = []
    copied = 0  # text[:copied] is already in ``pieces``
    search_from = 0
    while True:
        separator = text.find(_SEPARATOR, search_from)
        if separator < 0:
            break
        search_from = separator + len(_SEPARATOR)
        run_start = separator
        while run_start > copied and text[run_start - 1] in _SCHEME_CHARS:
            run_start -= 1
        scheme = _FIRST_LETTER.search(text, run_start, separator)
        if scheme is None:
            continue
        end = _CREDENTIALS.match(text, search_from).end()  # type: ignore[union-attr]
        if end == search_from or end >= len(text) or text[end] != "@":
            continue
        pieces.append(text[copied : scheme.start()])
        pieces.append(text[scheme.start() : search_from])
        pieces.append(HIDDEN_SECRET + "@")
        copied = search_from = end + 1
    if not pieces:
        return text
    pieces.append(text[copied:])
    return "".join(pieces)
