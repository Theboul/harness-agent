# Implementation Tasks: HU-01-01 — Bucle agéntico básico

**Feature**: `specs/005-basic-agent-loop/spec.md`
**Plan**: `specs/005-basic-agent-loop/plan.md` (contrato: `contracts/agent-loop-contract.md`; datos: `data-model.md`; decisiones: `research.md`; guía: `quickstart.md`)
**Responsable**: A — Núcleo | **Sprint**: 1 | **PHU**: 5 | **Prioridad**: Alta | **Python**: 3.12.x
**Generado**: 2026-10-18 por `/speckit-tasks` | **Estado**: tareas pendientes; no hay código. HU-01-01 sigue en `Pendiente` en `docs/PROGRESO.md` y **no se declara completada** por este documento.

**Decisiones incorporadas**: Q1–Q4 (aclaraciones; Q4 aprobada por el PO), **R-07** (la política evalúa los argumentos efectivos validados y la herramienta ejecuta exactamente los autorizados) y **R-08** (la cancelación prevalece sobre un fallo al publicar `INTERRUPTED`). R-07 y R-08 son decisiones adoptadas, comunicadas en la solicitud de `/speckit-tasks` del 2026-10-18; su ratificación formal por el PO queda pendiente si quien las comunicó no actúa como PO.

---

## Convenciones de este archivo

- **Línea de tarea** (analizable): `- [ ] T### [P] [US#] descripción con ruta`. `[P]` = paralelizable (archivos distintos y sin dependencia incompleta). `[US#]` solo en fases de historia de usuario.
- **Subcampos** bajo cada tarea: objetivo, archivos, estimación, dependencias, historia y actividad Sp1, criterios relacionados, evidencia requerida y **condición exacta de completado**.
- **Estimaciones**: cada tarea entre 15 y 40 minutos (la constitución fija 15–40 como objetivo y 60 como máximo). El presupuesto de A es exactamente **810 min = 13,5 h** (tabla de reparto abajo). Las dos tareas de integración con implementaciones reales de B y C (T031, T032) están **bloqueadas y fuera de ese presupuesto**.
- **Modo TDD**: no hay un modo TDD declarado en la configuración del proyecto ni en la constitución (que solo exige contratos primero con dobles). Esta lista aplica **pruebas primero por tarea** como práctica de la historia (cada fase de historia empieza con las pruebas en ROJO y luego la implementación en VERDE); el ROJO observado se registra en `docs/PROGRESO.md`, sin inventar evidencia. No es un requisito de la Definition of Done.
- **Ejecutor de pruebas**: `.venv/Scripts/python.exe -m pytest` (Windows) o `.venv/bin/python -m pytest` (Linux); `asyncio_mode = "auto"` ya está en `pyproject.toml`. **No se añade `pytest-timeout` ni otra dependencia**: los límites de tiempo usan `asyncio.timeout` mediante `run_bounded`.
- **Calidad por tarea**: tras cada tarea con código, `mypy` estricto y `ruff` sobre lo tocado; la puerta completa corre en T029.
- **Reglas transversales** (aplican a todas las tareas): no modificar contratos compartidos (`core/interfaces/*`, `core/entities.py`, `core/events.py`, `core/__init__.py`); no importar SDKs comerciales, `adapters/` ni `cli/` en `core/`; no `print`/`input`/`sys.stdout`/`sys.stderr` en `core/`; sin límites de HU-01-06, sin paralelismo, sin reintentos, sin SQLite ni compactación; no emitir `LIMIT_REACHED` ni `APPROVAL_*`; **no modificar AC-01 ni AC-02**; código, comentarios y mensajes de código en inglés; documentos del repositorio en español neutro.
- **Ubicación**: `src/harness_agent/core/loop.py` (`AgentLoop`) materializa el subsistema «`core/agent`» de la constitución (nota de correspondencia en `plan.md`; constitución sin modificar). `tests/core/` se crea nuevo (la carpeta no existe).

### Reparto del presupuesto (13,5 h = 810 min)

| Actividad | Descripción (`docs/03-plan-sprints.md:253-255`) | Presupuesto | Tareas | Min asignados |
|---|---|---|---|---|
| Sp1-12 | Implementar un turno: llamar al proveedor, procesar la respuesta, ejecutar herramientas, devolver resultados (7 h) | 420 | T001, T005, T008, T009, T010, T011, T012, T014, T016, T021, T022, T024, T025, T026 (14) | 420 |
| Sp1-13 | Condición de parada y emisión de eventos (2,5 h) | 150 | T006, T018, T019, T027, T029, T030 (6) | 150 |
| Sp1-14 | Pruebas con el proveedor simulado (4 h) | 240 | T002, T003, T004, T007, T013, T015, T017, T020, T023, T028 (10) | 240 |
| **Total A** | | **810** | **30 tareas** | **810** |
| Integración con B y C (bloqueadas, fuera del presupuesto) | T031, T032 | — | 2 | 60 (adicionales) |

Verificado con `docs/03-plan-sprints.md:253-255`: Sp1-12 = 7 h, Sp1-13 = 2,5 h, Sp1-14 = 4 h; sin discrepancia con el plan ni con la solicitud. La condición de parada (respuesta final sin `tool_calls`) se implementa en T009 (Sp1-12) y se verifica/cierra su publicación de eventos en T018 (Sp1-13).

### Reparto por fase / historia de usuario

| Fase | Historia | Tareas | Min |
|---|---|---|---|
| 1. Setup | — | T001 | 25 |
| 2. Fundacional | — | T002–T006 | 130 |
| 3. US1 (P1) — AC-01 | Un guion de tres pasos se ejecuta en orden hasta terminar | T007–T012 | 190 |
| 4. US2 (P1) — AC-02 | Un error de herramienta vuelve al modelo y el bucle continúa | T013–T014 | 55 |
| 5. US3 (P1) | Nada se ejecuta sin validación ni decisión de permisos (R-07) | T015–T016 | 60 |
| 6. US4 (P2) | Cada hecho relevante es un evento; el núcleo nunca imprime (Q4) | T017–T019 | 90 |
| 7. US5 (P2) | Historial coherente y dependencias ausentes fallan cerrado | T020–T022 | 80 |
| 8. US6 (P2) | Fallo del proveedor o cancelación terminan de forma explícita (R-08) | T023–T027 | 130 |
| 9. Pulido y cierre | — | T028–T030 | 50 |
| 10. Integración bloqueada (fuera del presupuesto) | — | T031–T032 | (60) |
| | | **Total dentro del presupuesto** | **810** |

---

## Phase 1: Setup

**Propósito**: fijar por prueba las firmas reales que el bucle consume y crear el paquete de pruebas nuevo.

- [ ] T001 Crear `tests/core/` y la prueba de firmas de los contratos consumidos en `tests/core/test_loop_contract_signatures.py`
  - **Objetivo**: crear `tests/core/__init__.py` y una prueba que, con `inspect`, afirme las firmas reales que usa el bucle: `Provider.complete` y `Tool.run` son `async def`; `ToolRegistry.get/list/validate_args`, `PermissionPolicy.evaluate` y `EventBus.emit` son síncronas; `validate_args(name, args) -> dict`; `evaluate(call) -> PermissionDecision`; los 17 miembros de `EventType` incluyen los siete que usa el bucle (`USER_MESSAGE`, `ASSISTANT_MESSAGE`, `TOOL_REQUESTED`, `PERMISSION_DECIDED`, `TOOL_FINISHED`, `PROVIDER_ERROR`, `INTERRUPTED`); `ToolCall` es `frozen` con `arguments: dict`; `Event.create(session_id, type, payload)` existe.
  - **Archivos**: `tests/core/__init__.py`, `tests/core/test_loop_contract_signatures.py`
  - **Estimación**: 25 min
  - **Dependencias**: ninguna
  - **Historia / actividad**: base de todas las historias / Sp1-12
  - **Criterios relacionados**: FR-027, FR-033, plan «Interfaces reutilizadas» (verificado con `archivo:línea`)
  - **Evidencia requerida**: salida de `pytest tests/core/test_loop_contract_signatures.py` en verde y `mypy` estricto sobre el archivo
  - **Completada cuando**: la prueba pasa sin modificar ningún archivo bajo `src/harness_agent/core/` (`git diff --stat -- src/harness_agent/core` vacío) y si una firma real difiere de la esperada se registra en `docs/PROGRESO.md` antes de continuar.

