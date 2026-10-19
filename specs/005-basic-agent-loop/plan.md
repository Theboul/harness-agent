# Implementation Plan: HU-01-01 — Bucle agéntico básico

**Branch**: `005-basic-agent-loop` (nombre de la especificación; la rama git activa no se cambia: `feat/hu-07-01-provider-message-format`) | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Especificación aclarada de `specs/005-basic-agent-loop/spec.md` (sesión de `/speckit-clarify` del 2026-10-18; Q4 aprobada por el Product Owner).

**Estado**: Implementado con dobles, en revisión (2026-10-19; ver `tasks.md`). Historial previo: Plan generado y actualizado con las decisiones R-07 y R-08 (2026-10-18); `tasks.md` generado por `/speckit-tasks`; sin código y sin commits. La historia sigue en `Pendiente` en `docs/PROGRESO.md`. Responsable: A — Núcleo. Sprint 1, 5 PHU.

## Summary

HU-01-01 añade al núcleo el motor del turno agéntico: recibe una tarea, consulta al `Provider`, valida y autoriza cada llamada a herramienta, ejecuta las permitidas **una por una y en orden**, devuelve cada resultado al modelo como `Message(role=TOOL)` y repite hasta que el proveedor deja de pedir herramientas. Los errores de herramienta vuelven al modelo como `ToolResult(is_error=True)`; nada se ejecuta sin validación y decisión `ALLOW` (falla cerrada); todo hecho relevante sale por `EventBus.emit`; el núcleo nunca imprime.

Enfoque técnico: **una sola clase `AgentLoop`** en `src/harness_agent/core/loop.py` (solo biblioteca estándar y contratos de `core/`), con los cuatro colaboradores inyectados (`Provider`, `ToolRegistry`, `PermissionPolicy`, `EventBus`) y un método `async run_turn(session_id, task, history) -> TurnResult`. El historial pertenece al llamador y el bucle solo le añade mensajes. Tres tipos nuevos mínimos (`TurnStatus`, `TurnResult` y dos errores de precondición); ningún contrato compartido cambia. Las pruebas usan dobles guionizados y `asyncio.timeout`; no hay límite interno de iteraciones (decisión del PO, FR-028).

## Technical Context

**Language/Version**: Python 3.12.x (única versión soportada, PD-07; `requires-python = ">=3.12,<3.13"`, `pyproject.toml:10`). Constitución vigente en el repositorio: v1.0.0; la v1.1.0 está sin commitear (no cambia nada relevante aquí).

**Primary Dependencies**: ninguna nueva. Biblioteca estándar (`asyncio`, `dataclasses`, `enum`) y contratos de `harness_agent.core`. Prohibido en el bucle: SDKs de proveedores, `adapters/`, `cli/` (FR-032).

**Storage**: N/A (historial en memoria, a cargo del llamador; sin SQLite ni reanudación: A-08).

**Testing**: `pytest` con `pytest-asyncio` (`asyncio_mode = "auto"`, `pyproject.toml:33`), dobles en `tests/doubles/`, oráculo de validación canónica y convertidores de HU-07-01 solo en pruebas. Sin red ni credenciales. Tiempo máximo con `asyncio.timeout` (no hay `pytest-timeout`; no se añade).

**Target Platform**: Windows y Linux con Python 3.12 (CI `quality (ubuntu-latest, py3.12)` y `quality (windows-latest, py3.12)`; la corrida remota de la matriz vigente sigue pendiente, T008).

**Project Type**: biblioteca/núcleo hexagonal (`src/harness_agent/core/`); sin interfaz propia.

**Performance Goals**: suite de la historia completa en memoria en menos de 5 s (SC-010). Sin objetivos de latencia del bucle: el tiempo propio del harness (V-07) se mide en historias posteriores.

**Constraints**: fail-closed en cada decisión; sin `print()`/`input()`; sin parámetro ni tope de iteraciones (FR-028); ejecución secuencial; no tocar `core/__init__.py` ni las interfaces compartidas; asincronía según las firmas actuales con D-01 **pendiente de aprobación**.

