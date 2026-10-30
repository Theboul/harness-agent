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
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
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
    SqliteCompactionArchive,
    SqliteEssentialStore,
    SqliteMessageStore,
    SqliteSessionStore,
    SqliteTaskStore,
    attach_event_recorder,
)
from harness_agent.adapters.system import (
    ProtectedPaths,
    WorkspaceArea,
    denied_commands_for,
    environment_notice,
    interpreter_for,
    option_synonyms_for,
    program_aliases_for,
    select_shell,
)
from harness_agent.adapters.tools import (
    COMMAND_ARGUMENT,
    DEFAULT_SHELL_TIMEOUT_SECONDS,
    TIMEOUT_ARGUMENT,
    ListFilesTool,
    ReadFileTool,
    SearchTextTool,
    ShellTool,
    WriteFileTool,
    make_command_runner,
)
from harness_agent.cli import (
    ConsoleApprover,
    ModelView,
    SessionRow,
    attach_criteria_status,
    format_compaction,
    format_model,
    format_new_session,
    format_sessions,
    run_cli,
)
from harness_agent.config import (
    PROVIDER_KEY_VARIABLES,
    ConfigError,
    HarnessConfig,
    load_config,
    process_environment,
)
from harness_agent.core import (
    AllowedCall,
    ApprovalGate,
    Approver,
    AuthorizedArea,
    CommandPolicy,
    ContextCompactor,
    ContextSettings,
    ConversationCapture,
    ConversationSaveError,
    CriteriaVerifier,
    DefaultPermissionPolicy,
    DenyList,
    Dialect,
    EssentialContextError,
    EssentialItem,
    EssentialRenewer,
    Event,
    EventBus,
    EventType,
    ExactCallPolicy,
    GitPolicy,
    InMemoryEventBus,
    InMemoryToolRegistry,
    Message,
    PermissionPolicy,
    ProtectedPolicy,
    Provider,
    ResumeError,
    Role,
    RuleError,
    SessionLimits,
    TaskCommand,
    TaskDefinition,
    ToolDefinition,
    VerifyingRunner,
    check_creation,
    check_session_id,
    commands_notice,
    compile_rule,
    criteria_reference,
    git_instructions,
    make_items,
    rejection_message,
    resume_session,
    threshold_tokens,
)
from harness_agent.core.loop import AgentLoop, TurnResult

NO_AREA_NOTICE = (
    "Aviso: no hay área de trabajo configurada (paths.workspace_root); "
    "las herramientas de archivos están desactivadas."
)
AREA_NOT_A_FOLDER_NOTICE = (
    "Aviso: el área de trabajo configurada no es una carpeta; "
    "las herramientas de archivos están desactivadas."
)

EXIT_STARTUP = 2
DENY_COMMANDS_NOT_UNDERSTOOD = (
    "una entrada de permissions.deny_commands no se entiende para {interpreter}."
)
ADDED_BY_CONFIGURATION = "Añadido por la configuración."
GIT_FOLDER_NAME = ".git"
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