---

## Phase 2: Foundational (bloquea las historias)

**Propósito**: dobles de prueba (Sp1-14), tipos del resultado y constructor, y el publicador de eventos. Los dobles **no implementan** HU-00-03, HU-01-02, HU-01-05 ni HU-05-01: son dobles de prueba con nombres que lo dejan claro.

- [ ] T002 [P] Crear el doble `ScriptedProvider` y el ayudante `run_bounded` en `tests/doubles/scripted_provider.py` y `tests/doubles/bounded.py`
  - **Objetivo**: `ScriptedProvider(Provider)` con guion finito de `ProviderResponse` (incluye respuestas con varias `tool_calls`), registro de las listas recibidas en cada consulta (copias, para comprobar FR-002), contador de consultas, valida al construirse que los ids de llamada del guion sean no vacíos y únicos en toda la sesión (salvo `allow_invalid_ids=True`, para las pruebas negativas de FR-024), y al agotarse el guion lanza `ScriptExhausted` y marca `exhausted=True`; también puede lanzar una excepción configurada en la consulta N y esperar (para cancelación). `run_bounded(coro, timeout=…)` envuelve `asyncio.timeout` y, tras terminar, falla si `provider.exhausted` es verdadero (agotar el guion es un fallo de prueba explícito, condición 2 de Q1).
  - **Archivos**: `tests/doubles/scripted_provider.py`, `tests/doubles/bounded.py`
  - **Estimación**: 20 min
  - **Dependencias**: T001
  - **Historia / actividad**: fundacional / Sp1-14
  - **Criterios relacionados**: FR-028 (condiciones del PO: guiones finitos, agotamiento ⇒ fallo, *timeouts*), FR-034, SC-010
  - **Evidencia requerida**: `mypy` estricto sobre ambos archivos y una prueba mínima (en `tests/core/test_loop_contract_signatures.py` o `tests/doubles/`) que cumpla `Provider` real y compruebe el agotamiento
  - **Completada cuando**: el doble pasa `isinstance(…, Provider)`, agotar el guion lanza `ScriptExhausted` y `run_bounded` falla con él; sin dependencias nuevas.

- [ ] T003 [P] Crear los dobles `InMemoryToolRegistry` y `ScriptedPolicy` en `tests/doubles/in_memory_registry.py` y `tests/doubles/scripted_policy.py`
  - **Objetivo**: registro mínimo de pruebas que implementa `ToolRegistry` (`register/get/list/validate_args`): `validate_args` valida contra un validador inyectable, puede **normalizar** (devolver un `dict` nuevo con argumentos efectivos distintos de la entrada), registrar la entrada recibida y comprobar que no se muta; modos configurables (lanza `ValueError`, lanza otra `Exception`, devuelve un valor que no es `dict`). `ScriptedPolicy(PermissionPolicy)` mapea nombre de herramienta → `PermissionDecision`/excepción/valor inesperado, **lo no mapeado ⇒ `DENY`**, y registra cada `ToolCall` recibida (para R-07). No es la HU-01-02 ni la HU-05-01.
  - **Archivos**: `tests/doubles/in_memory_registry.py`, `tests/doubles/scripted_policy.py`
  - **Estimación**: 20 min
  - **Dependencias**: T001
  - **Historia / actividad**: fundacional / Sp1-14
  - **Criterios relacionados**: FR-008, FR-009, FR-014, FR-034, R-07
  - **Evidencia requerida**: `mypy` estricto; ambos pasan `isinstance` contra las ABC reales
  - **Completada cuando**: los dobles cumplen las ABC, registran lo que reciben y ninguno aplica un permiso por defecto distinto de `DENY`.

- [ ] T004 Crear los dobles de herramientas y el bus que falla en `tests/doubles/scripted_tools.py` y `tests/doubles/failing_bus.py` y reexportar los dobles nuevos en `tests/doubles/__init__.py`
  - **Objetivo**: `RecordingTool` (cuenta ejecuciones, registra los `args` recibidos exactos, devuelve un `ToolResult` configurable con `call_id` configurable para probar la corrección del id), `FailingTool` (devuelve `is_error=True`), `RaisingTool` (lanza una excepción), `BlockingTool` (espera un `asyncio.Event` para probar cancelación), y un `ToolResult` inválido (no `ToolResult`) configurable. `FailingEventBus(RecordingEventBus)` lanza una excepción configurada al recibir tipos concretos de `EventType` (cuenta los intentos). Reexportar en `tests/doubles/__init__.py`, en esta única tarea y después de T002 y T003, los dobles nuevos de T002, T003 y T004 sin quitar nada de lo existente (archivo compartido: por eso T004 no lleva `[P]`).
  - **Archivos**: `tests/doubles/scripted_tools.py`, `tests/doubles/failing_bus.py`, `tests/doubles/__init__.py`
  - **Estimación**: 20 min
  - **Dependencias**: T001, T002, T003 (reexporta sus dobles en un archivo compartido)
  - **Historia / actividad**: fundacional / Sp1-14
  - **Criterios relacionados**: FR-016, FR-018, FR-031, FR-034
  - **Evidencia requerida**: `mypy` estricto; `pytest tests/contracts` sigue en verde (los dobles existentes no cambian)
  - **Completada cuando**: los dobles cumplen `Tool` y `EventBus`, los existentes (`DummyProvider`, `DummyTool`, `RecordingEventBus`, `DummyApprover`) siguen intactos y sus pruebas pasan.

- [ ] T005 [P] Definir `TurnStatus`, `TurnResult`, `MissingDependencyError`, `InvalidHistoryError` y el constructor de `AgentLoop` en `src/harness_agent/core/loop.py`
  - **Objetivo**: crear el módulo con solo biblioteca estándar y contratos de `core/`: `TurnStatus(str, Enum)` (`COMPLETED`, `PROVIDER_FAILED`, `INVALID_PROVIDER_RESPONSE`), `TurnResult` (`@dataclass(frozen=True)` con `status`, `final_response`, `history: tuple[Message, …]`, `error`), los dos errores (`ValueError`), `AgentLoop.__init__(provider, registry, policy, bus)` que lanza `MissingDependencyError` nombrando al colaborador ausente (`provider`, `registry`, `policy`, `bus`) y la firma `async run_turn(*, session_id, task, history) -> TurnResult` (cuerpo inicial: `raise NotImplementedError`). No exportar desde `core/__init__.py`. Comentario de módulo que documenta la correspondencia con «`core/agent`».
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 40 min
  - **Dependencias**: T001
  - **Historia / actividad**: fundacional / Sp1-12
  - **Criterios relacionados**: FR-006, FR-025, FR-032, FR-033, D-PLAN-01, D-PLAN-02, D-PLAN-13
  - **Evidencia requerida**: `mypy --strict` sobre `src/harness_agent/core/loop.py`; `pytest tests/architecture/test_core_boundaries.py` sigue en verde
  - **Completada cuando**: `AgentLoop(None, …)` lanza `MissingDependencyError` con el nombre del ausente para cada uno de los cuatro colaboradores, `run_turn` existe con la firma del contrato y ningún archivo compartido fue modificado.

- [ ] T006 Implementar los constructores de carga y el publicador de eventos en `src/harness_agent/core/loop.py`
  - **Objetivo**: auxiliares privados: `_emit(type, payload)` que construye `Event.create(session_id, type, payload)` y llama a `bus.emit` **sin capturar nada** (Q4), y los constructores de carga de los siete eventos según `contracts/agent-loop-contract.md` §5 (`USER_MESSAGE`, `ASSISTANT_MESSAGE`, `TOOL_REQUESTED`, `PERMISSION_DECIDED`, `TOOL_FINISHED`, `PROVIDER_ERROR`, `INTERRUPTED`), sin argumentos de herramientas ni contenido de archivos; mensajes acotados a 500 caracteres.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 30 min
  - **Dependencias**: T005
  - **Historia / actividad**: fundacional / Sp1-13
  - **Criterios relacionados**: FR-029, FR-031, D-PLAN-11
  - **Evidencia requerida**: `mypy --strict`; comprobación puntual en sesión (sin archivo permanente) de que las cargas no contienen argumentos de herramientas; la prueba permanente de las cargas pertenece a la fase US4 y no es prerrequisito de esta tarea
  - **Completada cuando**: existe un único punto de emisión sin `try/except` y las cargas no contienen argumentos de herramientas.

