"""Shared helpers for the composition-root tests (propuesta HU-00-08).

The provider is always an injected ``FakeProvider``; the clock and the identifiers are injected
too, and the database is a temporary file: no network, key or console.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_agent.bootstrap import Composition, compose
from harness_agent.config import HarnessConfig, Limits, Paths, Secret
from harness_agent.core import Event, EventType, PermissionRules, Provider, ProviderResponse
from tests.doubles import FakeProvider

FIXED_TIME = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"


def make_config(
    tmp_path: Path,
    *,
    workspace: Path | None = None,
    model: str = "openai/modelo-de-prueba",
    api_key: Secret | None = None,
    permissions: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
) -> HarnessConfig:
    return HarnessConfig(
        model=model,
        limits=Limits(max_output_tokens=777),
        paths=Paths(workspace_root=workspace, sessions_db=tmp_path / "datos" / "sesiones.db"),
        source=tmp_path / "config.toml",
        api_key=api_key,
        permissions=permissions,
    )


def scripted(*texts: str) -> FakeProvider:
    return FakeProvider([ProviderResponse(content=text) for text in texts])


def build(
    opened: list[Composition],
    config: HarnessConfig,
    provider: Provider | None = None,
    **kwargs: Any,
) -> Composition:
    chosen = provider if provider is not None else scripted("listo")
    composition = compose(config, provider_factory=lambda _config: chosen, **kwargs)
    opened.append(composition)
    return composition


def make_event(event_type: EventType, session_id: str, index: int) -> Event:
    return Event(id=f"evento-{index}", session_id=session_id, type=event_type, payload={})


async def one_turn(composition: Composition, task: str = "hola") -> Any:
    return await composition.loop.run_turn(session_id=composition.session_id, task=task, history=[])
