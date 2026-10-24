# Data Model: Raíz de composición y punto de entrada ejecutable

La historia no crea tablas, eventos ni puertos. Define un contenedor y el orden de construcción.

## Composition (en `bootstrap.py`)

`@dataclass(frozen=True)`. Se construye una vez por ejecución y no se comparte.

| Campo | Tipo | Descripción |
|---|---|---|
| `loop` | `AgentLoop` | el bucle conectado con proveedor, registro, política y bus |
| `bus` | `EventBus` | el bus al que están suscritos el registrador (y luego la CLI) |
| `store` | `SqliteSessionStore` | el almacén abierto; lo cierra `close()` |
| `session_id` | `str` | identificador de la sesión creada en el almacén (`StoredSession.id`) |
| `notices` | `tuple[str, ...]` | avisos de arranque para el usuario (área ausente o inválida); vacío en el caso normal |

Método `close() -> None`: cierra el almacén; idempotente (el almacén ya lo es).

**Invariantes**: el registrador está suscrito a los 17 tipos de evento antes de que exista la composición; la sesión existe en el almacén; si `notices` contiene el aviso de área, el registro de herramientas se construyó con `area=None`.

## Orden de construcción y qué hace cada paso

| # | Paso | Falla con | Recurso abierto |
|---|---|---|---|
| 1 | proveedor (`provider_factory(config)` o `LiteLLMProvider(...)`) | `ProviderDependencyError`, `ValueError` | ninguno |
| 2 | área (`WorkspaceArea(root)` si hay `workspace_root` y es carpeta; si no, `None` + aviso) | — (se degrada) | ninguno |
| 3 | registro con las 4 herramientas (`ReadFileTool`, `WriteFileTool`, `ListFilesTool`, `SearchTextTool`) | — | ninguno |
| 4 | política (`DefaultPermissionPolicy(registry, area, config.permissions)`) | — | ninguno |
| 5 | bus (`InMemoryEventBus()`) | — | ninguno |
| 6 | almacén (`SqliteSessionStore(config.paths.sessions_db, clock=…, id_factory=…)`) | `SessionStoreError`, `SchemaVersionError` | base abierta |
| 7 | sesión (`store.create_session(model=config.model)`) | `SessionStoreError` | fila `active` |
| 8 | registrador (`attach_event_recorder(bus, store)`) | — | suscripciones |
| 9 | bucle (`AgentLoop(provider, registry, policy, bus)`) | `TypeError` (colaborador inválido) | ninguno |

Si falla el paso 7, 8 o 9, se llama a `store.close()` antes de propagar.

## Sesión de ejecución

Ya definida por HU-03-01: `StoredSession(id, status, created_at, model, goal, parent_id)`. Esta historia la crea con `model=config.model` y sin `goal` (no hay tarea hasta que el usuario escribe; asignar el `goal` desde la primera tarea no cabe en el puerto actual: hallazgo).

## Estado de una ejecución

```text
arranque (load_config → compose) ──fallo──▶ mensaje + código 2
        │ ok
        ▼
   avisos (si hay) → prompt ◀──────────────┐
        │ línea                              │
        ├── /ayuda → ayuda ──────────────────┤
        ├── tarea → run_turn(history) ───────┘   (historial conservado)
        │              └─ excepción ordinaria → código 1
        ├── /salir o fin de entrada → close() → código 0
        └── Ctrl-C → close() → código 130
```