**Checkpoint**: dobles listos, tipos y publicador definidos; las historias pueden comenzar.

---

## Phase 3: User Story 1 — Un guion de tres pasos se ejecuta en orden (P1) — AC-01

**Meta**: el bucle ejecuta tres herramientas en orden y termina cuando el modelo no pide más (AC-01 literal en `spec.md`).
**Prueba independiente**: guion de cuatro respuestas (tres con una herramienta cada una, una final) con `ScriptedProvider`, `InMemoryToolRegistry`, `ScriptedPolicy(ALLOW)` y `RecordingTool`.

- [ ] T007 [US1] Escribir en ROJO las pruebas de AC-01 en `tests/core/test_loop_happy_path.py`
  - **Objetivo**: AC-01 y SC-001: tres herramientas ejecutadas en orden y una vez cada una, cuatro consultas, respuesta final, 20 repeticiones idénticas; texto + `tool_calls` no es respuesta final (FR-004); una respuesta con varias `tool_calls` se procesa en orden, un `ToolResult`/`TOOL` por llamada y las llamadas continúan tras una fallida (Q2); cada consulta recibe una copia del historial y las `ToolDefinition` salen de `Tool.name/description/schema` (FR-002); un doble que cumple `Provider` real (`DummyProvider`) funciona sin adaptaciones; pruebas mínimas de rechazo previo (herramienta desconocida y argumentos inválidos: ni política ni ejecución, con su resultado de error) y de R-07 (la política recibe una `ToolCall` con el mismo `id`/`name` y los argumentos efectivos que devuelve `validate_args`), que dan a T010 y T011 evidencia propia en VERDE. Los ids de llamada de los guiones son no vacíos y únicos en toda la sesión. Todas bajo `run_bounded`.
  - **Archivos**: `tests/core/test_loop_happy_path.py`
  - **Estimación**: 25 min
  - **Dependencias**: T002, T003, T004, T005
  - **Historia / actividad**: US1 / Sp1-14
  - **Criterios relacionados**: **AC-01**, FR-002, FR-003, FR-004, FR-015, SC-001
  - **Evidencia requerida**: salida de `pytest tests/core/test_loop_happy_path.py` mostrando las pruebas **fallando** (ROJO) por `NotImplementedError`
  - **Completada cuando**: las pruebas existen, están tipadas (`mypy` estricto) y fallan únicamente porque `run_turn` aún no está implementado; el texto de AC-01 usado en el docstring es literal.

- [ ] T008 [US1] Implementar la consulta al proveedor con copia del historial, `ToolDefinition` y validación de la respuesta en `src/harness_agent/core/loop.py`
  - **Objetivo**: en `run_turn`, cada consulta llama a `provider.complete(list(history), tools)` con `tools = [ToolDefinition(name=t.name, description=t.description, parameters=t.schema) for t in registry.list()]` recalculadas cada vez; valida la `ProviderResponse` (tipo correcto; ids de llamada no vacíos y únicos entre sí y respecto de las llamadas previas del historial: la unicidad en todo el historial proviene de la validación canónica de HU-07-01, D-02 §4.7, no del contrato `Provider`); si no, devuelve el resultado `INVALID_PROVIDER_RESPONSE` (el detalle de eventos y del fallo del proveedor se completa en T024).
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 35 min
  - **Dependencias**: T005, T006, T007
  - **Historia / actividad**: US1 / Sp1-12
  - **Criterios relacionados**: FR-002, FR-024, R-04 del plan, D-PLAN-03
  - **Evidencia requerida**: las pruebas de copia del historial y de `ToolDefinition` de T007 pasan a VERDE
  - **Completada cuando**: el proveedor nunca recibe la lista mutable del bucle y las definiciones reflejan el registro actual.

- [ ] T009 [US1] Implementar la tarea del usuario, el mensaje del asistente y la condición de parada en `src/harness_agent/core/loop.py`
  - **Objetivo**: añadir `Message(USER, task)` al historial del llamador (tras la precondición, T021), construir `Message(ASSISTANT, content, tuple(tool_calls), usage)` conservando `Message.content`, `ToolCall` y `TokenUsage`; la presencia de `tool_calls` prevalece sobre el texto; una respuesta sin `tool_calls` añade el `ASSISTANT` final y devuelve `TurnResult(COMPLETED, final_response, history)` sin consulta adicional; sin límite de iteraciones ni parámetro de turnos (FR-028).
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 30 min
  - **Dependencias**: T008
  - **Historia / actividad**: US1 / Sp1-12 (la publicación de los eventos de este paso es T018)
  - **Criterios relacionados**: **AC-01**, FR-001, FR-003, FR-004, FR-007, FR-028
  - **Evidencia requerida**: la prueba de respuesta final y de texto + llamadas de T007 en VERDE
  - **Completada cuando**: una respuesta sin llamadas termina el turno con `COMPLETED`, sin añadir parámetros de límite ni emitir `LIMIT_REACHED`.

- [ ] T010 [US1] Implementar el procesamiento secuencial por llamada: herramienta desconocida, validación y argumentos efectivos (R-07, parte 1) en `src/harness_agent/core/loop.py`
  - **Objetivo**: recorrer `tool_calls` **en orden y una a una**; por llamada: `registry.get(name)` (ausente o excepción ⇒ resultado `unknown_tool`, sin política ni ejecución); `registry.validate_args(name, call.arguments)` pasando una copia profunda de los argumentos (para que el registro no pueda mutar `call.arguments`); cualquier `Exception` o retorno que no sea `dict` ⇒ resultado `invalid_arguments` con el motivo (≤500 caracteres) sin consultar la política; si el retorno es un `dict`, tomar una **copia profunda** como **argumentos efectivos**, conservando los argumentos originales solo para diagnóstico. Los rechazos se convierten en `ToolResult(call_id=call.id, is_error=True)` con texto estructurado `[unknown_tool]`/`[invalid_arguments]` y se añade su `Message(TOOL)` al historial inmediatamente; continuar con la siguiente llamada.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 35 min
  - **Dependencias**: T009
  - **Historia / actividad**: US1 / Sp1-12
  - **Criterios relacionados**: FR-008(a)(b), FR-010, FR-011, FR-015, FR-019, R-07
  - **Evidencia requerida**: las pruebas de T007 de múltiples llamadas en orden y de rechazo previo (herramienta desconocida y argumentos inválidos) pasan a VERDE (evidencia propia: no depende de pruebas de tareas posteriores)
  - **Completada cuando**: una llamada desconocida o con argumentos rechazados no consulta la política ni ejecuta nada, y los argumentos efectivos son una copia independiente del `dict` de `validate_args` y de `call.arguments`.

- [ ] T011 [US1] Implementar la evaluación de la política sobre una `ToolCall` con los argumentos efectivos (R-07, parte 2) y la compuerta `ALLOW` en `src/harness_agent/core/loop.py`
  - **Objetivo**: construir la `ToolCall` de evaluación con `id` y `name` del original y **otra copia profunda** de los argumentos efectivos (`dataclasses.replace(call, arguments=…)`), invocar `policy.evaluate(eval_call)`; solo si el valor es exactamente `PermissionDecision.ALLOW` se prosigue a ejecutar con los argumentos autorizados (una copia propia, distinta de la que vio la política); toda otra salida (otro valor, excepción) se trata como no ejecutable (el mapeo detallado y los textos de `DENY`/`ASK`/fallo es T016). La `ToolCall` original no se pasa a la política.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 35 min
  - **Dependencias**: T010
  - **Historia / actividad**: US1 / Sp1-12
  - **Criterios relacionados**: FR-008(c), FR-009, FR-014, R-07
  - **Evidencia requerida**: la prueba mínima de R-07 de T007 (la política recibe los argumentos efectivos con el mismo `id`/`name`) pasa a VERDE; las pruebas completas de permisos de la fase US3 (incluida la inmutabilidad posterior a la autorización) se ejecutan cuando esa fase se complete y no son prerrequisito de esta tarea
  - **Completada cuando**: la herramienta no se ejecuta salvo con `ALLOW` exacto y los argumentos que se ejecutan son los mismos valores que se autorizaron.

