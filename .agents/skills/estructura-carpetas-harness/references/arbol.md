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
│   │   ├── tools/          # InMemoryToolRegistry, validador JSON Schema propio, errores (HU-01-02)
│   │   ├── permissions/    # DefaultPermissionPolicy, PermissionRules (HU-05-01)
│   │   ├── limits.py       # (planeado: HU-01-06) turnos, tiempo y consumo
│   │   ├── context/        # (planeado: HU-02-01, HU-02-03) ContextManager, estimación, compactación
│   │   └── subagents/      # (planeado: HU-09-01) SubagentRunner, perfiles, resultado estructurado
│   ├── adapters/           # implementaciones de los puertos
│   │   ├── converters/     # formato canónico <-> OpenAI/Anthropic, ConversionEnvelope (HU-07-01)
│   │   ├── providers/      # (planeado: HU-07-02 litellm_provider; el FakeProvider de HU-00-03 vive en tests/doubles/fake_provider.py)
│   │   ├── storage/        # (planeado: HU-03-01) SQLite: esquema, sesiones, eventos
│   │   ├── tools/          # leer_archivo, escribir_archivo, listar_archivos, buscar_texto (HU-01-03); planeado: shell (HU-01-04), …
│   │   ├── system/         # WorkspaceArea: AuthorizedArea real (rutas reales, «..», enlaces, reglas de Windows) (HU-01-03)
│   │   └── mcp/            # (planeado: HU-08-01) cliente MCP por stdio y traducción a Tool
│   ├── observability/      # (planeado: HU-05-05, HU-10-01, HU-10-02) auditoría, trazas, redacción
│   ├── config.py           # load_config(), HarnessConfig, Secret (HU-00-04)
│   ├── bootstrap.py        # (planeado) RAÍZ DE COMPOSICIÓN: único lugar que une núcleo y adaptadores
│   └── cli/                # terminal: se suscribe al bus (HU-06-01)
│       ├── app.py          # run_cli, attach_renderer, comandos /ayuda y /salir
│       ├── render.py       # render_event: texto de cada evento, sanitizado y acotado
│       └── approver.py     # (planeado: HU-05-03) pregunta de aprobación en terminal
└── tests/
    ├── doubles/            # dobles compartidos (ScriptedProvider, ScriptedPolicy, RecordingEventBus…); protegido
    ├── unit/               # una prueba por módulo, ruta espejo: unit/core/<pkg>/, unit/cli/, unit/test_config_*.py
    ├── core/               # bucle del agente (support.py: make_rig)
    ├── adapters/           # pruebas de adaptadores (hoy: conversores)
    ├── contracts/          # un contrato que corre contra el doble y la implementación real
    ├── integration/        # piezas reales juntas (AgentLoop + bus/política/registro/CLI)
    ├── architecture/       # guardas AST de fronteras y secretos
    ├── spikes/             # spikes (SPK-02); algunos solo en Linux
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
| A (Núcleo) | `core/loop.py`, `core/limits.py`, `core/subagents/`, `adapters/converters/`, segundo proveedor y conmutación (HU-07-03 a HU-07-05) |
| B (Estado) | `adapters/storage/`, `core/context/`, `core/in_memory_event_bus.py`, `config.py`, `observability/`, `adapters/providers/` (LiteLLM HU-07-02; el FakeProvider de HU-00-03 vive en `tests/doubles/fake_provider.py`) |
| C (Control y conexiones) | `core/permissions/`, `core/tools/`, `adapters/tools/`, `adapters/system/`, `adapters/mcp/`, `cli/` |
| A, B y C juntos | `core/interfaces/`, `core/entities.py`, `core/events.py` (contratos de HU-00-01) |

El responsable de cada historia está en `docs/PROGRESO.md` y manda sobre esta tabla. Cada integrante es dueño de su área; todo cambio lo revisa otra persona.
