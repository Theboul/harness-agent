# Árbol acordado

```
harness-agent/
├── pyproject.toml          # dependencias y herramientas (pytest, mypy, ruff, import-linter)
├── README.md
├── CLAUDE.md               # resumen corto que apunta a docs/00-indice.md
├── .env.example            # plantilla sin secretos
├── config.example.toml     # modelo, límites, rutas, reglas de permisos
├── docs/
│   ├── 00-indice.md                # mapa de la documentación y dónde está cada ID
│   ├── 01-vision-y-decisiones.md   # equipo, alcance, decisiones V-01 a V-17
│   ├── 02-arquitectura.md          # diagramas, contratos, eventos, modelo de datos
│   ├── 03-plan-sprints.md          # pruebas, riesgos, épicas, sprints, tareas
│   ├── 04a..04e-historias-*.md     # historias de usuario por épicas
│   ├── 05-trazabilidad.md          # requisito -> historia y arranque
│   ├── 06-historial-planificacion.md  # auditoría, decisiones PD, capacidad (v2.5)
│   ├── PROGRESO.md                 # qué se hizo y dónde está
│   └── demo.md                     # guion de demostración (10 a 15 min)
├── src/harness_agent/
│   ├── core/               # NÚCLEO: sin imports externos
│   │   ├── loop.py         # bucle del agente (máquina de estados)
│   │   ├── messages.py     # formato interno: roles, bloques, uso
│   │   ├── events.py       # tipos de evento y EventBus
│   │   ├── limits.py       # turnos, tiempo y consumo
│   │   ├── errors.py       # errores de dominio
│   │   ├── ports.py        # Provider, SessionStore, MemoryStore, McpClient, Approver, TaskCriteria, AreaAutorizada
│   │   ├── context/        # ContextManager, estimación, compactación, recorte
│   │   ├── permissions/    # política, lista base de denegados
│   │   ├── tools/          # Tool, ToolRegistry, validación de esquema
│   │   └── subagents/      # SubagentRunner, perfiles, resultado estructurado
│   ├── adapters/           # implementaciones de los puertos
│   │   ├── providers/      # litellm_provider.py, fake_provider.py
│   │   ├── storage/        # sqlite_store.py, esquema y migraciones
│   │   ├── mcp/            # cliente MCP y traducción a Tool
│   │   └── tools/          # herramientas nativas: archivos, shell, preguntar, memoria, delegar
│   ├── observability/      # trazas, auditoría, redacción de secretos (suscriptores del bus)
│   ├── config.py           # carga de archivo y variables de entorno
│   ├── bootstrap.py        # RAÍZ DE COMPOSICIÓN: único lugar que une núcleo y adaptadores
│   └── cli/                # terminal: se suscribe al bus
│       ├── app.py          # entrada y comandos (/sesiones, /reanudar…)
│       ├── render.py       # impresión de eventos
│       └── approver.py     # pregunta de aprobación en terminal
└── tests/
    ├── unit/               # sin red, con FakeProvider
    ├── integration/        # bucle completo, aprobación, reanudación
    ├── failures/           # cierre forzado, proveedor caído, MCP caído
    ├── contract/           # cada Provider real cumple la interfaz
    └── architecture/       # test de fronteras
```

# Reparto de áreas

| Área | Dueño de |
|---|---|
| A (Núcleo) | `core/loop.py`, `core/events.py`, `core/subagents/`, `adapters/providers/` |
| B (Estado) | `adapters/storage/`, `core/context/`, `observability/`, `core/messages.py` |
| C (Control y conexiones) | `core/permissions/`, `adapters/tools/`, `adapters/mcp/`, `cli/` |

Cada integrante es dueño de su área; todo cambio lo revisa otra persona. Los puertos de `core/ports.py` son el único punto que los tres deben acordar.