- [ ] T012 [US1] Implementar la ejecución, la normalización del resultado, la conservación de `call_id` y el mensaje `TOOL` en `src/harness_agent/core/loop.py`
  - **Objetivo**: `await tool.run(authorized_args)` solo con `ALLOW`; el `ToolResult` entregado lleva siempre `call_id = call.id` (`dataclasses.replace` si la herramienta informó otro); `Message(role=TOOL, content=tool_result.content, tool_result=…, is_external=True)` añadido al historial **inmediatamente** al terminar cada llamada y antes de procesar la siguiente; solo tras la última llamada se vuelve a consultar al proveedor. Con esto AC-01 queda en VERDE.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 30 min
  - **Dependencias**: T011
  - **Historia / actividad**: US1 / Sp1-12
  - **Criterios relacionados**: **AC-01**, FR-003, FR-015, FR-016, FR-021, FR-022, SC-001
  - **Evidencia requerida**: `pytest tests/core/test_loop_happy_path.py` completo en VERDE bajo `run_bounded`; `mypy --strict` y `ruff` sobre `loop.py`
  - **Completada cuando**: el guion de tres pasos termina con la respuesta final, las tres herramientas se ejecutaron una vez y en orden, y cada `TOOL` tiene `content == tool_result.content` y `call_id` igual al `id` de la llamada.

**Checkpoint US1**: AC-01 verificable de forma independiente con dobles (MVP junto con US2).

---

## Phase 4: User Story 2 — Un error de herramienta vuelve al modelo (P1) — AC-02

**Meta**: una herramienta que falla se devuelve al modelo como resultado estructurado y el bucle continúa (AC-02 literal en `spec.md`).
**Prueba independiente**: `FailingTool`/`RaisingTool` en el segundo paso de un guion de tres; el modelo recibe el error y el guion llega a su respuesta final.

- [ ] T013 [US2] Escribir en ROJO las pruebas de AC-02 y de errores de herramienta en `tests/core/test_loop_tool_errors.py`
  - **Objetivo**: AC-02 y SC-003: `is_error=True` devuelto íntegro con el `id` de la llamada y el bucle continúa; excepción de la herramienta ⇒ resultado de error con nombre de clase y mensaje, sin traza; retorno que no es `ToolResult` ⇒ error `invalid_tool_result`; `call_id` ajeno informado por la herramienta ⇒ se fuerza el `id` de la llamada; herramienta desconocida ⇒ error que nombra la herramienta; varias llamadas con una fallida: las demás se procesan y cada una tiene su resultado; el contenido de los resultados de herramientas no se recorta; `is_external` verdadero para resultados de la herramienta y falso para rechazos del bucle. Las excepciones de `Exception` no escapan; `CancelledError` no se trata aquí (T023).
  - **Archivos**: `tests/core/test_loop_tool_errors.py`
  - **Estimación**: 25 min
  - **Dependencias**: T003, T004, T005
  - **Historia / actividad**: US2 / Sp1-14
  - **Criterios relacionados**: **AC-02**, FR-010, FR-016–FR-019, FR-022, SC-003
  - **Evidencia requerida**: salida de `pytest tests/core/test_loop_tool_errors.py` en ROJO
  - **Completada cuando**: las pruebas existen, están tipadas y fallan solo por comportamiento aún no implementado; el texto de AC-02 en el docstring es literal.

- [ ] T014 [US2] Implementar las categorías de fallo de herramienta y los textos estructurados en `src/harness_agent/core/loop.py`
  - **Objetivo**: `Tool.run` que lanza `Exception` ⇒ `[tool_exception] Tool '{name}' raised {ExceptionType}: {message}` (mensaje acotado a 500 caracteres, sin traza); retorno que no sea `ToolResult` con `content: str` ⇒ `[tool_exception] …returned an invalid result ({type})`; `ToolResult(is_error=True)` de la herramienta pasa íntegro con `call_id` forzado; `CancelledError` (es `BaseException`) **nunca** se captura; `is_external=True` para `ok`, `tool_error`, `tool_exception` e `invalid_tool_result`, `False` para los rechazos previos a la ejecución; el bucle continúa tras cada fallo. Categorías: `ok`, `tool_error`, `tool_exception`, `invalid_tool_result`, `unknown_tool`, `invalid_arguments`, `permission_denied`, `approval_required_unavailable`.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 30 min
  - **Dependencias**: T012, T013
  - **Historia / actividad**: US2 / Sp1-12
  - **Criterios relacionados**: **AC-02**, FR-017, FR-018, FR-019, FR-022, SC-003
  - **Evidencia requerida**: `pytest tests/core/test_loop_tool_errors.py` completo en VERDE
  - **Completada cuando**: el 100 % de los fallos de herramienta llega al modelo como `ToolResult(is_error=True)` con el `id` de la llamada y el bucle sigue hasta la respuesta final; ninguna excepción de herramienta escapa y `CancelledError` no se absorbe.

**Checkpoint US1+US2**: MVP (AC-01 + AC-02) completo y probado con dobles.

---

## Phase 5: User Story 3 — Nada se ejecuta sin validación ni permisos (P1) — R-07

**Meta**: ninguna herramienta se ejecuta sin validación y decisión `ALLOW`; la política evalúa los argumentos efectivos y se ejecuta exactamente lo autorizado.
**Prueba independiente**: contador de ejecuciones por escenario con `ScriptedPolicy` y registro doble que rechaza o normaliza argumentos.

- [ ] T015 [US3] Escribir en ROJO las pruebas de permisos y de R-07 en `tests/core/test_loop_permissions.py`
  - **Objetivo**: SC-002 (contador de ejecuciones solo avanza con válido + `ALLOW`): argumentos inválidos (la política no se consulta), `DENY`, `ASK` (resuelto como denegación con mensaje de aprobación no disponible; sin eventos `APPROVAL_*`), política que lanza, política que devuelve un valor que no es `PermissionDecision`, política sin mapeo ⇒ `DENY`; **R-07**: la política recibe una `ToolCall` con el mismo `id` y `name` y los **argumentos efectivos** del registro que normaliza (no los crudos); `Tool.run` recibe exactamente los argumentos autorizados; mutar `call.arguments` original, el `dict` devuelto por `validate_args` o lo recibido por la política después de autorizar **no altera** lo ejecutado; el registro no puede mutar `call.arguments`; los argumentos originales permanecen en el mensaje `ASSISTANT` del historial; sin cambios de firma. Todo ejecutado bajo `run_bounded`.
  - **Archivos**: `tests/core/test_loop_permissions.py`
  - **Estimación**: 35 min
  - **Dependencias**: T003, T004, T005
  - **Historia / actividad**: US3 / Sp1-14
  - **Criterios relacionados**: FR-008, FR-009, FR-011–FR-014, SC-002, R-07
  - **Evidencia requerida**: salida de `pytest tests/core/test_loop_permissions.py` en ROJO (las de R-07 y las de `ALLOW` avanzan con T010–T012)
  - **Completada cuando**: las pruebas existen, están tipadas y cubren cada fila de la matriz de errores de permisos del contrato §3 y los cuatro puntos de R-07 (política ve efectivos, herramienta recibe autorizados, mutaciones posteriores no alteran, `id`/`name` conservados).

- [ ] T016 [US3] Implementar el mapeo `DENY`/`ASK`/fallo de política con falla cerrada en `src/harness_agent/core/loop.py`
  - **Objetivo**: `DENY` ⇒ `[permission_denied] Tool '{name}' was denied by the permission policy.`; `ASK` (Sprint 1) ⇒ `[approval_required_unavailable] …resolved as denied.`; excepción o valor inesperado de `evaluate` ⇒ tratado como `DENY` con `…could not be evaluated and was denied (fail closed).`; `Approver` no se usa; el bucle trata como no ejecutable todo valor distinto de `ALLOW` y es la última barrera sin duplicar la política provisional de C (Sp1-35); no se amplían permisos desde el núcleo. Todos con `is_error=True`, `is_external=False`.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 25 min
  - **Dependencias**: T011, T015
  - **Historia / actividad**: US3 / Sp1-12
  - **Criterios relacionados**: FR-009, FR-012, FR-013, FR-014, FR-019, SC-002, Q5
  - **Evidencia requerida**: `pytest tests/core/test_loop_permissions.py` completo en VERDE
  - **Completada cuando**: en todos los escenarios de la matriz de permisos el número de ejecuciones de herramientas coincide con las llamadas válidas permitidas y ninguna ruta ejecuta con `DENY`, `ASK` o un valor inesperado.

---

## Phase 6: User Story 4 — Cada hecho relevante es un evento (P2) — Q4

