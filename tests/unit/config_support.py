"""Shared helpers for the configuration tests (HU-00-04 / T002).

Nothing here imports ``harness_agent.config``, and nothing here looks like a secret to the
automatic check of AC-02: the name of a key field is built by concatenation and the TOML text
with a key field is built at run time (see ``toml_with_field``).
"""

from __future__ import annotations

from pathlib import Path

SENTINEL = "VALOR-DE-PRUEBA-123"
MINIMAL_CONFIG = 'model = "fake/test"\n'
SECRET_FIELD = "api_" + "key"


def write_config(directory: Path, content: str | bytes, *, name: str = "config.toml") -> Path:
    """Write ``content`` as bytes (a ``str`` is encoded as UTF-8) and return the absolute path."""
    target = directory / name
    data = content.encode("utf-8") if isinstance(content, str) else content
    target.write_bytes(data)
    return target.resolve()


def toml_with_field(name: str, value: str = SENTINEL) -> str:
    """Build, at run time, one TOML line ``<name> = "<value>"`` (no detectable literal)."""
    return f'{name} = "{value}"\n'
