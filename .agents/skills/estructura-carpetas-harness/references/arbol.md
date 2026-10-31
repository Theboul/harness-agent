# Árbol del repositorio

Leyenda: sin marca = existe hoy · `(planeado: HU-xx-yy)` = se crea con esa historia, no antes (Principio VI).

```
harness-agent/
├── pyproject.toml          # paquete, pytest, mypy estricto, ruff (línea 100), cobertura
├── requirements-dev.txt    # versiones fijadas para la CI
├── README.md
├── CLAUDE.md               # contexto base de cada sesión por historia
├── .env.example            # nombres de las variables de clave, sin valores
├── config.example.toml     # modelo, límites, rutas, [permissions] deny/ask
├── .github/workflows/ci.yml  # ruff format, ruff check, mypy, pytest en Ubuntu y Windows (Py 3.12)
├── .specify/               # Spec Kit: constitución (memory/constitution.md), plantillas, scripts, feature.json
├── .claude/skills/, .agents/skills/  # skills (copias idénticas para cada agente)
├── specs/NNN-slug/         # una carpeta por historia: spec, plan, research, data-model, contracts/, tasks, quickstart
├── docs/
│   ├── 00-indice.md                # mapa de la documentación y dónde está cada ID
│   ├── 01-vision-y-decisiones.md   # equipo, alcance, decisiones V-01 a V-17, DoD
│   ├── 02-arquitectura.md          # diagramas, contratos (§4), eventos, modelo de datos SQLite
│   ├── 03-plan-sprints.md          # pruebas, riesgos, épicas, sprints, tareas Sp*-xx
│   ├── 04a..04e-historias-*.md     # fichas de historias por épica (ancla #hu-xx-yy)
│   ├── 05-trazabilidad.md          # requisito -> historia
│   ├── 06-historial-planificacion.md  # auditoría, decisiones PD, capacidad
│   ├── PROGRESO.md                 # única fuente de estado y evidencia
│   ├── guia-contratos-desarrollo.md   # cómo consumir contratos y dobles
│   ├── decisiones/                 # D-01 (asyncio), D-02 (envelope), revisión conjunta
│   ├── archivo/                    # históricos: NO se editan
│   └── demo.md                     # (planeado: HU-00-06) guion de demostración
├── src/harness_agent/
│   ├── core/               # NÚCLEO: solo stdlib y harness_agent.core
│   │   ├── __init__.py     # API pública del núcleo (__all__): todo consumidor importa de aquí
│   │   ├── entities.py     # Role, Message, ToolCall, ToolResult, TokenUsage (frozen)
│   │   ├── events.py       # EventType (17 tipos) y Event
│   │   ├── interfaces/     # PUERTOS (ABC), ver tabla abajo
│   │   ├── loop.py         # AgentLoop: bucle razonar–actuar–observar (HU-01-01)
│   │   ├── in_memory_event_bus.py  # InMemoryEventBus, EventDeliveryError (HU-01-05)
│   │   ├── redaction.py    # hide_url_credentials, HIDDEN_SECRET (HU-11-02); provisional: HU-10-02 la absorberá (observability/ no es importable desde adapters/tools ni bootstrap)
│   │   ├── tools/          # InMemoryToolRegistry, validador JSON Schema propio, errores (HU-01-02); output_limit.py: recorte general de salidas, TruncatingTool (HU-02-02)
│   │   ├── permissions/    # DefaultPermissionPolicy, PermissionRules (HU-05-01); protected.py: ProtectedPolicy, decorador que solo deniega (HU-11-01); exact_calls.py: AllowedCall, ExactCallPolicy, permite solo la llamada exacta declarada tras un «preguntar» (HU-11-03); command_parser.py (analizador de comandos bash/PowerShell, sin shlex), command_rules.py (CompiledRule, DenyList, lista de denegados compilada) y command_policy.py (CommandPolicy, solo endurece) (HU-05-02); git_table.py (tabla de subcomandos de git, solo datos, la revisa el PO) y git_rules.py (classify_git, GitPolicy, git_instructions) (HU-11-02); approvals.py: ApprovalGate, aprobación una vez/sesión con falla cerrada (HU-05-03), y `clean_reason`/`rejection_message`, que componen el texto del rechazo con el motivo saneado (HU-05-04)
│   │   ├── tasks/          # TaskDefinition, CriterionDefinition, parse_task, TaskFormatError: formato y validación de la tarea (HU-11-01); commands.py: TaskCommand, CommandKind, commands_notice, sección «## Comandos» (HU-11-03); condition.py: Condition, parse_condition, condition_met: la condición esperada de un criterio (`codigo_salida == N` / `!= N`, HU-11-04.1)
│   │   ├── progress/       # HU-11-08.1: ProgressRecorder (punto de control por turno y final), ProgressSnapshot, render_progress (formato fijo), progress_file_name, ProgressSink (puerto local: el destino lo inyecta bootstrap.py; el archivo lo escribe `adapters/storage/progress_file.py` con renombrado atómico)
│   │   ├── startup/        # HU-11-08.2: StartupRoutine (progreso + log de git + prueba básica al reanudar un ticket), build_briefing (marco de datos y aviso fijo), GatedCommandRunner (política → aprobación → ejecución de un comando); solo stdlib y núcleo, las lecturas y los comandos los inyecta bootstrap.py
│   │   ├── verification/   # HU-11-04.1: CriteriaVerifier (único escritor de passes), VerifyingRunner (ronda de corrección), compose_feedback, evidence_text, task_state, CommandOutcome
│   │   ├── limits.py       # HU-01-06: SessionLimits, LimitTracker (turnos = llamadas al modelo, tiempo, tokens)
│   │   ├── context/        # HU-02-01: estimación, prefijo estable, ContextAssembler; HU-02-03: compactación automática (settings.py umbral por modelo, cut.py corte seguro, summary.py prompt/transcripción/marco del resumen, store.py protocolo CompactionStore, compactor.py ContextCompactor); el ensamblador y el compactador aún no están en el bucle (la compactación corre en run_session); HU-02-06.1: essential.py (contexto esencial: elementos, topes, texto del bloque, marca) y renewer.py (EssentialRenewer, protocolos de solo lectura; solo lo llama la composición); HU-03-04: conversation.py (MessageRecord, clean_message, ConversationCapture: guarda cada mensaje real cuando el bus publica su evento) y resume.py (identificador, errores fijos, reconstrucción pura y resume_session)
│   │   └── subagents/      # (planeado: HU-09-01) SubagentRunner, perfiles, resultado estructurado
│   ├── adapters/           # implementaciones de los puertos
│   │   ├── converters/     # formato canónico <-> OpenAI/Anthropic, ConversionEnvelope (HU-07-01)
│   │   ├── providers/      # LiteLLMProvider: un adaptador para cualquier <proveedor>/<modelo>, sin ramas por proveedor; litellm (dependencia opcional) solo aquí y con importlib (HU-07-02); errors.py (RateLimited, subtipo de QuotaExceeded) y retrying_provider.py (envoltura de reintentos con espera exponencial, HU-07-04); el FakeProvider de HU-00-03 vive en tests/doubles/fake_provider.py
│   │   ├── storage/        # SqliteSessionStore: esquema sessions/events, creación de sesión (HU-03-01), save_event/load_session y attach_event_recorder (HU-03-02); esquema v2 con criterios (migración), SqliteTaskStore y copia de solo lectura con huella (HU-11-01); esquema v3 con `resumenes` y SqliteCompactionArchive (`compaction_archive.py`, HU-02-03: resumen + marcas en `events.compacted_by` + evento `context_compacted` en una transacción; `attach_event_recorder(..., skip=)`); esquema v4 con `contexto_esencial` y SqliteEssentialStore (`essential_store.py`, HU-02-06.1: elementos de la tarea, escritura única, solo lectura después); esquema v5 con `mensajes` y SqliteMessageStore (`message_store.py`, HU-03-04: mensajes de la conversación de una sesión sin tarea, escritura atómica e idempotente, lectura con cobertura de resúmenes)
│   │   ├── tasks/          # load_task_file, load_github_issue (gh inyectable), TaskSourceError (HU-11-01)
│   │   ├── tools/          # leer_archivo, escribir_archivo, listar_archivos, buscar_texto (HU-01-03); shell (HU-01-04); planeado: otras herramientas, …; shell_outcome.py: make_command_runner, outcome_from_result (lee el resultado de `shell`, HU-11-04.1)
│   │   ├── system/         # WorkspaceArea: AuthorizedArea real (rutas reales, «..», enlaces, reglas de Windows) (HU-01-03);
│   │   │                   # shells (HU-01-04): SubprocessShell (tiempo máximo, árbol de procesos, salida acotada), BashShell,
│   │   │                   # PowerShellShell, select_shell/interpreter_for, environment_notice, denied_commands (dato);
│   │   │                   # ProtectedPaths (HU-11-01): AuthorizedArea de lo protegido, `contains` = «protegido»
│   │   └── mcp/            # McpStdioClient: cliente MCP por stdio con una tarea de fondo dueña de la conexión (el SDK exige cerrar en la misma tarea), connect_all/close_all tolerantes a fallos, errores de dominio con texto fijo, entorno del servidor por lista blanca, stderr a archivo; `mcp` (dependencia opcional, extra `mcp`) solo en sdk.py y con importlib (HU-08-01); planeado: traducir a Tool (HU-08-02)
│   ├── observability/      # (planeado: HU-05-05, HU-10-01, HU-10-02) auditoría, trazas, redacción
│   ├── config.py           # load_config(), HarnessConfig, Secret (HU-00-04); sección [mcp_servers.<nombre>] (HU-08-01)
│   ├── config_mcp.py       # McpServerConfig y check_mcp_servers: validación pura de [mcp_servers] que config.py invoca (HU-08-01)
│   ├── bootstrap.py        # RAÍZ DE COMPOSICIÓN: único lugar que une núcleo, adaptadores, CLI y configuración; compose(), run_session(), main() (HU-00-08)
│   ├── __main__.py         # python -m harness_agent: llama a bootstrap.main
│   └── cli/                # terminal: se suscribe al bus (HU-06-01)
│       ├── app.py          # run_cli, attach_renderer, comandos /ayuda y /salir
│       ├── render.py       # render_event: texto de cada evento, sanitizado y acotado
│       ├── approval.py     # ConsoleApprover: muestra el detalle, lee la decisión y el motivo del rechazo (HU-05-03, HU-05-04)
│       ├── criteria.py     # criterion_line, CriteriaBoard, attach_criteria_status: estado de cada criterio y `/criterios` (HU-11-04.1)
│       └── approver.py     # (planeado: HU-05-03) pregunta de aprobación en terminal
└── tests/
    ├── litellm_offline.py  # sustituye el codificador de LiteLLM en memoria para que ninguna prueba descargue nada (HU-07-02)
    ├── doubles/            # dobles compartidos (ScriptedProvider, ScriptedPolicy, RecordingEventBus…); protegido
    ├── unit/               # una prueba por módulo, ruta espejo: unit/core/<pkg>/, unit/cli/, unit/test_config_*.py
    ├── core/               # bucle del agente (support.py: make_rig)
    ├── adapters/           # pruebas de adaptadores (hoy: conversores); las del resto de adaptadores van en unit/adapters/<paquete>/ (p. ej. providers/)
    ├── contracts/          # un contrato que corre contra el doble y la implementación real
    ├── integration/        # piezas reales juntas (AgentLoop + bus/política/registro/CLI)
    ├── architecture/       # guardas AST de fronteras y secretos
    ├── spikes/             # spikes (SPK-01, SPK-02); algunos solo en Linux; conftest.py mantiene offline el de LiteLLM
    └── failures/           # (planeado: HU-00-05.1) fallos: cierre forzado, proveedor caído, MCP caído
```