**Meta**: los hechos relevantes salen por `EventBus.emit` en el orden definido y el bucle propaga cualquier excepción de `emit`.
**Prueba independiente**: `RecordingEventBus` registra la secuencia exacta; `FailingEventBus` falla en cada tipo de evento.

- [ ] T017 [US4] Escribir en ROJO las pruebas de eventos y de Q4 en `tests/core/test_loop_events.py`
  - **Objetivo**: secuencia exacta de eventos en el guion de tres pasos (`USER_MESSAGE`, `ASSISTANT_MESSAGE`, por llamada `TOOL_REQUESTED` < `PERMISSION_DECIDED` < `TOOL_FINISHED`, respuesta final) con las cargas del contrato §5; sin suscriptores el resultado es idéntico; ni `LIMIT_REACHED` ni `APPROVAL_REQUESTED`/`APPROVAL_RESOLVED` en ningún escenario; salida estándar y de error capturadas vacías (`capsys`/`capfd`); **Q4**: `FailingEventBus` que lanza en cada tipo (`USER_MESSAGE`, `ASSISTANT_MESSAGE`, `TOOL_REQUESTED`, `PERMISSION_DECIDED`, `TOOL_FINISHED`): la excepción original se propaga (no un `ToolResult`, no un `TurnResult`), sin reintentos (un solo intento de `emit` fallido), la herramienta de esa llamada **no** se ejecuta si el fallo ocurre en `TOOL_REQUESTED`/`PERMISSION_DECIDED`, y con `TOOL_FINISHED` fallido la herramienta **ya** se ejecutó una sola vez, su `TOOL` ya está en el historial y no se repite ni se ejecutan las llamadas siguientes.
  - **Archivos**: `tests/core/test_loop_events.py`
  - **Estimación**: 25 min
  - **Dependencias**: T004, T012
  - **Historia / actividad**: US4 / Sp1-14
  - **Criterios relacionados**: FR-029, FR-030, FR-031, FR-028, SC-004, SC-006, Q3, Q4
  - **Evidencia requerida**: salida de `pytest tests/core/test_loop_events.py` en ROJO
  - **Completada cuando**: las pruebas existen, están tipadas y distinguen explícitamente suscriptor aislado (fuera del bucle), fallo real de `emit`, fallo de herramienta, fallo del proveedor y cancelación.

- [ ] T018 [US4] Implementar los puntos de publicación y el orden de eventos en `src/harness_agent/core/loop.py`
  - **Objetivo**: publicar con `_emit` (T006) en los puntos del contrato §5: `USER_MESSAGE` tras añadir el `USER`; `ASSISTANT_MESSAGE` tras añadir el `ASSISTANT` si hay texto (con `tool_call_count` y `final`); por llamada `TOOL_REQUESTED` antes de procesarla (por llamada, no por lote), `PERMISSION_DECIDED` solo para llamadas que llegan a la política (con `decision`, `resolved_as`, `reason`), `TOOL_FINISHED` tras añadir el `TOOL` (con `category`); orden relativo garantizado; sin `print`.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 30 min
  - **Dependencias**: T006, T012, T016, T017
  - **Historia / actividad**: US4 / Sp1-13
  - **Criterios relacionados**: FR-029, FR-030, SC-006
  - **Evidencia requerida**: las pruebas de secuencia y cargas de `tests/core/test_loop_events.py` en VERDE
  - **Completada cuando**: la secuencia observada en el bus coincide exactamente con la tabla de eventos del contrato en el 100 % de los escenarios de éxito, error y denegación.

- [ ] T019 [US4] Implementar y verificar la semántica de fallo de `emit` (Q4) en `src/harness_agent/core/loop.py`
  - **Objetivo**: confirmar que ningún punto de publicación captura excepciones del bus; ordenar las operaciones para que el estado sea seguro: `TOOL_REQUESTED` y `PERMISSION_DECIDED` se publican **antes** de ejecutar; el mensaje `TOOL` se añade al historial **antes** de publicar `TOOL_FINISHED`; ante un fallo de `emit` el bucle no ejecuta herramientas posteriores, no reintenta y no convierte la excepción en `ToolResult`; no se asume rollback tras una operación con efectos.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 35 min
  - **Dependencias**: T018
  - **Historia / actividad**: US4 / Sp1-13
  - **Criterios relacionados**: FR-031, Q4 (reglas 1–7), D-PLAN-06, D-PLAN-09
  - **Evidencia requerida**: todas las pruebas de Q4 de `tests/core/test_loop_events.py` en VERDE; revisión del diff sin `except` alrededor de `bus.emit`
  - **Completada cuando**: `rg "except" src/harness_agent/core/loop.py` no muestra ningún `except` que envuelva una llamada a `_emit`/`bus.emit` salvo el caso acotado de R-08 (T026), y las pruebas Q4 pasan.

---

## Phase 7: User Story 5 — Historial coherente y dependencias ausentes fallan cerrado (P2)

**Meta**: el historial solo crece por añadido y es canónicamente válido entre turnos; un historial inválido o una dependencia ausente fallan antes de cualquier efecto.
**Prueba independiente**: dos turnos consecutivos sobre la misma lista; historiales inválidos; constructor con cada colaborador ausente.

- [ ] T020 [US5] Escribir en ROJO las pruebas de historial, varios turnos y colaboradores ausentes en `tests/core/test_loop_history.py` y `tests/core/test_loop_construction.py`
  - **Objetivo**: solo se añade (nada se modifica, reordena ni elimina; `TOOL.content == tool_result.content`); un segundo turno sobre el historial del primero conserva el orden y la correlación de ids; en cada consulta el historial pasa la validación canónica existente (oráculo de HU-07-01 usado **solo en la prueba**: `validate_canonical_messages` y conversión con los dos convertidores, SC-005); `InvalidHistoryError` para SYSTEM intercalado (fuera del prefijo contiguo), llamadas pendientes de un turno cancelado/interrumpido e ids repetidos, sin añadir ni publicar nada; los guiones del segundo turno usan ids distintos de los del primero (una respuesta que repite un id ya presente en el historial es `INVALID_PROVIDER_RESPONSE`, T023); el contexto no se asume «solo SYSTEM»; `AgentLoop` con cada uno de los cuatro colaboradores `None` ⇒ `MissingDependencyError` que lo nombra, 0 consultas y 0 ejecuciones (SC-008).
  - **Archivos**: `tests/core/test_loop_history.py`, `tests/core/test_loop_construction.py`
  - **Estimación**: 25 min
  - **Dependencias**: T002, T003, T004, T005
  - **Historia / actividad**: US5 / Sp1-14
  - **Criterios relacionados**: FR-001, FR-020, FR-021, FR-025, SC-005, SC-008
  - **Evidencia requerida**: salida de `pytest tests/core/test_loop_history.py tests/core/test_loop_construction.py` en ROJO (construcción ya en VERDE por T005)
  - **Completada cuando**: las pruebas existen, están tipadas, y la validación canónica se obtiene de `adapters/converters/` solo desde el código de prueba.

- [ ] T021 [US5] Implementar `_check_history` y `InvalidHistoryError` en `src/harness_agent/core/loop.py`
  - **Objetivo**: comprobación estructural mínima y privada del historial inicial sin importar `adapters/`: mensajes `SYSTEM` solo como prefijo contiguo (regla de HU-07-01), ids de llamada únicos, y cada `ASSISTANT` con llamadas seguido de su `TOOL` por cada id en orden (un historial que termina en llamadas sin resultado se rechaza); se ejecuta antes de añadir cualquier mensaje o publicar cualquier evento; lanza `InvalidHistoryError` con el motivo. No se asume que el historial contenga solo `SYSTEM`.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 35 min
  - **Dependencias**: T009, T020
  - **Historia / actividad**: US5 / Sp1-12
  - **Criterios relacionados**: FR-001, FR-020, FR-021, FR-026, D-PLAN-05
  - **Evidencia requerida**: pruebas de historial inválido de T020 en VERDE; `pytest tests/architecture/test_core_boundaries.py` sigue en verde
  - **Completada cuando**: los historiales inválidos fallan antes de cualquier efecto y un historial válido de varios turnos se acepta.

