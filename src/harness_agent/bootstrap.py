"""Composition root of HARNESS: the one place that knows every layer and joins them.

Proposed story HU-00-08 (provisional id).

``compose`` builds, in a fixed order, everything the agent loop needs from the loaded
configuration and fails closed. It adds no rule: it only chooses which implementation goes in
each port. Whatever touches the outside (the provider, the clock, the identifiers) enters by
parameter, so the composition can run in tests without network, keys or console.

Build order (what can fail because of the user's environment goes before anything is opened):
provider, authorized area and tools, policy, bus, session store, session, event recorder, loop.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from harness_agent.adapters.providers.litellm_provider import LiteLLMProvider
from harness_agent.adapters.storage import SqliteSessionStore, attach_event_recorder
from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools import ListFilesTool, ReadFileTool, SearchTextTool, WriteFileTool
from harness_agent.config import HarnessConfig
from harness_agent.core import (
    AuthorizedArea,
    DefaultPermissionPolicy,
    EventBus,
    InMemoryEventBus,
    InMemoryToolRegistry,
    Provider,
)
from harness_agent.core.loop import AgentLoop

NO_AREA_NOTICE = (
    "Aviso: no hay área de trabajo configurada (paths.workspace_root); "
    "las herramientas de archivos están desactivadas."
)
AREA_NOT_A_FOLDER_NOTICE = (
    "Aviso: el área de trabajo configurada no es una carpeta; "
    "las herramientas de archivos están desactivadas."
)

ProviderFactory = Callable[[HarnessConfig], Provider]


@dataclass(frozen=True)
class Composition:
    """Everything one run needs, already connected; built once per run and never shared.

    Attributes:
        loop: The agent loop wired with provider, registry, policy and bus.
        bus: The bus the event recorder (and later the terminal) is subscribed to.
        store: The open session store; ``close`` closes it.
        session_id: Identifier of the session created for this run.
        notices: Startup notices for the user (missing or unusable work area); usually empty.
    """

    loop: AgentLoop
    bus: EventBus
    store: SqliteSessionStore
    session_id: str
    notices: tuple[str, ...]

    def close(self) -> None:
        """Close the session store; safe to call more than once."""
        self.store.close()


def _default_provider(config: HarnessConfig) -> Provider:
    """The real provider: LiteLLM with the configured model, output cap and key."""
    return LiteLLMProvider(
        config.model,
        max_output_tokens=config.limits.max_output_tokens,
        api_key=config.api_key,
    )


def _build_area(root: Path | None) -> tuple[AuthorizedArea | None, tuple[str, ...]]:
    """The authorized area, or ``None`` plus a notice when there is no usable folder."""
    if root is None:
        return None, (NO_AREA_NOTICE,)
    if not root.is_dir():
        return None, (AREA_NOT_A_FOLDER_NOTICE,)
    return WorkspaceArea(root), ()


def compose(
    config: HarnessConfig,
    *,
    provider_factory: ProviderFactory | None = None,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> Composition:
    """Build the connected system from ``config``; nothing is left half open on failure.

    Args:
        config: The loaded configuration.
        provider_factory: Builds the provider from the configuration; defaults to LiteLLM.
        clock: Clock of the session store; defaults to UTC now.
        id_factory: Identifier factory of the session store; defaults to ``uuid4``.

    Raises:
        ProviderDependencyError: The optional dependency of the real provider is missing.
        SessionStoreError: The sessions database could not be opened or written.
        SchemaVersionError: The sessions database has an unknown schema version.
    """
    provider = (provider_factory if provider_factory is not None else _default_provider)(config)
    area, notices = _build_area(config.paths.workspace_root)
    registry = InMemoryToolRegistry()
    for tool in (
        ReadFileTool(area),
        WriteFileTool(area),
        ListFilesTool(area),
        SearchTextTool(area),
    ):
        registry.register(tool)
    policy = DefaultPermissionPolicy(registry, area, config.permissions)
    bus = InMemoryEventBus()
    store_options: dict[str, Any] = {}
    if clock is not None:
        store_options["clock"] = clock
    if id_factory is not None:
        store_options["id_factory"] = id_factory
    store = SqliteSessionStore(config.paths.sessions_db, **store_options)
    try:
        session = store.create_session(model=config.model)
        attach_event_recorder(bus, store)
        loop = AgentLoop(provider, registry, policy, bus)
    except BaseException:
        store.close()
        raise
    return Composition(loop=loop, bus=bus, store=store, session_id=session.id, notices=notices)