**Scale/Scope**: un módulo de núcleo (estimado 250–350 líneas), un paquete de pruebas (`tests/core/`, 7 archivos), 5 dobles de prueba nuevos y 2 pruebas de contrato/arquitectura. 13,5 h de tareas (Sp1-12, Sp1-13, Sp1-14).

## Constitution Check

*GATE: debe pasar antes de la investigación y se vuelve a evaluar tras el diseño.*

| Principio / restricción | Evaluación previa (antes de Phase 0) | Evaluación posterior (tras Phase 1) |
|---|---|---|
| I. Una historia por especificación | Cumple: solo HU-01-01. El solapamiento con HU-01-07 (varias llamadas por turno) está declarado y acotado al mínimo secuencial. | Cumple. El diseño no añade nada de HU-01-06/07/08. |
| II. Microtareas de 15–40 min (máx. 60) | Se decide en `/speckit-tasks`. | Cumple por diseño: la tabla de «costuras» (abajo) parte las 13,5 h en bloques de 15–55 min. |
| III. Modular, hexagonal, tipado, Python 3.12.x | Cumple: el bucle vive en `core/`; solo stdlib; `mypy --strict`. | Cumple: sin imports de `adapters/`, `cli/` ni SDKs; tres tipos nuevos con anotaciones completas; guardas AST. |
| IV. Pruebas sin red, calidad y CI en Windows y Linux | Cumple: dobles guionizados. | Cumple en diseño. **Pendiente de evidencia**: CI remota de la matriz 3.12 (T008) aún no ejecutada. |
| V. ACs inmutables | Cumple: AC-01 y AC-02 literales en la spec. | Cumple: el plan no los reformula; E-01 y E-02 los verifican. |
| VI. Disciplina de sprints | Cumple: nada de Sprint 2 o 3 (sin límites, sin detección de repetidas, sin paralelismo). | Cumple: Q1 (sin tope) evita adelantar HU-01-06. |
| VII. Consulta documental quirúrgica | Cumple: se leyeron constitución, spec, contratos de `core/`, docs 02/03/04a, PROGRESO, D-01, D-02 y reglas de HU-07-01. | Cumple. |
| VIII. Registro en `PROGRESO.md` | Cumple: fila de la sesión de plan añadida. | Obligación futura: registrar cada tarea implementada con comando y resultado. |
| IX. Definition of Done | No exigible aún (no hay código). | Estado: pendiente de implementación; además, revisión por otra área, CI remota y demo del sprint. |
| X. `docs/archivo/` inmutable | No se toca. | No se toca. |
| V-01 (núcleo no imprime, sin bloquear terminal) | Cumple. | Cumple: prueba AST + captura de consola; `Approver` no se cablea. |
| V-02 / Falla cerrada | Cumple: solo `ALLOW` ejecuta. | Cumple: política que falla, valor inesperado y `ASK` = no ejecuta. |
| V-11 (cancelación limpia con resultado al modelo) | Se difiere a HU-06-03. | Cumple el mínimo del Sprint 1 (`INTERRUPTED` y propagación); sin fabricar resultados. |
| Manejo de errores y aislamiento (error de proveedor no quiebra la sesión) | Cumple. | Cumple: `PROVIDER_FAILED` es un resultado, no una excepción. |

**Resultado del gate**: aprobado, sin violaciones que justificar (la sección «Complexity Tracking» no aplica). Observaciones de gobernanza no bloqueantes:

1. La constitución (Área A) llama al bucle «`core/agent`»; el árbol acordado (`.agents/skills/estructura-carpetas-harness/references/arbol.md`) fija `core/loop.py`. **Correspondencia**: el subsistema «`core/agent`» de la constitución se materializa en `src/harness_agent/core/loop.py` (`AgentLoop`); no se crea un paquete `core/agent/` ni se enmienda la constitución. `tests/core/` se crea nuevo (la carpeta no existe aún) y refleja `src/harness_agent/core/`.
2. D-01 (asyncio) y las aprobaciones de HU-00-01 (T016), HU-07-01 (D-02/T018) siguen pendientes; esta historia se apoya en el código vigente y no las da por cerradas.

## Project Structure

### Documentation (this feature)

