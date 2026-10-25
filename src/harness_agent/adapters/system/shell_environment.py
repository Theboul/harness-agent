"""The environment a shell command runs with (HU-01-04).

The command inherits the environment of the harness without the variables that hold the API keys
of the providers, so ``env`` or ``printenv`` cannot show them. The environment and the names to
remove are injected: this module reads neither ``os.environ`` nor the configuration.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping


def child_environment(
    environ: Mapping[str, str], removed: Collection[str], *, windows: bool
) -> dict[str, str]:
    """A copy of ``environ`` without the variables named in ``removed``.

    Args:
        environ: The environment to start from; it is not modified.
        removed: Names of the variables to leave out.
        windows: True to compare names ignoring case, as Windows does.

    Returns:
        A new dictionary with everything else untouched.
    """
    if windows:
        hidden = {name.upper() for name in removed}
        return {name: value for name, value in environ.items() if name.upper() not in hidden}
    hidden_exact = set(removed)
    return {name: value for name, value in environ.items() if name not in hidden_exact}