- [ ] T022 [US5] Implementar la instantánea del historial en `TurnResult` y la reutilización entre turnos en `src/harness_agent/core/loop.py`
  - **Objetivo**: `TurnResult.history` es una instantánea `tuple` del estado final; el bucle añade en el sitio a la lista del llamador (propiedad del llamador, sin referencias entre turnos), de modo que el siguiente turno reutiliza la misma lista; sin persistencia ni reanudación por identificador y sin `ContextManager`; tras `COMPLETED`, `PROVIDER_FAILED` o `INVALID_PROVIDER_RESPONSE` el historial es reutilizable; `AgentLoop` queda sin estado por turno.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 20 min
  - **Dependencias**: T021, T012
  - **Historia / actividad**: US5 / Sp1-12
  - **Criterios relacionados**: FR-006, FR-007, FR-020, SC-005
  - **Evidencia requerida**: `pytest tests/core/test_loop_history.py tests/core/test_loop_construction.py` en VERDE y `tests/contracts/test_loop_canonical_oracle.py` (si se crea ahí el oráculo) en VERDE
  - **Completada cuando**: dos turnos consecutivos sobre la misma lista conservan el orden y los ids, y la instantánea devuelta no es mutable.

---

## Phase 8: User Story 6 — Fallos del proveedor y cancelación terminan de forma explícita (P2) — R-08

**Meta**: un fallo del proveedor o una cancelación terminan de forma explícita, con un solo evento, sin reintentos ni historial corrupto; la cancelación prevalece sobre un fallo de `emit(INTERRUPTED)`.
**Prueba independiente**: proveedor que falla; herramienta bloqueante cancelada; bus que falla al recibir `INTERRUPTED`.

- [ ] T023 [US6] Escribir en ROJO las pruebas de fallos, cancelación y R-08 en `tests/core/test_loop_failures.py`
  - **Objetivo**: SC-009: fallo del proveedor ⇒ `TurnResult(PROVIDER_FAILED)`, un solo `PROVIDER_ERROR`, 0 reintentos, 0 conmutaciones; respuesta inválida (ids vacíos o repetidos, dentro de la respuesta o respecto del historial) ⇒ `INVALID_PROVIDER_RESPONSE`, ninguna llamada ejecutada y la respuesta no se añade; cancelación durante `Provider.complete` y durante una herramienta (`BlockingTool`) ⇒ `CancelledError` llega al llamador, exactamente un `INTERRUPTED` con `phase`, ninguna consulta ni herramienta posterior, ningún `ToolResult` fabricado, historial parcial del llamador sin duplicados; el historial interrumpido a mitad de llamadas se rechaza en el turno siguiente con `InvalidHistoryError`; **R-08**: con `FailingEventBus` que lanza en `INTERRUPTED` durante una cancelación, la excepción propagada **es la `CancelledError` original** (no el error del bus), con el diagnóstico del fallo adjunto como nota (`__notes__` contiene el tipo y el mensaje del error del bus; la prueba NO exige `__context__`, que no queda con el error del bus), un solo intento de `emit`, sin más herramientas ni reintentos ni `ToolResult`; **contraste**: un fallo de `emit` fuera de una cancelación se propaga como el error del bus (Q4); si falla `PROVIDER_ERROR` se propaga el error del bus encadenado al del proveedor; salida estándar vacía.
  - **Archivos**: `tests/core/test_loop_failures.py`
  - **Estimación**: 30 min
  - **Dependencias**: T002, T004, T005
  - **Historia / actividad**: US6 / Sp1-14
  - **Criterios relacionados**: FR-005, FR-023, FR-024, FR-026, SC-009, R-08, Q4
  - **Evidencia requerida**: salida de `pytest tests/core/test_loop_failures.py` en ROJO
  - **Completada cuando**: las pruebas existen, están tipadas, distinguen cancelación de errores ordinarios del bus y ninguna usa red.

- [ ] T024 [US6] Implementar el fallo del proveedor y la respuesta inválida como `TurnResult` explícito en `src/harness_agent/core/loop.py`
  - **Objetivo**: `Provider.complete` que lanza `Exception` (no `BaseException`) ⇒ publicar `PROVIDER_ERROR(reason=provider_exception, error_type, message≤500)` y devolver `TurnResult(PROVIDER_FAILED, error=…)` con el historial hasta ese punto, sin reintento ni fallback; respuesta inválida ⇒ `PROVIDER_ERROR(reason=invalid_response)` y `TurnResult(INVALID_PROVIDER_RESPONSE)` sin ejecutar nada y sin añadir la respuesta; si `emit(PROVIDER_ERROR)` falla se propaga el error del bus encadenado al del proveedor.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 30 min
  - **Dependencias**: T009, T006, T023
  - **Historia / actividad**: US6 / Sp1-12
  - **Criterios relacionados**: FR-005, FR-023, FR-024, SC-009
  - **Evidencia requerida**: pruebas de proveedor e inválida de T023 en VERDE
  - **Completada cuando**: ningún camino reintenta ni cambia de proveedor y el resultado y el evento son los de la tabla del contrato §3.

- [ ] T025 [US6] Implementar la cancelación (`INTERRUPTED` una sola vez y re-lanzar) en `src/harness_agent/core/loop.py`
  - **Objetivo**: un `try` externo alrededor del turno captura `asyncio.CancelledError`, determina la fase (`provider_call` o `tool_execution`, y `call_id`), publica `INTERRUPTED` **una sola vez** con `_emit`, y vuelve a lanzar la cancelación original; sin `asyncio.shield`, sin limpieza propia ni fabricación de resultados «interrumpido» (V-11 → HU-06-03); los `except Exception` de herramienta y proveedor nunca interceptan `CancelledError`; el historial del llamador queda sin duplicados ni orden alterado.
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 30 min
  - **Dependencias**: T024
  - **Historia / actividad**: US6 / Sp1-12
  - **Criterios relacionados**: FR-026, FR-027, SC-009, D-PLAN-10, D-01 §6 (pendiente de aprobación)
  - **Evidencia requerida**: pruebas de cancelación de T023 en VERDE
  - **Completada cuando**: la cancelación llega al llamador como `CancelledError` con un solo `INTERRUPTED`, sin consultas ni herramientas posteriores.

- [ ] T026 [US6] Implementar la precedencia de la cancelación sobre un fallo de `emit(INTERRUPTED)` (R-08) en `src/harness_agent/core/loop.py`
  - **Objetivo**: al publicar `INTERRUPTED` dentro del manejo de la cancelación, si `bus.emit` lanza, capturar **únicamente ese** fallo, adjuntar a la `CancelledError` original una nota con el tipo y el mensaje del fallo (`add_note`; mecanismo explícito: no se confía en `__context__`, que no queda con el error del bus) y re-lanzar la **`CancelledError` original** (no un error del bus); no reintentar, no ejecutar más herramientas, no convertirla en `ToolResult`. Ningún otro punto de publicación captura excepciones (Q4 intacta).
  - **Archivos**: `src/harness_agent/core/loop.py`
  - **Estimación**: 20 min
  - **Dependencias**: T025
  - **Historia / actividad**: US6 / Sp1-12
  - **Criterios relacionados**: FR-026, FR-031, R-08, Q4
  - **Evidencia requerida**: pruebas R-08 de T023 en VERDE, junto con las pruebas Q4 de T017 aún en VERDE
  - **Completada cuando**: con un bus que falla al recibir `INTERRUPTED` la excepción propagada es la `CancelledError` original con el diagnóstico en `__notes__`, y un fallo de `emit` fuera de una cancelación sigue propagando el error del bus.

- [ ] T027 [US6] Verificar y cerrar la publicación de `PROVIDER_ERROR` e `INTERRUPTED` y su comportamiento ante fallo en `src/harness_agent/core/loop.py`
  - **Objetivo**: revisar que las cargas (`reason`, `error_type`, `message` ≤500 caracteres; `phase`, `call_id`) coinciden con el contrato §5, que `INTERRUPTED` se publica una vez por cancelación y `PROVIDER_ERROR` una vez por fallo, que el orden relativo con el resto de eventos es el definido y que no existe ningún otro `except` que capture excepciones del bus; ajustar el código o el contrato (solo si hay discrepancia) y registrar el resultado.
  - **Archivos**: `src/harness_agent/core/loop.py`, `specs/005-basic-agent-loop/contracts/agent-loop-contract.md` (solo si hay discrepancia verificada)
  - **Estimación**: 20 min
  - **Dependencias**: T019, T024, T025, T026
  - **Historia / actividad**: US6 / Sp1-13
  - **Criterios relacionados**: FR-029, FR-031, SC-006, SC-009
  - **Evidencia requerida**: `pytest tests/core/test_loop_events.py tests/core/test_loop_failures.py` en VERDE
  - **Completada cuando**: la secuencia y las cargas de eventos de fallo coinciden con el contrato y no quedan discrepancias abiertas.