```text
specs/005-basic-agent-loop/
├── spec.md                       # Especificación aclarada (Q4 aprobada)
├── plan.md                       # Este archivo
├── research.md                   # Phase 0: decisiones, alternativas, divergencias con contratos
├── data-model.md                 # Phase 1: entidades reutilizadas, tipos nuevos, invariantes
├── quickstart.md                 # Phase 1: guía de validación
├── contracts/
│   └── agent-loop-contract.md    # Phase 1: API, orden, errores, historial y eventos
├── checklists/
│   └── requirements.md
└── tasks.md                      # NO se crea aquí (lo genera /speckit-tasks)
```

### Source Code (repository root)

```text
src/harness_agent/core/
└── loop.py                       # NUEVO: AgentLoop, TurnResult, TurnStatus,
                                  #        MissingDependencyError, InvalidHistoryError
                                  # (core/__init__.py y core/interfaces/ NO se modifican)

tests/
├── core/                         # NUEVO (refleja src/harness_agent/core/); incluye __init__.py
│   ├── test_loop_construction.py     # FR-025, SC-008
│   ├── test_loop_happy_path.py       # AC-01, SC-001, FR-002, FR-004, determinismo
│   ├── test_loop_tool_errors.py      # AC-02, FR-016–FR-019, SC-003
│   ├── test_loop_permissions.py      # FR-008–FR-015, SC-002
│   ├── test_loop_events.py           # FR-029–FR-031, SC-006, Q4 (E-06)
│   ├── test_loop_history.py          # FR-001, FR-020–FR-022, varios turnos, _check_history
│   └── test_loop_failures.py         # FR-023–FR-026, SC-009 (proveedor, respuesta inválida, cancelación)
├── contracts/
│   └── test_loop_canonical_oracle.py # SC-005: oráculo de HU-07-01 + acuerdo con _check_history
├── architecture/
│   └── test_loop_boundaries.py       # FR-030, FR-032, SC-004, SC-007: AST (sin print/input/stdout; imports)
└── doubles/                      # NUEVOS dobles (se reexportan en tests/doubles/__init__.py)
    ├── scripted_provider.py          # guion finito; agotamiento ⇒ ScriptExhausted + exhausted=True
    ├── in_memory_registry.py         # ToolRegistry mínimo de pruebas (NO es HU-01-02)
    ├── scripted_policy.py            # PermissionPolicy de pruebas; lo no mapeado ⇒ DENY
    ├── failing_bus.py                # RecordingEventBus que lanza en tipos configurados
    ├── scripted_tools.py             # RecordingTool, FailingTool, RaisingTool, BlockingTool
    └── bounded.py                    # run_bounded(): asyncio.timeout + comprobación de exhausted
```

**Structure Decision**: el bucle va en `core/loop.py` por el árbol acordado (el dueño es A) y por Principio III. Los dobles viven junto a los existentes (`DummyProvider`, `DummyTool`, `RecordingEventBus`, `DummyApprover` en `tests/doubles/`); no se implementan `FakeProvider` (B, `adapters/providers/fake_provider.py`) ni `ToolRegistry`/`PermissionPolicy` reales (C). Los nombres de los dobles dejan claro que son de prueba. La estructura de pruebas sigue la skill de carpetas (`tests/` refleja `src/`); `tests/core/` es nueva.

## Arquitectura propuesta

```text
                       llamador (CLI / pruebas)
                               │  run_turn(session_id, task, history)
                               ▼
        ┌─────────────────────────────────────────────┐
        │  core/loop.py  ·  AgentLoop                 │   solo stdlib + core/*
        │   _check_history · _tool_definitions        │
        │   pipeline por llamada · eventos · errores  │
        └──────┬──────────┬───────────┬───────────┬───┘
               │          │           │           │
        Provider      ToolRegistry  PermissionPolicy  EventBus     ← puertos existentes
        (async)       get/list/     evaluate (sync)   emit (sync)     (core/interfaces/)
                      validate_args
               ▲          ▲           ▲           ▲
         adapters (B)   C (HU-01-02) C (HU-05-01)  B (HU-01-05)     ← fuera de esta historia
         pruebas: ScriptedProvider · InMemoryToolRegistry · ScriptedPolicy · RecordingEventBus
```

### Flujo del bucle (los 15 pasos de la solicitud)