# Puertos (`core/interfaces/`)

| Archivo | Puertos y tipos | Síncrono / async |
|---|---|---|
| `provider.py` | `Provider`, `ProviderResponse`, `ToolDefinition` | `complete` async |
| `tool.py` | `Tool`, `ToolRegistry`, `RiskLevel` | `Tool.run` async; registro síncrono |
| `security.py` | `PermissionPolicy`, `PermissionDecision`, `Approver`, `ApprovalAction`, `ApprovalResult` | `evaluate` síncrono; `Approver.request` async |
| `storage.py` | `SessionStore`, `SessionSummary`, `MemoryStore`, `MemoryItem` | síncronos |
| `context.py` | `ContextManager`, `CompactResult` | síncronos |
| `system.py` | `Shell`, `ShellResult`, `AuthorizedArea`, `TaskCriteria`, `TaskCriteriaItem` | síncronos |
| `connections.py` | `McpClient`, `SubagentRunner`, `SubagentResult` | async |
| `event_bus.py` | `EventBus`, `EventHandler` | síncronos |

Todos se reexportan en `core/interfaces/__init__.py` y en `core/__init__.py`.

# Reparto de áreas

| Área | Dueño de |
|---|---|
| A (Núcleo) | `core/loop.py`, `core/limits.py`, `core/subagents/`, `core/tasks/`, `adapters/tasks/` (HU-11-01), `adapters/converters/`, segundo proveedor y conmutación (HU-07-03 a HU-07-05) |
| B (Estado) | `adapters/storage/`, `core/context/`, `core/progress/` (HU-11-08.1), `core/in_memory_event_bus.py`, `config.py`, `observability/`, `adapters/providers/` (LiteLLM HU-07-02; el FakeProvider de HU-00-03 vive en `tests/doubles/fake_provider.py`) |
| C (Control y conexiones) | `core/permissions/`, `core/tools/`, `core/startup/` (HU-11-08.2), `adapters/tools/`, `adapters/system/`, `adapters/mcp/`, `cli/` |
| A, B y C juntos | `core/interfaces/`, `core/entities.py`, `core/events.py` (contratos de HU-00-01) |

El responsable de cada historia está en `docs/PROGRESO.md` y manda sobre esta tabla. Cada integrante es dueño de su área; todo cambio lo revisa otra persona.
