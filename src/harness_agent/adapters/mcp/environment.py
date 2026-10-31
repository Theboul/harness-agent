"""The environment an MCP server process receives (HU-08-01 / FR-007).

It is an allow list: only the variables the configuration names, taken from the environment that
is injected (this module reads neither ``os.environ`` nor the configuration). The SDK adds its own
safe base on top (``PATH``, ``HOME``, ``SYSTEMROOT``...), so the API keys of the providers never
reach the server unless someone names them.
"""

from __future__ import annotations

import os
from collections.abc import Collection, Mapping


def server_environment(
    environ: Mapping[str, str], names: Collection[str], *, windows: bool | None = None
) -> dict[str, str]:
    """The variables of ``environ`` that ``names`` lists, in a new dictionary.

    Args:
        environ: The environment of the parent; it is not modified.
        names: Names of the variables to pass on; the ones that do not exist are skipped.
        windows: True to compare names ignoring case, as Windows does; defaults to the platform.

    Returns:
        A dictionary with exactly the named variables that exist, spelled as in ``environ``.
    """
    insensitive = os.name == "nt" if windows is None else windows
    if insensitive:
        wanted = {name.upper() for name in names}
        return {key: value for key, value in environ.items() if key.upper() in wanted}
    wanted_exact = set(names)
    return {key: value for key, value in environ.items() if key in wanted_exact}