1. **Recibir la tarea**: `task` + `session_id`.
2. **Construir o recibir el historial canónico**: `history` del llamador; `_check_history` (R-04); se añade `USER(task)` y se publica `USER_MESSAGE`.
3. **Invocar** `provider.complete(copy.deepcopy(history), tools)` con `tools = [ToolDefinition(t.name, t.description, t.schema) for t in registry.list()]` recalculadas en cada consulta y construidas **antes** del `try` del proveedor (T033: su fallo es estructural, se propaga y no es `PROVIDER_ERROR`). Copia profunda del historial (T034) y de las `ToolCall` de la respuesta antes de registrarlas.
4. **Interpretar** `ProviderResponse`: tipo correcto e ids de llamada no vacíos y únicos entre sí y respecto del historial (regla canónica de HU-07-01, D-02 §4.7; si no: `INVALID_PROVIDER_RESPONSE`).
5. **Registrar la respuesta del asistente**: `Message(ASSISTANT, content, tuple(tool_calls), usage)`; `ASSISTANT_MESSAGE` si hay texto.
6. **Identificar todas las `ToolCall`** de la respuesta; sin ninguna ⇒ ir al paso 15.
7. **Consultar `ToolRegistry`** (`get`) por llamada, en orden.
8. **Validar argumentos** (`validate_args`; falla cerrada) y obtener los **argumentos efectivos** (copia profunda del `dict` devuelto; R-07).
9. **Evaluar `PermissionPolicy`** sobre una `ToolCall` de evaluación con el mismo `id` y `name` y los argumentos efectivos (otra copia profunda); publicar `PERMISSION_DECIDED`.
10. **Ejecutar** solo con `ALLOW`, secuencialmente, con exactamente los argumentos autorizados (copia propia, no compartida con la política).
11. **Convertir** el resultado o el rechazo en `ToolResult` (siempre con `call_id = call.id`).
12. **Incorporar** el `Message(TOOL)` al historial en cuanto termina cada llamada; publicar `TOOL_FINISHED`.
13. **Emitir eventos** según la tabla del contrato (§5); ningún `print`.
14. **Repetir** (volver al paso 3) mientras la respuesta traiga herramientas.
15. **Finalizar** con `TurnResult(COMPLETED)` cuando una respuesta no trae `tool_calls`.

Detalle del orden, de los fallos y de las cargas de eventos: [contracts/agent-loop-contract.md](contracts/agent-loop-contract.md).

### Interfaces reutilizadas (sin cambios)

`Provider.complete` (`core/interfaces/provider.py:54`), `ProviderResponse` (`:32`), `ToolDefinition` (`:17`), `Tool` (`core/interfaces/tool.py:29`, `run` en `:60`), `ToolRegistry.get/list/validate_args` (`tool.py:81,86,91`), `PermissionPolicy.evaluate` (`core/interfaces/security.py:64`, síncrona), `PermissionDecision` (`:17`), `EventBus.emit` (`core/interfaces/event_bus.py:21`, síncrona), `Event.create` (`core/events.py:86`), `EventType` (`:18`), `Message` (`core/entities.py:79`), `ToolCall` (`:31`), `ToolResult` (`:46`), `TokenUsage` (`:61`). `Approver`, `ContextManager`, `SessionStore` no se usan.

### Componentes que se crearán

| Componente | Ubicación | Responsabilidad |
|---|---|---|
| `AgentLoop` | `core/loop.py` | Orquestar un turno; única clase con lógica |
| `TurnResult`, `TurnStatus` | `core/loop.py` | Resultado explícito de un turno (FR-006) |
| `MissingDependencyError`, `InvalidHistoryError` | `core/loop.py` | Precondiciones violadas (FR-025, R-04) |
| `_check_history`, `_tool_definitions`, constructores de resultado y de carga de eventos | `core/loop.py` (privados) | Auxiliares sin API pública |
| Dobles de prueba (6 archivos) | `tests/doubles/` | Sustituir historias de B y C sin implementarlas |
| Pruebas (9 archivos) | `tests/core/`, `tests/contracts/`, `tests/architecture/` | Verificación de la historia |

## Decisiones arquitectónicas justificadas (ADR resumido)

