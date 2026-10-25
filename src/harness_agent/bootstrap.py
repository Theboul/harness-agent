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

import asyncio
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

from harness_agent.adapters.providers.litellm_provider import (
    LiteLLMProvider,
    ProviderDependencyError,
)
from harness_agent.adapters.storage import (
    SessionStoreError,
    SqliteSessionStore,
    attach_event_recorder,
)
from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools import ListFilesTool, ReadFileTool, SearchTextTool, WriteFileTool
from harness_agent.cli import run_cli
from harness_agent.config import ConfigError, HarnessConfig, load_config
from harness_agent.core import (
    AuthorizedArea,
    DefaultPermissionPolicy,
    EventBus,
    InMemoryEventBus,
    InMemoryToolRegistry,
    Message,
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

EXIT_STARTUP = 2
EXIT_INTERRUPTED = 130
STARTUP_FAILURE_PREFIX = "No se pudo iniciar: "

TEST_ONLY_PROVIDERS = frozenset({"fake"})
TEST_ONLY_PROVIDER_MESSAGE = (
    "El proveedor 'fake' solo existe para pruebas y no se puede usar con el comando; "
    "elija un modelo real en config.toml (por ejemplo <proveedor>/<modelo>)."
)

ProviderFactory = Callable[[HarnessConfig], Provider]


class StartupError(Exception):
    """The system cannot start because of a choice of the user; the message is for the user."""


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
    if config.model.partition("/")[0] in TEST_ONLY_PROVIDERS:
        raise StartupError(TEST_ONLY_PROVIDER_MESSAGE)
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


def _write_notice(stream: TextIO, text: str) -> None:
    """Write one line, replacing what the stream cannot encode (as the terminal render does)."""
    encoding = getattr(stream, "encoding", None)
    line = text + "\n"
    if encoding:
        line = line.encode(encoding, errors="replace").decode(encoding, errors="replace")
    stream.write(line)
    stream.flush()


async def run_session(
    composition: Composition,
    *,
    input_stream: TextIO | None = None,
    output: TextIO | None = None,
) -> int:
    """Run the terminal cycle over ``composition`` and return its exit code (0 or 1).

    The startup notices are written before the first prompt. The conversation history is kept
    between the lines of the session, so each task sees the previous ones.

    Args:
        composition: The connected system.
        input_stream: Where the lines are read from; defaults to standard input.
        output: Where the notices and the events are written; defaults to standard output.
    """
    stream = sys.stdout if output is None else output
    for notice in composition.notices:
        _write_notice(stream, notice)
    history: list[Message] = []

    async def run_turn(task: str) -> object:
        return await composition.loop.run_turn(
            session_id=composition.session_id, task=task, history=history
        )

    return await run_cli(composition.bus, run_turn, input_stream=input_stream, output=stream)


def _report_startup_failure(error: TextIO, text: str) -> int:
    """Write one line (prefix plus ``text`` on a single line) and return the startup exit code."""
    _write_notice(error, STARTUP_FAILURE_PREFIX + " ".join(text.split()))
    return EXIT_STARTUP


def main(
    *,
    environ: Mapping[str, str] | None = None,
    config_path: str | os.PathLike[str] | None = None,
    input_stream: TextIO | None = None,
    output: TextIO | None = None,
    error: TextIO | None = None,
    provider_factory: ProviderFactory | None = None,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> int:
    """Load the configuration, compose the system, run the session and close the store.

    This is the function behind ``python -m harness_agent`` and the ``harness`` command. Every
    parameter is ``None`` in real use; tests inject the environment, the streams and the provider.

    A startup failure is written as one line in Spanish on ``error`` and never shows a trace or the
    text of an unexpected exception (it could hold a secret). A keyboard interrupt ends the whole
    program, with the store closed.

    Returns:
        0 after ``/salir`` or the end of the input, 1 if a turn failed (decided by the CLI),
        ``EXIT_STARTUP`` (2) if the system could not start, ``EXIT_INTERRUPTED`` (130) after a
        keyboard interrupt.
    """
    failures = sys.stderr if error is None else error
    composition: Composition | None = None
    try:
        try:
            config = load_config(config_path, environ=environ)
            composition = compose(
                config, provider_factory=provider_factory, clock=clock, id_factory=id_factory
            )
        except (ConfigError, ProviderDependencyError, SessionStoreError, StartupError) as problem:
            return _report_startup_failure(failures, str(problem))
        except Exception as problem:
            kind = type(problem).__name__
            return _report_startup_failure(failures, f"error inesperado ({kind}).")
        return asyncio.run(run_session(composition, input_stream=input_stream, output=output))
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    finally:
        if composition is not None:
            composition.close()
