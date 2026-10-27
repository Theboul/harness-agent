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
_CREDENTIALS = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://)[^\s/@]+@")


def hide_url_credentials(text: str) -> str:
    """``text`` with the credentials of every URL replaced by ``HIDDEN_SECRET``.

    Raises:
        TypeError: ``text`` is not a text.
    """
    if not isinstance(text, str):
        raise TypeError("El texto debe ser un str.")
    return _CREDENTIALS.sub(lambda found: f"{found.group(1)}{HIDDEN_SECRET}@", text)