Detalle, justificación y alternativas en [research.md](research.md).

| ID | Decisión | Resumen de la justificación |
|---|---|---|
| D-PLAN-01 | Una clase `AgentLoop` en `core/loop.py`; método `run_turn` | API mínima; el árbol acordado ubica el bucle ahí; evita máquina de estados prematura |
| D-PLAN-02 | Colaboradores en el constructor; `session_id` por llamada; `None` ⇒ `MissingDependencyError` | Falla cerrada antes de cualquier efecto (FR-025); `Event` exige `session_id` |
| D-PLAN-03 | Historial propiedad del llamador; el bucle añade en el sitio; copia al proveedor; instantánea en el resultado | Único modo de conservar el historial parcial ante cancelación o fallo de `emit` (FR-026) sin envolver `CancelledError` |
| D-PLAN-04 | Fallos del proveedor = `TurnResult`; precondiciones, fallos del bus y cancelación = excepciones | El error de proveedor no quiebra la sesión; no se oculta ni el bus (Q4) ni la cancelación (D-01 §6) |
| D-PLAN-05 | `_check_history` mínimo en el núcleo + prueba de acuerdo con el validador de HU-07-01 | No se puede importar `adapters/`; no se toca HU-07-01; falla rápido y detecta llamadas pendientes de un turno cancelado |
| D-PLAN-06 | Orden de la tubería: `TOOL_REQUESTED` → get → validar → evaluar → `PERMISSION_DECIDED` → ejecutar → añadir `TOOL` → `TOOL_FINISHED` | Auditoría antes del efecto; observación conservada aunque falle el último `emit` |
| D-PLAN-07 | **R-07 adoptada**: `validate_args` → copia profunda de los argumentos efectivos → la política evalúa `ToolCall(id, name, efectivos)` → `Tool.run` recibe exactamente los argumentos autorizados; originales solo para diagnóstico e historial `ASSISTANT` | Lo autorizado es lo ejecutado; sin diccionarios compartidos; sin cambiar firmas. Reemplaza la redacción previa de FR-008 (política sobre la llamada cruda). Semántica de `validate_args` por confirmar con C |
| D-PLAN-08 | `call_id` forzado a `call.id`; `content` del `TOOL` = `tool_result.content`; categorías e `is_external` definidos; retorno inválido ⇒ error | Correlación (D-02 §4.7) y D9; evita que un contenido no textual rompa el convertidor |
| D-PLAN-09 | Q4 (aprobada) y **R-08 (adoptada)**: `emit` no se captura; efectos por punto de publicación; si `emit(INTERRUPTED)` falla durante una cancelación, prevalece la `CancelledError` original con el diagnóstico adjunto (nota adjunta con `add_note`; el encadenamiento implícito no está garantizado y no se exige) | Falla cerrada sin perder observaciones ni la semántica de cancelación (D-01 §6) |
| D-PLAN-10 | `INTERRUPTED` una vez y re-lanzar `CancelledError`; sin `shield` ni limpieza propia | D-01 §6 (pendiente de aprobación); limpieza de procesos es de HU-01-04 |
| D-PLAN-11 | Cargas de eventos mínimas; sin argumentos de herramientas | Evitar información sensible hasta que exista la redacción (V-13) |
| D-PLAN-12 | Dobles propios + `asyncio.timeout`; sin dependencias nuevas | Principio IV y restricciones del PO; no hay `pytest-timeout` |
| D-PLAN-13 | No exportar desde `core/__init__.py` | Superficie de HU-00-01 aún sin aprobar (T016) |

## Tratamiento de errores (resumen)

Matriz completa en el contrato §3. Regla general: **todo rechazo previo a la ejecución y todo fallo de herramienta se convierte en `ToolResult(is_error=True)` con el `id` de la llamada y el bucle continúa; nada se ejecuta salvo `ALLOW` explícito tras validar.** `Exception` de herramienta o de proveedor se captura; `CancelledError` nunca; los errores de `EventBus.emit` nunca se capturan.

## Continuidad de sesiones

