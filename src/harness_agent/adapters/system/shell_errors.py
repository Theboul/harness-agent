"""Errors of the shell adapters (HU-01-04)."""

from __future__ import annotations


class ShellStartError(OSError):
    """The interpreter is missing or the command could not be started.

    The message is for the model: it names the interpreter but never a path or the command.
    """