---

## Phase 9: Pulido y cierre

- [ ] T028 [P] Escribir las guardas de arquitectura (AST) en `tests/architecture/test_loop_boundaries.py`
  - **Objetivo**: con `ast`, comprobar que `src/harness_agent/core/loop.py` no usa `print`, `input`, `sys.stdout` ni `sys.stderr` (FR-030); solo importa biblioteca estándar y `harness_agent.core` (sin `adapters`, `cli`, `observability` ni SDKs comerciales: reutilizando `FORBIDDEN_PACKAGES` de `tests/architecture/test_core_boundaries.py`); no emite `EventType.LIMIT_REACHED` ni `APPROVAL_*`; no define un parámetro de límite de turnos en `run_turn`/`AgentLoop`; ningún archivo compartido de `core/` fue modificado por la historia; la prueba de fronteras existente sigue en verde.
  - **Archivos**: `tests/architecture/test_loop_boundaries.py`
  - **Estimación**: 15 min
  - **Dependencias**: T005
  - **Historia / actividad**: transversal / Sp1-14
  - **Criterios relacionados**: FR-028, FR-030, FR-032, FR-033, SC-004, SC-007
  - **Evidencia requerida**: `pytest tests/architecture` en verde
  - **Completada cuando**: las guardas pasan sobre el `loop.py` final y fallan si se introduce un `print` o un import prohibido (comprobado con una prueba negativa sobre código de ejemplo en memoria).

- [ ] T029 Ejecutar la puerta de calidad completa y corregir hallazgos en `src/harness_agent/core/loop.py` y `tests/`
  - **Objetivo**: `pytest` completo, `mypy` estricto sobre `src` y `tests`, `ruff check` y `ruff format --check` con el entorno 3.12; corregir lo que falle dentro del alcance de la historia; medir que la suite de la historia corre en menos de 5 s en memoria (SC-010); comprobar que la línea base previa (385 passed, 5 skipped) no se degrada.
  - **Archivos**: `src/harness_agent/core/loop.py`, `tests/core/*`, `tests/doubles/*`, `tests/architecture/test_loop_boundaries.py`
  - **Estimación**: 20 min
  - **Dependencias**: T014, T016, T019, T022, T027, T028
  - **Historia / actividad**: cierre / Sp1-13
  - **Criterios relacionados**: SC-010, Principio IV, Definition of Done (calidad)
  - **Evidencia requerida**: los cuatro comandos con su salida y resultado, que se registran en `docs/PROGRESO.md` al completar el registro documental; en WSL2 si hay entorno disponible
  - **Completada cuando**: los cuatro comandos terminan en verde, sin `# type: ignore` ni `noqa` nuevos injustificados y sin tests omitidos por esta historia.

- [ ] T030 Actualizar la documentación y el seguimiento sin declarar completada la historia en `docs/PROGRESO.md` y `specs/005-basic-agent-loop/tasks.md`
  - **Objetivo**: marcar las tareas completadas con su evidencia en este archivo; añadir en `docs/PROGRESO.md` una fila de registro por la implementación con comandos y resultados reales (ROJO observado de las pruebas, VERDE final, `mypy`, `ruff`) y los archivos tocados; pasar HU-01-01 a «En revisión» **solo** si T029 está en verde, nunca a «Hecha»; dejar listados como pendientes: revisión por otra área, CI remota de la matriz 3.12 (T008 de la spec 002), demostración del sprint, las integraciones T031/T032, ratificación formal de R-07/R-08/Q4 si corresponde, D-01 y las aprobaciones de HU-00-01/HU-07-01; actualizar el estado de `spec.md` y `plan.md` a «implementado, en revisión» sin tocar AC-01 ni AC-02.
  - **Archivos**: `docs/PROGRESO.md`, `specs/005-basic-agent-loop/tasks.md`, `specs/005-basic-agent-loop/spec.md`, `specs/005-basic-agent-loop/plan.md`
  - **Estimación**: 15 min
  - **Dependencias**: T029
  - **Historia / actividad**: cierre / Sp1-13
  - **Criterios relacionados**: Principio VIII (registro en `PROGRESO.md`), Principio IX (Definition of Done)
  - **Evidencia requerida**: diff documental revisado; `rg "Hecha" docs/PROGRESO.md` no muestra HU-01-01 como hecha
  - **Completada cuando**: el registro refleja la evidencia real, HU-01-01 no figura como `Hecha` y los pendientes externos están enumerados.

---

## Phase 10: Integración con las implementaciones reales de B y C (BLOQUEADAS — fuera del presupuesto de 810 min)

**No forman parte de la condición de terminado de A con dobles.** Quedan sin marcar hasta que B y C entreguen sus historias; un único `/speckit-implement` debe **dejarlas sin ejecutar**.

- [ ] T031 [BLOQUEADA: B] Prueba de integración con el `FakeProvider` real (HU-00-03) y el `EventBus` real (HU-01-05) en `tests/integration/test_loop_with_b_components.py`
  - **Objetivo**: ejecutar el guion de AC-01 con el `FakeProvider` de B (acepta respuestas con varias `tool_calls`, falla explícitamente al agotarse, no modifica la lista recibida; sus guiones emiten ids de llamada no vacíos y únicos en toda la sesión, también entre turnos, y coherentes con los `call_id` de los resultados: regla de la validación canónica de HU-07-01, que B debe confirmar) y el bus real; comprobar que un suscriptor que falla queda aislado por el bus y que un fallo propio de `emit` se propaga (Q4); verificar con un doble propio que `APPROVAL_*` son de B y no del bucle.
  - **Archivos**: `tests/integration/test_loop_with_b_components.py`
  - **Estimación**: 30 min (adicionales, fuera del presupuesto)
  - **Dependencias**: HU-00-03 y HU-01-05 entregadas por B; T012, T019
  - **Historia / actividad**: US1/US4 / integración (fuera de Sp1-12/13/14)
  - **Criterios relacionados**: **AC-01**, FR-031, Q3, Q4
  - **Evidencia requerida**: salida de `pytest tests/integration/test_loop_with_b_components.py`
  - **Completada cuando**: B confirma la semántica y la prueba pasa con sus implementaciones reales; hasta entonces permanece sin marcar.

- [ ] T032 [BLOQUEADA: C] Prueba de integración con el `ToolRegistry` real (HU-01-02) y la `PermissionPolicy` real (HU-05-01/Sp1-35) en `tests/integration/test_loop_with_c_components.py`
  - **Objetivo**: confirmar con C la semántica exacta de `validate_args` (devuelve un `dict` nuevo con los argumentos efectivos sin mutar la entrada; excepciones posibles) y que la política razona sobre los argumentos efectivos (R-07); ejecutar la demostración «leer, escribir y releer» y registrar si la política provisional clasifica la lectura como `ASK` (riesgo A-12): **no se amplían permisos desde el núcleo**; el desenlace se reporta a C.
  - **Archivos**: `tests/integration/test_loop_with_c_components.py`
  - **Estimación**: 30 min (adicionales, fuera del presupuesto)
  - **Dependencias**: HU-01-02 y HU-05-01 entregadas por C; T016
  - **Historia / actividad**: US3 / integración (fuera de Sp1-12/13/14)
  - **Criterios relacionados**: FR-008, FR-013, A-12, R-07
  - **Evidencia requerida**: salida de la prueba y nota de C sobre la semántica de `validate_args` en `docs/PROGRESO.md`
  - **Completada cuando**: C confirma la semántica y la demostración corre (o se documenta la denegación de la lectura sin ampliar permisos); hasta entonces permanece sin marcar.

---

## Dependencias y orden de ejecución

### Dependencias entre fases