Una sesión es una secuencia de turnos; `run_turn` ejecuta **un** turno (hasta que el proveedor deja de pedir herramientas) y devuelve el control. El consumidor conserva la lista `history` en memoria y la entrega en el turno siguiente; el bucle no persiste ni reanuda por identificador, y no usa `ContextManager`. Tras `COMPLETED`, `PROVIDER_FAILED` o `INVALID_PROVIDER_RESPONSE` el historial es reutilizable; tras una cancelación o un fallo de `emit` a mitad de llamadas se rechaza con `InvalidHistoryError`. Prefijo `SYSTEM`: solo contiguo al inicio (HU-07-01); el bucle no asume que el historial contenga solo mensajes `SYSTEM`.

## Estrategia de eventos

Siete tipos (`USER_MESSAGE`, `ASSISTANT_MESSAGE`, `TOOL_REQUESTED`, `PERMISSION_DECIDED`, `TOOL_FINISHED`, `PROVIDER_ERROR`, `INTERRUPTED`), con cargas mínimas, publicados con `Event.create`. Ni `LIMIT_REACHED` ni `APPROVAL_*`. Si `emit` falla se propaga y el turno se detiene; el punto de publicación está elegido para que cada fallo deje un estado seguro (research R-08). Orden y cargas: contrato §5.

## Estrategia de pruebas

Todas deterministas, en memoria, sin red; cada prueba usa `run_bounded` (`asyncio.timeout`) y comprueba que el guion no se agotó.

| Requisito | Archivo de prueba | Qué comprueba |
|---|---|---|
| AC-01, FR-003/004/015, SC-001 | `tests/core/test_loop_happy_path.py` | Tres herramientas en orden; 4 consultas; respuesta final; 20 repeticiones idénticas; texto+llamadas no es final; copia al proveedor |
| AC-02, FR-016–019, SC-003 | `tests/core/test_loop_tool_errors.py` | `is_error=True` devuelto con el `id`; excepción de herramienta; retorno inválido; `call_id` ajeno forzado; herramienta desconocida; varias llamadas con una fallida |
| FR-008–015, SC-002 | `tests/core/test_loop_permissions.py` | Argumentos inválidos; `DENY`; `ASK`; política que falla o devuelve un valor inesperado; sin política ⇒ no hay ejecución; contador de ejecuciones; **R-07**: la política ve los argumentos efectivos, la herramienta recibe exactamente los autorizados, mutaciones posteriores no alteran la ejecución, `id`/`name` conservados |
| FR-029–031, SC-004, SC-006 | `tests/core/test_loop_events.py` | Secuencia exacta de eventos; sin suscriptores; `emit` que falla en cada tipo (antes y después de la operación); sin `APPROVAL_*` ni `LIMIT_REACHED` |
| FR-001, FR-020–022, SC-005 | `tests/core/test_loop_history.py` + `tests/contracts/test_loop_canonical_oracle.py` | Solo añadido; `TOOL.content == tool_result.content`; `is_external`; varios turnos; `InvalidHistoryError` (SYSTEM intercalado, llamadas pendientes, ids repetidos); acuerdo con el validador de HU-07-01; conversión con ambos convertidores |
| FR-023–026, SC-009 | `tests/core/test_loop_failures.py` | Fallo del proveedor; respuesta inválida; cancelación en proveedor y en herramienta; un solo `INTERRUPTED`; historial parcial; `CancelledError` no absorbido; **R-08**: `INTERRUPTED` fallido durante una cancelación ⇒ prevalece la `CancelledError` original con diagnóstico, frente a un fallo ordinario de `emit` que se propaga como error del bus |
| FR-025, SC-008 | `tests/core/test_loop_construction.py` | Cuatro colaboradores ausentes ⇒ error que nombra al ausente; 0 consultas |
| FR-030, FR-032, FR-033, SC-007 | `tests/architecture/test_loop_boundaries.py` | AST: sin `print`/`input`/`sys.stdout`/`sys.stderr`; sin importaciones de `adapters`, `cli`, SDKs; solo stdlib y `harness_agent.core`; la prueba de fronteras existente sigue pasando |
| Compatibilidad con `Provider` | `test_loop_happy_path.py` | Un doble que cumple `Provider` real (incluido `DummyProvider`) funciona sin adaptaciones |

