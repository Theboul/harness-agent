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
import platform
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
    EXPORT_FILE_NAME,
    SessionStoreError,
    SqliteSessionStore,
    SqliteTaskStore,
    attach_event_recorder,
)
from harness_agent.adapters.system import (
    ProtectedPaths,
    WorkspaceArea,
    environment_notice,
    interpreter_for,
    select_shell,
)
from harness_agent.adapters.tools import (
    ListFilesTool,
    ReadFileTool,
    SearchTextTool,
    ShellTool,
    WriteFileTool,
)
from harness_agent.cli import ConsoleApprover, run_cli
from harness_agent.config import (
    PROVIDER_KEY_VARIABLES,
    ConfigError,
    HarnessConfig,
    load_config,
    process_environment,
)
from harness_agent.core import (
    Approver,
    AuthorizedArea,
    DefaultPermissionPolicy,
    EventBus,
    InMemoryEventBus,
    InMemoryToolRegistry,
    Message,
    ProtectedPolicy,
    Provider,
    Role,
    SessionLimits,
    TaskDefinition,
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

TASKS_DIR_NAME = "tareas"
_DATABASE_SIDE_FILES = ("-wal", "-shm", "-journal")

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
        session_id: Identifier of the session created for this run (the task's, if there is one).
        notices: Startup notices for the user (missing or unusable work area); usually empty.
        history_prefix: Messages that open every conversation (the environment notice for the
            model); the session history starts as a copy of them.
    """

    loop: AgentLoop
    bus: EventBus
    store: SqliteSessionStore
    session_id: str
    notices: tuple[str, ...]
    history_prefix: tuple[Message, ...] = ()
    task_store: SqliteTaskStore | None = None
    task: TaskDefinition | None = None
    criteria_export: Path | None = None

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


def _protection(
    database: Path, workspace: Path | None
) -> tuple[Path, tuple[Path, ...], tuple[Path, ...], tuple[str, ...]]:
    """What the agent tools must never reach: ``(exports_dir, files, folders, shell_markers)``.

    The folder of the sessions database is protected whole. If the work area lives inside it (or
    is it), protecting the whole folder would lock the agent out of its own work, so only the
    database files and the folder of the criteria copies are protected then.
    """
    harness_dir = database.parent
    exports_dir = harness_dir / TASKS_DIR_NAME
    files = (database, *(database.with_name(database.name + tail) for tail in _DATABASE_SIDE_FILES))
    markers = [database.name, EXPORT_FILE_NAME]
    if workspace is not None and _inside(workspace, harness_dir):
        return exports_dir, files, (exports_dir,), tuple(markers)
    markers.append(harness_dir.name)
    return exports_dir, files, (harness_dir,), tuple(markers)


def _inside(path: Path, folder: Path) -> bool:
    """Whether ``path`` is ``folder`` or lives under it, comparing real, normalized paths."""
    real_path = os.path.normcase(os.path.realpath(path))
    real_folder = os.path.normcase(os.path.realpath(folder))
    return real_path == real_folder or real_path.startswith(real_folder + os.sep)


def compose(
    config: HarnessConfig,
    *,
    task: TaskDefinition | None = None,
    provider_factory: ProviderFactory | None = None,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
    environ: Mapping[str, str] | None = None,
    system_name: str | None = None,
    approver: Approver | None = None,
) -> Composition:
    """Build the connected system from ``config``; nothing is left half open on failure.

    Args:
        config: The loaded configuration.
        task: A validated task to start: its session becomes the run's session and its
            criteria are stored and exported; without it the run starts a plain session.
        provider_factory: Builds the provider from the configuration; defaults to LiteLLM.
        clock: Clock of the session store; defaults to UTC now.
        id_factory: Identifier factory of the session store; defaults to ``uuid4``.
        environ: Environment the shell commands start from (without the provider keys); defaults
            to the one of the running process.
        system_name: Operating system name as ``platform.system()`` gives it; that is the default.
        approver: Asks the user about the actions the policy asks about; without one those
            actions are denied (``main`` passes the terminal one).

    Raises:
        ProviderDependencyError: The optional dependency of the real provider is missing.
        SessionStoreError: The sessions database could not be opened or written.
        SchemaVersionError: The sessions database has an unknown schema version.
    """
    provider = (provider_factory if provider_factory is not None else _default_provider)(config)
    area, notices = _build_area(config.paths.workspace_root)
    system = platform.system() if system_name is None else system_name
    shell = None
    if area is not None:
        shell = select_shell(
            system,
            cwd=area.root,
            environ=process_environment() if environ is None else environ,
            removed_env={name for name in PROVIDER_KEY_VARIABLES.values() if name},
        )
    registry = InMemoryToolRegistry(max_output_chars=config.limits.max_tool_output_chars)
    for tool in (
        ReadFileTool(area),
        WriteFileTool(area),
        ListFilesTool(area),
        SearchTextTool(area),
        ShellTool(shell, area, on_cancel=None if shell is None else shell.terminate_running),
    ):
        registry.register(tool)
    bus = InMemoryEventBus()
    store_options: dict[str, Any] = {}
    if clock is not None:
        store_options["clock"] = clock
    if id_factory is not None:
        store_options["id_factory"] = id_factory
    store = SqliteSessionStore(config.paths.sessions_db, **store_options)
    try:
        exports_dir, files, folders, markers = _protection(
            config.paths.sessions_db, config.paths.workspace_root
        )
        protected = ProtectedPaths(
            area.root if area is not None else Path(config.paths.sessions_db.anchor or os.sep),
            files=files,
            directories=folders,
        )
        policy = ProtectedPolicy(
            DefaultPermissionPolicy(registry, area, config.permissions), protected, markers
        )
        task_options: dict[str, Any] = dict(store_options)
        task_store = SqliteTaskStore(store, exports_dir=exports_dir, bus=bus, **task_options)
        export: Path | None = None
        if task is None:
            session_id = store.create_session(model=config.model).id
        else:
            started = task_store.start_task(task, model=config.model)
            session_id, export = started.session_id, started.export_path
        attach_event_recorder(bus, store)
        # The limits of the session are mapped here: the core does not import ``config`` (HU-01-06).
        # ``max_tokens`` is the budget of the whole run, never the cap of one call.
        limits = SessionLimits(
            max_turns=config.limits.max_turns,
            max_seconds=config.limits.max_seconds,
            max_tokens=config.limits.max_tokens,
        )
        loop = AgentLoop(provider, registry, policy, bus, approver=approver, limits=limits)
    except BaseException:
        store.close()
        raise
    notice = Message(role=Role.SYSTEM, content=environment_notice(system, interpreter_for(system)))
    return Composition(
        loop=loop,
        bus=bus,
        store=store,
        session_id=session_id,
        notices=notices,
        history_prefix=(notice,),
        task_store=task_store,
        task=task,
        criteria_export=export,
    )


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
    history: list[Message] = list(composition.history_prefix)

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
                config,
                provider_factory=provider_factory,
                clock=clock,
                id_factory=id_factory,
                environ=environ,
                approver=ConsoleApprover(input_stream, output),
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