- **Setup (T001)** → todo.
- **Fundacional (T002–T006)**: T002, T003 y T005 son paralelizables entre sí tras T001 (archivos distintos); T004 va después de T002 y T003 porque reexporta sus dobles en `tests/doubles/__init__.py` (archivo compartido, sin `[P]`); T006 depende de T005. Bloquea todas las historias.
- **US1 (T007–T012)**: T007 (ROJO) tras T002–T005; luego T008 → T009 → T010 → T011 → T012 (mismo archivo `loop.py`, secuencial).
- **US2 (T013–T014)** tras T012; T013 puede escribirse en paralelo con la implementación de US1 (archivo distinto) una vez existan los dobles y T005.
- **US3 (T015–T016)**: T015 puede escribirse en paralelo con US1/US2; T016 tras T011.
- **US4 (T017–T019)**: T017 tras T004 y T012; T018 tras T016/T017; T019 tras T018.
- **US5 (T020–T022)**: T020 tras los dobles y T005; T021 tras T009 y T020; T022 tras T021 y T012.
- **US6 (T023–T027)**: T023 tras los dobles y T005; T024 → T025 → T026 en secuencia; T027 tras T019 y T026.
- **Pulido (T028–T030)**: T028 puede hacerse tras T005; T029 tras todo el código; T030 último.

**Regla de evidencia**: ninguna tarea exige como prerrequisito evidencia que solo existe tras completar una tarea posterior; la evidencia de T010 y T011 sale de las pruebas mínimas de T007, y las pruebas completas de T013 y T015 (que solo dependen de T003–T005) se ejecutan al completarse esas tareas. Las pruebas en ROJO de T013 y T015 pueden escribirse antes de T010/T011, pero no es obligatorio.

Las tareas que editan `src/harness_agent/core/loop.py` **no son paralelizables entre sí** (un solo escritor); las pruebas (`tests/core/*`) y los dobles sí lo son entre archivos distintos.

### Oportunidades de paralelismo (sin comprometer contratos compartidos)

```text
Tras T001:   T002 [P]   T003 [P]   T005 [P]    (archivos distintos); después T004 (sin [P]: reexporta en tests/doubles/__init__.py)
Tras T004 y T005:   T007  ∥  T013  ∥  T015  ∥  T020  ∥  T023  ∥  T028 [P]   (pruebas en ROJO, archivos distintos)
Implementación: secuencial sobre loop.py (T006, T008–T012, T014, T016, T018, T019, T021, T022, T024–T027)
```

### Tareas desbloqueadas y bloqueadas

| Estado | Tareas | Motivo |
|---|---|---|
| **Desbloqueadas ahora (A, con dobles)** | T001–T030 | Dependen solo de contratos existentes y de dobles de prueba propios |
| **Bloqueadas por B** | T031 | Requiere `FakeProvider` (HU-00-03) y `EventBus` real con aislamiento de suscriptores (HU-01-05) |
| **Bloqueadas por C** | T032 | Requiere `ToolRegistry`/`validate_args` (HU-01-02) y `PermissionPolicy` (HU-05-01, Sp1-35) |

### Dependencias externas identificadas

| Integrante | Historia | Qué se usa | Cómo se desbloquea A |
|---|---|---|---|
| B | HU-00-03 `FakeProvider` | `Provider.complete`; ids de llamada no vacíos y únicos en toda la sesión (T031) | `ScriptedProvider` (T002) |
| B | HU-01-05 `EventBus` | `EventBus.emit` (síncrono) y aislamiento de suscriptores | `RecordingEventBus` + `FailingEventBus` (T004) |
| C | HU-01-02 `ToolRegistry` | `get`, `list`, `validate_args` | `InMemoryToolRegistry` (T003) |
| C | HU-05-01 `PermissionPolicy` (Sp1-35) | `evaluate` (síncrono); política provisional de `ASK` | `ScriptedPolicy` (T003) |

A no implementa ninguna de estas historias y no duplica la política provisional de `ASK` de C. Los dobles son pruebas con dobles; **no sustituyen la integración con las implementaciones reales** (T031, T032).

---

## Estrategia de implementación

- **MVP**: Fase 1 + Fase 2 + US1 + US2 (T001–T014) ⇒ **AC-01 y AC-02** verificables con dobles. Parar y validar (`pytest tests/core/test_loop_happy_path.py tests/core/test_loop_tool_errors.py`).
- **Entrega incremental**: US3 (seguridad y R-07) → US4 (eventos y Q4) → US5 (historial) → US6 (fallos, cancelación y R-08) → pulido. Cada historia es verificable de forma independiente con sus propias pruebas.
- **Un solo escritor** sobre `loop.py`; ningún trabajo en paralelo sobre ese archivo.

### Ejecución autónoma (`/speckit-implement` único)

- **Debe completar**: T001–T030, en el orden de las fases, con pruebas primero por tarea (ROJO registrado y luego VERDE) y la verificación indicada en cada tarea. Marcar `[X]` solo una tarea con evidencia observada.
- **Debe dejar sin ejecutar**: T031 y T032 (bloqueadas por B y C). No simular su resultado ni marcarlas.
- **Condiciones de parada** (detenerse y reportar, sin inventar decisiones): (1) una firma real difiere de la esperada (T001); (2) una prueba de seguridad (permisos, R-07, Q4) no puede pasar sin modificar un contrato compartido; (3) se detecta que cumplir una tarea exigiría implementar HU-00-03, HU-01-02, HU-01-05, HU-05-01, HU-01-06 o HU-01-07; (4) un mandato de ubicación resulta inequívocamente incompatible con `core/loop.py`; (5) `mypy`, `ruff` o `pytest` fallan por motivos ajenos a la historia (reportar sin tocar código ajeno); (6) se requiere una dependencia nueva.
- **No debe**: crear commits, hacer push, abrir PR, declarar HU-01-01 «Hecha» ni modificar AC-01/AC-02, la constitución o contratos compartidos.

---

## Matriz de cobertura (requisito → tareas)

| Requisito | Pruebas | Implementación |
|---|---|---|
| **AC-01** (literal) | T007 | T008–T012 |
| **AC-02** (literal) | T013 | T010, T014 |
| FR-001 | T020 | T009, T021 |
| FR-002 | T007 | T008 |
| FR-003 | T007 | T009, T010, T012 |
| FR-004 | T007 | T009 |
| FR-005 | T023 | T024, T025 |
| FR-006 | T020 | T005, T022 |
| FR-007 | T007, T020 | T009, T022 |
| FR-008 (R-07) | T015 | T010, T011 |
| FR-009 | T015 | T011, T016 |
| FR-010 | T013, T015 | T010 |
| FR-011 | T015 | T010 |
| FR-012 | T015 | T016 |
| FR-013 | T015 | T016 |
| FR-014 | T015 | T011, T016 |
| FR-015 | T007 | T010, T012 |
| FR-016 | T013 | T012 |
| FR-017 | T013 | T014 |
| FR-018 | T013 | T014 |
| FR-019 | T013, T015 | T010, T014, T016 |
| FR-020 | T020 | T021, T022 |
| FR-021 | T007, T020 | T012 |
| FR-022 | T013 | T012, T014 |
| FR-023 | T023 | T024 |
| FR-024 | T023 | T008, T024 |
| FR-025 | T020 | T005 |
| FR-026 (R-08) | T023 | T025, T026 |
| FR-027 | T001 | T005 |
| FR-028 | T028, T017 | T009 |
| FR-029 | T017 | T006, T018 |
| FR-030 | T017, T028 | T018 |
| FR-031 (Q4) | T017 | T019, T026, T027 |
| FR-032 | T028 | T005 |
| FR-033 | T001, T028 | T005 |
| FR-034 | T002–T004 | — |
| SC-001 | T007 | T012 |
| SC-002 | T015 | T016 |
| SC-003 | T013 | T014 |
| SC-004 | T017, T028 | T018 |
| SC-005 | T020 | T021, T022 |
| SC-006 | T017 | T018, T019, T027 |
| SC-007 | T028 | T005 |
| SC-008 | T020 | T005 |
| SC-009 | T023 | T024–T026 |
| SC-010 | T029 | T029 |
| R-07 | T015, T032 | T010, T011 |
| R-08 | T023 | T026 |
| Q3 (sin `APPROVAL_*`) | T015, T017, T028 | T016 |
| Q4 (`emit` propaga) | T017 | T019 |

**Riesgos residuales** (detalle en `plan.md`): D-01 y las aprobaciones de HU-00-01/HU-07-01 pendientes; sin tope de iteraciones (ejecución desatendida con proveedores reales no segura, R-04); la semántica de `validate_args` y la lectura de la demo bajo `ASK` dependen de C (R-05/R-07); el aislamiento de suscriptores depende de B (R-03); CI remota de la matriz 3.12 (T008 de la spec 002) pendiente; ratificación formal de R-07/R-08 pendiente si quien las comunicó no actúa como PO.