Calidad: `mypy --strict` sobre `src` y `tests`, `ruff check` y `ruff format --check` (SC-010). El modo TDD efectivo y su ejecutor se resuelven en `/speckit-tasks`; este plan no presupone ni descarta pruebas primero.

## Dependencias entre integrantes y puntos de integración

| Historia | Dueño | Contrato que usa el bucle | Qué debe verificarse conjuntamente | Doble mientras tanto |
|---|---|---|---|---|
| HU-00-03 `FakeProvider` | B | `Provider.complete` | El guion de B acepta respuestas con varias `tool_calls`; ids estables; falla de forma explícita al agotarse; no modifica la lista recibida | `ScriptedProvider` |
| HU-01-05 `EventBus` | B | `EventBus.emit` (sync) | Aislar fallos de suscriptores dentro del bus; `emit` solo lanza por fallos propios; no se suprimen las excepciones del bus; verificar `APPROVAL_*` con un doble propio (el bucle no los emite) | `RecordingEventBus`, `FailingEventBus` |
| HU-01-02 `ToolRegistry` | C | `get`, `list`, `validate_args` | `validate_args` devuelve un `dict` nuevo con los argumentos efectivos sin mutar la entrada; qué excepciones lanza además de `ValueError`; `list()` y `Tool.schema` usables como `ToolDefinition.parameters` | `InMemoryToolRegistry` |
| HU-05-01 `PermissionPolicy` (incl. Sp1-35) | C | `evaluate` (sync) | La política provisional de `ASK` es de C; el bucle solo es la última barrera; la política recibe una `ToolCall` con los **argumentos efectivos validados** (R-07): C confirma que razona sobre ellos (p. ej. rutas contra `AuthorizedArea`) | `ScriptedPolicy` |

**Riesgo de la demostración «leer → escribir → releer»** (`docs/03`, spec A-12): si la política provisional de C resuelve lo no previsto (incluidas las lecturas) como `ASK` y, por tanto, como denegación, la lectura de la demo fallaría. **El bucle no amplía permisos para evitarlo**; se coordina con C que la regla de lectura (riesgo `LOW`) quede explícita en HU-05-01. No es un cambio en esta historia.

## Alineación de esfuerzo y descomposición

Sp1-12 = 7 h, Sp1-13 = 2,5 h, Sp1-14 = 4 h (`docs/03-plan-sprints.md:253-255`): 13,5 h = 810 min, sin discrepancia con la spec. Las «costuras» siguientes son límites de módulo para que `/speckit-tasks` genere microtareas (15–55 min) sin reabrir el diseño; **no son tareas** y no sustituyen a `tasks.md`.

| Bloque (Sp1-xx) | Costura | Min |
|---|---|---|
| Sp1-12 (420) | A1 Tipos, constructor y `MissingDependencyError` | 40 |
| | A2 `_check_history` e `InvalidHistoryError` | 45 |
| | A3 `ToolDefinition`, consulta al proveedor y validación de la respuesta | 50 |
| | A4 Mensaje del asistente y camino de respuesta final | 35 |
| | A5 Tubería por llamada: `get` y `validate_args` | 50 |
| | A6 Tubería: política (`DENY`, `ASK`, fallos) | 50 |
| | A7 Ejecución, normalización del resultado y mensaje `TOOL` | 55 |
| | A8 Fallo del proveedor y respuesta inválida ⇒ `TurnResult` | 45 |
| | A9 Cancelación (`INTERRUPTED`, re-lanzar) | 50 |
| Sp1-13 (150) | B1 Constructores de carga y publicación de eventos | 40 |
| | B2 Puntos de publicación y orden | 35 |
| | B3 Semántica de fallo de `emit` (Q4) | 45 |
| | B4 `PROVIDER_ERROR` e `INTERRUPTED` integrados con B1–B3 | 30 |
| Sp1-14 (240) | C1 Dobles de prueba y `run_bounded` | 45 |
| | C2 Pruebas AC-01 / SC-001 | 30 |
| | C3 Pruebas AC-02 y errores de herramienta | 30 |
| | C4 Pruebas de permisos | 30 |
| | C5 Pruebas de eventos y Q4 | 30 |
| | C6 Pruebas de historial, varios turnos y oráculo | 30 |
| | C7 Pruebas de fallos del proveedor y cancelación | 30 |
| | C8 Guardas de arquitectura (AST) | 15 |