class WarningSink:
    """Where the compactor writes its warnings: the output of the session once it runs.

    The compactor is built before the session has an output, so it writes through this sink;
    ``run_session`` points it at the stream it was given (standard output until then).
    """

    def __init__(self) -> None:
        self.stream: TextIO | None = None

    def write(self, text: str) -> None:
        """Write one line of warning to the stream of the session."""
        _write_notice(sys.stdout if self.stream is None else self.stream, text)


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
    runner: VerifyingRunner[TurnResult] | None = None
    compactor: ContextCompactor | None = None
    warning_sink: WarningSink = field(default_factory=WarningSink)
    essential: EssentialRenewer | None = None
    capture: ConversationCapture | None = None
    messages: SqliteMessageStore | None = None
    compactor_for: Callable[[str], ContextCompactor] | None = None
    model: str = ""
    model_view: ModelView | None = None
    manual_compactor_for: Callable[[str], ContextCompactor] | None = None

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

    The ``.git`` folder of the work area is protected too (HU-11-02): its configuration could make
    a git read that runs without asking execute a program. The protected area does not tell reads
    from writes, so the file tools cannot read it either; ``git status``/``log``/``show`` can. It
    is not a shell marker (``.git`` appears in harmless commands such as ``cat .gitignore``).
    """
    harness_dir = database.parent
    exports_dir = harness_dir / TASKS_DIR_NAME
    files = (database, *(database.with_name(database.name + tail) for tail in _DATABASE_SIDE_FILES))
    markers = [database.name, EXPORT_FILE_NAME]
    repository = () if workspace is None else (workspace / GIT_FOLDER_NAME,)
    if workspace is not None and _inside(workspace, harness_dir):
        return exports_dir, files, (exports_dir, *repository), tuple(markers)
    markers.append(harness_dir.name)
    return exports_dir, files, (harness_dir, *repository), tuple(markers)


def _inside(path: Path, folder: Path) -> bool:
    """Whether ``path`` is ``folder`` or lives under it, comparing real, normalized paths."""
    real_path = os.path.normcase(os.path.realpath(path))
    real_folder = os.path.normcase(os.path.realpath(folder))
    return real_path == real_folder or real_path.startswith(real_folder + os.sep)


def _allowed_commands(commands: tuple[TaskCommand, ...], tool: str) -> tuple[AllowedCall, ...]:
    """The calls to the shell that the commands of the task allow, exactly (HU-11-03).

    Without a time in the call the shell applies its default, so that is what is compared with the
    limit of each command.
    """
    return tuple(
        AllowedCall(
            tool=tool,
            argument=COMMAND_ARGUMENT,
            value=command.command,
            limit_argument=TIMEOUT_ARGUMENT,
            limit=command.timeout_seconds,
            default_limit=DEFAULT_SHELL_TIMEOUT_SECONDS,
        )
        for command in commands
    )


def _deny_list(interpreter: str, added: tuple[str, ...]) -> DenyList:
    """The deny list of the interpreter: its base list plus what the configuration adds.

    Raises:
        StartupError: An added entry is not understood (the message never repeats it).
    """
    dialect = Dialect(interpreter)
    aliases = program_aliases_for(interpreter)
    synonyms = option_synonyms_for(interpreter)
    base = [
        compile_rule(
            entry.pattern,
            entry.reason,
            dialect,
            aliases=aliases,
            synonyms=synonyms,
            allow_literal=True,
        )
        for entry in denied_commands_for(interpreter)
    ]
    try:
        extra = [
            compile_rule(text, ADDED_BY_CONFIGURATION, dialect, aliases=aliases, synonyms=synonyms)
            for text in added
        ]
    except RuleError:
        message = DENY_COMMANDS_NOT_UNDERSTOOD.format(interpreter=interpreter)
        raise StartupError(message) from None
    return DenyList(dialect, base, extra, aliases=aliases, synonyms=synonyms)


def _provisional_prefix(
    system: str, area: AuthorizedArea | None, commands: tuple[TaskCommand, ...]
) -> list[tuple[str, Message]]:
    """The system messages that open every conversation, each with the origin it is recorded under.

    They are the instructions of the model (HU-01-04, HU-11-02, HU-11-03) and depend on nothing
    that is opened later, so they are built before the store is.
    """
    pairs = [
        (
            "entorno",
            Message(role=Role.SYSTEM, content=environment_notice(system, interpreter_for(system))),
        )
    ]
    if area is not None:
        # How to use git in the task (HU-11-02, Sp2-44); provisional until HU-02-01 assembles it.
        pairs.append(("git", Message(role=Role.SYSTEM, content=git_instructions())))
    commands_text = commands_notice(commands)
    if commands_text is not None:
        pairs.append(("comandos", Message(role=Role.SYSTEM, content=commands_text)))
    return pairs


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
    # Compiled before anything is opened: a bad entry of the configuration stops the start.
    deny_list = _deny_list(interpreter_for(system), config.deny_commands)
    registry = InMemoryToolRegistry(max_output_chars=config.limits.max_tool_output_chars)
    shell_tool = ShellTool(
        shell, area, on_cancel=None if shell is None else shell.terminate_running
    )
    for tool in (
        ReadFileTool(area),
        WriteFileTool(area),
        ListFilesTool(area),
        SearchTextTool(area),
        shell_tool,
    ):
        registry.register(tool)
    commands = () if task is None else task.commands
    provisional = _provisional_prefix(system, area, commands)
    essential: tuple[EssentialItem, ...] = ()
    if task is not None:
        # The essential context of the task (HU-02-06.1) is checked before anything is opened, so a
        # value over its cap or a block that does not fit never leaves a session behind.
        try:
            essential = make_items(
                ticket=task.title,
                objective=task.objective,
                rules=task.rules,
                instructions=[(origin, message.content) for origin, message in provisional],
            )
            check_creation(
                essential,
                [criterion.description for criterion in task.criteria],
                config.context,
                config.model,
            )
        except EssentialContextError as error:
            raise StartupError(str(error)) from None
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
        # Deny > ask > allow: the protection decides first; then the deny list of the shell
        # (HU-05-02) denies before anything else is asked and never lets a command it does not
        # understand be allowed; then the git rules (HU-11-02) deny destructive git calls, ask
        # writes without asking further in and allow pure reads; only then may the exact commands
        # of the task turn the "ask" of the default policy into "allow" (HU-11-03).
        policy = ProtectedPolicy(
            CommandPolicy(
                GitPolicy(
                    ExactCallPolicy(
                        DefaultPermissionPolicy(registry, area, config.permissions),
                        _allowed_commands(commands, shell_tool.name),
                        ask_names=config.permissions.ask,
                    ),
                    dialect=deny_list.dialect,
                    tool=shell_tool.name,
                    argument=COMMAND_ARGUMENT,
                    deny_names=config.permissions.deny,
                    ask_names=config.permissions.ask,
                ),
                deny_list,
                tool=shell_tool.name,
                argument=COMMAND_ARGUMENT,
            ),
            protected,
            markers,
        )
        task_options: dict[str, Any] = dict(store_options)
        clock_options: dict[str, Any] = {} if clock is None else {"clock": clock}
        renewer: EssentialRenewer | None = None
        task_store = SqliteTaskStore(store, exports_dir=exports_dir, bus=bus, **task_options)
        export: Path | None = None
        if task is None:
            session_id = store.create_session(model=config.model).id
        else:
            started = task_store.start_task(task, model=config.model)
            session_id, export = started.session_id, started.export_path
            # A second transaction (the task store is not touched): if it fails the start stops, the
            # store is closed below and no composition exists (R17). The reference is the session.
            elements = SqliteEssentialStore(store, **clock_options)
            elements.save_items(session_id, (*essential, criteria_reference(session_id)))
            renewer = EssentialRenewer(
                elements,
                task_store,
                config.context,
                session_id=session_id,
                model=lambda: config.model,
            )
        # The archive stores ``context_compacted`` in its own transaction (HU-02-03): the recorder
        # must not store it again. The ``skip`` goes by position.
        warning_sink = WarningSink()
        messages: SqliteMessageStore | None = None
        capture: ConversationCapture | None = None
        if task is None:
            # The messages of the conversation are saved when the bus publishes each event, and
            # **before** the event recorder: a cut leaves a message with no event, never an event
            # with no message (HU-03-04, FR-034). A session with a task is not resumable (Q3), so
            # nothing more is written for it.
            messages = SqliteMessageStore(store, **clock_options)
            capture = ConversationCapture(
                messages,
                warn=warning_sink.write,
                rejected_text=lambda name: rejection_message(name, None),
            )
            for kind in (
                EventType.USER_MESSAGE,
                EventType.ASSISTANT_MESSAGE,
                EventType.TOOL_REQUESTED,
                EventType.TOOL_FINISHED,
            ):
                bus.subscribe(kind, capture.on_event)
        attach_event_recorder(bus, store, (EventType.CONTEXT_COMPACTED,))
        # The limits of the session are mapped here: the core does not import ``config`` (HU-01-06).
        # ``max_tokens`` is the budget of the whole run, never the cap of one call.
        limits = SessionLimits(
            max_turns=config.limits.max_turns,
            max_seconds=config.limits.max_seconds,
            max_tokens=config.limits.max_tokens,
        )
        loop = AgentLoop(provider, registry, policy, bus, approver=approver, limits=limits)
        compactor = _compactor(
            provider, store, config, session_id, registry, bus, warning_sink, clock, id_factory
        )

        def compactor_for(session: str) -> ContextCompactor:
            """The compactor of another session of this run (HU-03-04); the logic is the same."""
            return _compactor(
                provider, store, config, session, registry, bus, warning_sink, clock, id_factory
            )

        def manual_compactor_for(session: str) -> ContextCompactor:
            """The compactor behind ``/compactar`` (HU-06-05): same logic, threshold forced low.

            Its own warnings are silenced: the compaction line the person asked for is the answer.
            """
            return _compactor(
                provider,
                store,
                config,
                session,
                registry,
                bus,
                warning_sink,
                clock,
                id_factory,
                settings=forced_context_settings(config.context),
                warn=_discard,
            )

        runner: VerifyingRunner[TurnResult] | None = None
        if task is not None:
            runner = _verifying_runner(
                loop,
                task,
                task_store,
                policy,
                registry,
                shell_tool,
                bus,
                session_id,
                approver,
                clock,
                id_factory,
                renewer,
                warning_sink,
            )
    except BaseException:
        store.close()
        raise
    prefix = [message for _, message in provisional]
    return Composition(
        loop=loop,
        bus=bus,
        store=store,
        session_id=session_id,
        notices=notices,
        history_prefix=tuple(prefix),
        task_store=task_store,
        task=task,
        criteria_export=export,
        runner=runner,
        compactor=compactor,
        warning_sink=warning_sink,
        essential=renewer,
        capture=capture,
        messages=messages,
        compactor_for=compactor_for,
        model=config.model,
        model_view=ModelView(
            model=config.model,
            window_tokens=config.context.window_for(config.model),
            threshold_tokens=threshold_tokens(config.context, config.model),
            max_turns=config.limits.max_turns,
            max_seconds=config.limits.max_seconds,
            max_tokens=config.limits.max_tokens,
            max_output_tokens=config.limits.max_output_tokens,
        ),
        manual_compactor_for=manual_compactor_for,
    )


def _discard(_text: str) -> None:
    """A warning sink that says nothing."""


def forced_context_settings(settings: ContextSettings) -> ContextSettings:
    """``settings`` with the lowest threshold the core accepts, for a compaction asked by hand.

    The smallest window with the smallest percentage gives a threshold of 100 tokens, whatever the
    model; the share of recent messages kept whole and the size of the summary do not change.
    """
    return replace(settings, window_tokens=1_000, windows=(), threshold_percent=10)


def _compactor(
    provider: Provider,
    store: SqliteSessionStore,
    config: HarnessConfig,
    session_id: str,
    registry: InMemoryToolRegistry,
    bus: EventBus,
    warning_sink: WarningSink,
    clock: Callable[[], datetime] | None,
    id_factory: Callable[[], str] | None,
    *,
    settings: ContextSettings | None = None,
    warn: Callable[[str], None] | None = None,
) -> ContextCompactor:
    """The compactor of the context (HU-02-03), connected to the pieces of the session.

    ``settings`` and ``warn`` default to the configured ones and to the warning sink of the run.

    It only connects: the archive works on the session store, the model and the window come from
    the configuration, the tool declarations are the ones the loop sends, and the summary event
    (already stored by the archive) goes out through the bus.
    """
    archive_options: dict[str, Any] = {} if clock is None else {"clock": clock}

    def emit(kind: EventType, payload: dict[str, Any]) -> None:
        bus.emit(
            Event.create(
                session_id,
                kind,
                payload,
                event_id=None if id_factory is None else id_factory(),
                timestamp=None if clock is None else clock(),
            )
        )

    def definitions() -> list[ToolDefinition]:
        return [
            ToolDefinition(name=tool.name, description=tool.description, parameters=tool.schema)
            for tool in registry.list()
        ]

    return ContextCompactor(
        provider,
        SqliteCompactionArchive(store, **archive_options),
        config.context if settings is None else settings,
        session_id=session_id,
        model=lambda: config.model,
        definitions=definitions,
        emit=emit,
        publish=bus.emit,
        warn=warning_sink.write if warn is None else warn,
        new_id=id_factory if id_factory is not None else lambda: str(uuid.uuid4()),
    )


def _verifying_runner(
    loop: AgentLoop,
    task: TaskDefinition,
    task_store: SqliteTaskStore,
    policy: PermissionPolicy,
    registry: InMemoryToolRegistry,
    shell_tool: ShellTool,
    bus: EventBus,
    session_id: str,
    approver: Approver | None,
    clock: Callable[[], datetime] | None,
    id_factory: Callable[[], str] | None,
    renewer: EssentialRenewer | None,
    warning_sink: WarningSink,
) -> VerifyingRunner[TurnResult]:
    """The runner that verifies the criteria of ``task`` each time the agent proposes to finish.

    It only connects pieces (HU-11-04.1): the policy and the shell tool are the ones of the agent,
    the approver is the one of the session (the verifier keeps its own gate) and the time limits
    of the commands the task declares are handed over so an identical criterion command inherits
    them.
    """

    def emit(kind: EventType, payload: dict[str, Any]) -> None:
        bus.emit(
            Event.create(
                session_id,
                kind,
                payload,
                event_id=None if id_factory is None else id_factory(),
                timestamp=None if clock is None else clock(),
            )
        )

    verifier = CriteriaVerifier(
        task_store,
        task,
        policy,
        shell_tool,
        make_command_runner(registry, shell_tool.name),
        emit,
        gate=None if approver is None else ApprovalGate(approver),
        tool_name=shell_tool.name,
        command_argument=COMMAND_ARGUMENT,
        timeout_argument=TIMEOUT_ARGUMENT,
        declared_timeouts={command.command: command.timeout_seconds for command in task.commands},
    )

    async def run_turn(text: str, history: list[Message]) -> TurnResult:
        # Before each round: the criteria the verifier marked after the last one show in the block.
        _renew_or_report(renewer, history, warning_sink)
        return await loop.run_turn(session_id=session_id, task=text, history=history)

    return VerifyingRunner(run_turn, verifier, session_id)


@dataclass
class _Active:
    """Which session the terminal is working on, and the compactor that belongs to it."""

    session_id: str
    compactor: ContextCompactor | None
    closures: list[tuple[str, str]] = field(default_factory=list)


READ_FAILED = "No se pudo leer la sesión; la sesión actual sigue sin cambios."
RESUME_NOT_AVAILABLE = "Reanudar no está disponible en esta sesión."
LIST_FAILED = "No se pudo leer la lista de sesiones."
MODEL_NOT_AVAILABLE = "Modelo no disponible en esta ejecución."
COMPACT_NOT_AVAILABLE = "Compactar no está disponible en esta ejecución."
NEW_NOT_AVAILABLE = "Nueva sesión no está disponible en esta ejecución."
NEW_FAILED = "No se pudo crear la sesión nueva; la sesión actual sigue sin cambios."


def _compact_command(
    composition: Composition, active: _Active, history: list[Message]
) -> Callable[[], Awaitable[str]]:
    """The function behind ``/compactar`` (HU-06-05): compact the context now, whatever its size.

    The compactor is the one of ``compose`` with a forced low threshold, so it summarizes the old
    messages as the automatic one would (same cut, same archive, same checks). When it finds nothing
    to summarize, or it fails (it reports the failure itself and leaves the view untouched), the
    answer is one fixed line. A cancellation goes up.
    """
    factory = composition.manual_compactor_for

    async def compact() -> str:
        if factory is None:
            return COMPACT_NOT_AVAILABLE
        # As before any request: the calls a cut left without a result get their closing first.
        _close_interrupted(composition.bus, active)
        return format_compaction(await factory(active.session_id).before_turn(history))

    return compact


def _new_command(
    composition: Composition, active: _Active, history: list[Message]
) -> Callable[[], str]:
    """The function behind ``/nueva`` (HU-06-05): a clean conversation in a new session.

    It follows what ``/reanudar`` does to switch: the history is replaced in place by the prefix,
    the saving of the messages is bound to the new session and its compactor becomes the active
    one. The session that is left stays saved and can be resumed. The limits of the run are not
    reset (they live in the loop). A session with a task, or a composition without the pieces to
    save messages, refuses; any failure leaves the current session as it was.
    """
    capture, factory = composition.capture, composition.compactor_for

    def new_session() -> str:
        if capture is None or composition.messages is None or factory is None:
            return NEW_NOT_AVAILABLE
        if composition.runner is not None:
            return NEW_NOT_AVAILABLE
        try:
            session = composition.store.create_session(model=composition.model).id
            compactor = factory(session)
        except Exception:
            return NEW_FAILED
        history[:] = composition.history_prefix
        active.session_id = session
        active.compactor = compactor
        active.closures.clear()
        capture.bind(session, history, 1, len(history))
        return format_new_session(session)

    return new_session


def _sessions_command(composition: Composition, active: _Active) -> Callable[[], str]:
    """The function behind ``/sesiones`` (HU-06-05): it never raises and writes nothing.

    It lists the sessions of the user (subagent sessions are left out) with the current one marked.
    """

    def sessions() -> str:
        store = composition.store
        try:
            rows = []
            for summary in store.list_sessions():
                detail = store.get_session(summary.id)
                if detail is not None and detail.parent_id is not None:
                    continue
                rows.append(
                    SessionRow(
                        id=summary.id,
                        created_at=summary.created_at,
                        status=summary.status,
                        model=summary.model,
                        goal=summary.goal,
                        current=summary.id == active.session_id,
                    )
                )
        except Exception:
            return LIST_FAILED
        return format_sessions(rows)

    return sessions


def _model_command(composition: Composition) -> Callable[[], str]:
    """The function behind ``/model``: the model and the limits in force, never a secret."""

    def model() -> str:
        view = composition.model_view
        return MODEL_NOT_AVAILABLE if view is None else format_model(view)

    return model


def _resume_command(
    composition: Composition, active: _Active, history: list[Message]
) -> Callable[[str], str]:
    """The function behind ``/reanudar <id>`` (HU-03-04): it never raises, it returns one line.

    On success it replaces the history in place, makes the resumed session the active one and
    binds the saving of the messages to it; the session that is left is not touched again.
    """
    capture, source, factory = composition.capture, composition.messages, composition.compactor_for

    def resume(argument: str) -> str:
        if capture is None or source is None or factory is None or composition.runner is not None:
            return RESUME_NOT_AVAILABLE
        try:
            resumed = resume_session(
                source,
                argument,
                prefix=composition.history_prefix,
                current_model=composition.model,
                current_session_id=active.session_id,
                known_incomplete=capture.incomplete_sessions,
            )
            session = check_session_id(argument)
            compactor = factory(session)
        except ResumeError as error:
            return str(error)
        except Exception:
            return READ_FAILED
        history[:] = resumed.history
        active.session_id = session
        active.compactor = compactor
        active.closures[:] = resumed.closed_calls
        capture.bind(session, history, resumed.next_position, resumed.saved_count)
        return resumed.notice

    return resume


def _close_interrupted(bus: EventBus, active: _Active) -> None:
    """Publish the closing event of each call that a cut left without a result (HU-03-04).

    The result was rebuilt in the history when the session was resumed; the event makes it a real
    one (the capture saves the message and the recorder the event), so the history that is stored
    stays coherent and the compaction keeps working. A closure leaves the list only once it was
    published, and the list is rebuilt from what is stored every time a session is resumed, so a
    call is closed once.
    """
    while active.closures:
        call_id, name = active.closures[0]
        payload = {
            "call_id": call_id,
            "name": name,
            "is_error": True,
            "category": "tool_interrupted",
        }
        bus.emit(Event.create(active.session_id, EventType.TOOL_FINISHED, payload))
        del active.closures[0]


def _flush_quietly(capture: ConversationCapture | None) -> None:
    """Save what is pending while another failure goes up; a failure of its own was already told."""
    if capture is None:
        return
    try:
        capture.flush()
    except ConversationSaveError:
        pass


def _renew_or_report(
    renewer: EssentialRenewer | None, history: list[Message], sink: WarningSink
) -> None:
    """Renew the essential block; if it cannot be, write the fixed message and let it fail.

    A session without a task has no renewer and nothing happens. With a task, a block that does not
    fit or elements that cannot be read stop the request before the model sees it (HU-02-06.1).
    """
    if renewer is None:
        return
    try:
        renewer.renew(history)
    except EssentialContextError as error:
        sink.write(str(error))
        raise


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
    composition.warning_sink.stream = stream
    for notice in composition.notices:
        _write_notice(stream, notice)
    history: list[Message] = list(composition.history_prefix)
    capture = composition.capture
    if capture is not None and composition.messages is not None:
        last = composition.messages.last_position(composition.session_id)
        capture.bind(composition.session_id, history, last + 1, len(history))

    runner = composition.runner
    active = _Active(composition.session_id, composition.compactor)

    async def run_turn(task: str) -> object:
        try:
            result = await turn(task)
        except BaseException:
            _flush_quietly(capture)
            raise
        if capture is not None:
            capture.flush()  # an empty answer has no event; it is saved when the turn closes
        return result

    async def turn(task: str) -> object:
        # First the calls a cut left without a result: each gets its closing event, once (R21).
        _close_interrupted(composition.bus, active)
        # First the block (so the estimate of the compaction sees it), then the compaction.
        _renew_or_report(composition.essential, history, composition.warning_sink)
        if active.compactor is not None:
            # Before the request reaches the loop (and the verifier): the view is replaced in place.
            await active.compactor.before_turn(history)
        if runner is not None:
            return await runner.run(task, history)
        return await composition.loop.run_turn(
            session_id=active.session_id, task=task, history=history
        )

    commands: dict[str, tuple[str, Callable[[], str | Awaitable[str]]]] = {
        "/sesiones": ("Lista las sesiones guardadas.", _sessions_command(composition, active)),
        "/nueva": ("Empieza una sesión nueva.", _new_command(composition, active, history)),
        "/compactar": (
            "Compacta el contexto ahora.",
            _compact_command(composition, active, history),
        ),
        "/model": ("Muestra el modelo y los límites.", _model_command(composition)),
    }
    if runner is not None:
        board = attach_criteria_status(composition.bus, stream)
        commands["/criterios"] = ("Muestra el estado de los criterios.", board.report)
    resume = (
        "Reanuda una sesión guardada por su identificador.",
        _resume_command(composition, active, history),
    )
    return await run_cli(
        composition.bus,
        run_turn,
        input_stream=input_stream,
        output=stream,
        commands=commands,
        argument_commands={"/reanudar": resume},
    )


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