El orden de ejecución, las dependencias entre costuras y si las pruebas se escriben antes que el código se deciden en `/speckit-tasks`.

## Riesgos pendientes

| # | Riesgo | Impacto | Mitigación / dueño |
|---|---|---|---|
| R-01 | D-01 (asyncio) sin aprobar de A, B y C | Revisar las firmas `async` y la semántica de cancelación | Esta historia consume las firmas vigentes; revisar si D-01 cambia (A, B, C) |
| R-02 | HU-00-01 (T016) y HU-07-01 (D-02/T018) sin aprobación individual | Contratos y reglas canónicas podrían cambiar | Usarlos tal como están; revisar tras la reunión conjunta |
| R-03 | Q4 aprobada por el PO, pero el bus de B aún no aísla suscriptores | Un suscriptor defectuoso podría detener el turno si el bus no lo aísla | Coordinar con B que HU-01-05 aísle fallos de suscriptores; hasta entonces, los dobles son el único oráculo |
| R-04 | Sin tope de iteraciones (FR-028) | Un modelo real que no termina gasta cuota sin límite | Ejecución desatendida con proveedores reales **no segura** hasta HU-01-06 o controles externos; la demo usa proveedor simulado o ejecución supervisada |
| R-05 | Lectura de la demo clasificada como `ASK` por la política provisional de C | La demo «leer, escribir y releer» fallaría | Coordinar con C (HU-05-01); el núcleo no amplía permisos |
| R-06 | Duplicación mínima de reglas canónicas en `_check_history` | Divergencia futura frente al validador de HU-07-01 | Prueba de acuerdo en `tests/contracts/`; propuesta futura de mover el validador a `core/` (no en esta historia) |
| R-07 | Decisión adoptada: la política evalúa los argumentos efectivos y la herramienta ejecuta exactamente los autorizados. Riesgo residual: la semántica de `validate_args` (¿`dict` nuevo?, ¿excepciones?) y que la política de C asuma argumentos crudos | Si `validate_args` normaliza distinto de lo que C espera, la política podría decidir sobre datos inesperados (la copia profunda del bucle neutraliza que devuelva el mismo objeto o lo mute) | Confirmar con C (HU-01-02, HU-05-01); ratificación formal del PO pendiente si quien comunicó la decisión no actúa como PO |
| R-08 | Decisión adoptada: la cancelación prevalece sobre un fallo de `emit(INTERRUPTED)` | Tensión entre dos reglas (no ignorar `emit`; no absorber la cancelación) | El diagnóstico del bus queda en una nota (`add_note`) de la `CancelledError` original; no se exige `__context__`; ratificación formal del PO pendiente si quien comunicó la decisión no actúa como PO |
| R-09 | Cargas de eventos sin argumentos ni redacción | La CLI podría necesitar más datos | Cambio aditivo posterior; la redacción de secretos (V-13) es de observabilidad |
| R-10 | Historial parcial tras cancelación no reenviable (V-11 pendiente) | El consumidor debe descartarlo o esperar HU-06-03 | Documentado; `InvalidHistoryError` explícito |
| R-11 | CI remota de la matriz 3.12 (T008) sin ejecutar | DoD incompleta | Fuera de esta historia; registrar la evidencia al abrir la PR |
| R-12 | `emit` síncrono con suscriptores lentos bloquea el bucle | Latencia | Contrato de HU-01-05 (B); el bucle no lo evita |

## Fuera de alcance (sin cambios respecto de la spec)

HU-01-06 (límites de turnos, tiempo, tokens y costo), HU-01-07 (alcance propio de varias herramientas), HU-01-08 (llamadas repetidas), persistencia SQLite, compactación del contexto, reintentos y fallback, shell, MCP, subagentes, CLI de producción, interfaz de aprobación (HU-05-03), captura de Ctrl+C (HU-06-03), recorte de salidas (HU-02-02), streaming. Implementar HU-00-03, HU-01-02, HU-01-05 o HU-05-01 tampoco forma parte de esta historia.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
