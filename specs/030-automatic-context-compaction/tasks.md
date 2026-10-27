# Tasks: HU-02-03 — Compactación automática por umbral

**Input**: `specs/030-automatic-context-compaction/` (spec.md con Clarifications, plan.md, research.md R1–R18, data-model.md, contracts/ ×5, quickstart.md)
**Rama**: `gustavo` (sin commit, push ni cambio de rama por parte de Claude)
**Responsable**: B — Estado | **PHU**: 5 | **Sprint**: 2
**Tareas de referencia**: Sp2-14, Sp2-15, Sp2-16, Sp2-17

## Cómo leer este documento

- **Regla RITMO**: 5 PHU → 9 tareas de implementación de ≤ 40 min (T002–T010), agrupadas por módulo, más el inicio (T001), el cierre (T011) y las humanas (H1–H8). Si una tarea supera 40 min al ejecutarla, se parte; no se recorta alcance por el presupuesto del sprint. Con 5 PHU, `/speckit-analyze` va entre estas tareas y `/speckit-implement`.
- **TDD dentro de cada tarea**:
  1. escribir las pruebas;
  2. ejecutarlas y ver el **rojo por la razón esperada** (anotarlo en la evidencia);
  3. implementar lo mínimo;
  4. pasar `ruff format --check .`, `ruff check .`, `mypy src tests` y las pruebas del módulo con cobertura (100 % de líneas y ramas del módulo nuevo).
- **Formato**: `- [ ] Tnnn [USn] descripción con ruta`.
  - US1: se compacta solo al superar el umbral del modelo (FR-001 a FR-003, FR-019, FR-020).
  - US2: lo antiguo se resume con una llamada aparte y lo reciente queda íntegro (AC-01; FR-004 a FR-006, FR-012, FR-016, FR-017).
  - US3: el turno continúa con el contexto reducido y reconstruido (FR-007).
  - US4: el historial original sigue guardado y los eventos cubiertos quedan marcados (AC-02; FR-008 a FR-011).
  - US5: lo protegido y la seguridad no se debilitan (FR-013 a FR-015).
- **Decisiones añadidas al plan** (research R16 a R18): (R16) un fallo al publicar el evento **después** del `COMMIT` no es un fallo de compactación: no se deshace ni se reintenta, la vista compactada se mantiene, el turno continúa y se informa por el `warn` con texto fijo; (R17) el adaptador usa `store.connection()` y no abre otra conexión; (R18) pruebas de `[context.windows]` con claves entrecomilladas con `/` y `.`, valores inválidos por modelo y sin repetir el valor.
- **Lo que no se toca** (diff vacío al cerrar): `src/harness_agent/core/loop.py`, `core/interfaces/`, `core/events.py`, `core/in_memory_event_bus.py`, `core/redaction.py`, `core/permissions/`, `core/tasks/`, `core/verification/`, `adapters/tools/`, `cli/`, `tests/doubles/`, `docs/archivo/`. **Si algo lo exige, detente y avisa.**
- **Pruebas existentes que cambian** (y solo estas):
  - `tests/unit/adapters/storage/test_schema_migration.py`: las cuatro aserciones de versión (`SCHEMA_VERSION == 2` → 3, `user_version == 2` → 3 en dos sitios y la prueba de «versión desconocida», que pone `user_version = 3`, pasa a 4) (T006);
  - `tests/unit/adapters/storage/test_public_api.py`: solo el nombre nuevo `SqliteCompactionArchive` en la lista esperada (T007).
  - `tests/unit/adapters/storage/test_schema.py`: la aserción `SCHEMA_VERSION == 2` de `test_schema_version_is_current` pasa a 3 (T006; hallada por el análisis);
  - `tests/integration/test_rejection_reason_agent_loop.py`: el conjunto exacto de tablas (`{"sessions", "events", "criterios", "criterios_sello"}`, ~línea 296) gana `"resumenes"` (T006; hallada por el análisis).
  - Pruebas de configuración: ninguna prevista; si alguna fallara solo por añadir `context` a las tablas o a los campos, el único ajuste permitido es esa lista y se declara.
  - **Cualquier otra prueba existente que falle: detente y avisa con la razón antes de ajustarla.** En particular, si una prueba de `bootstrap` falla por el `skip` del registrador, es un hallazgo. El registrador se llama con `skip` de forma **posicional**, porque `tests/unit/test_bootstrap_compose.py` lo sustituye por `failing_recorder(*_args)` (no acepta nombres) y esa prueba no cambia.
- **Caracteres ocultos**: en `specs/` y `docs/` escribe `U+202E` y `U+200B` como texto. En código y pruebas se construyen con `chr(0x202E)`, `chr(0x200B)` y `chr(27)`, nunca con secuencias `\u...` en el texto que escribe la herramienta. El «U+200B» de los contratos es notación.
- **Finales de línea**: todo archivo de `specs/` y `docs/` en CRLF, con scripts que lean y escriban bytes; nunca `sed -i`.
- **Secretos**: ninguna asignación con forma de clave ni URL con credenciales literales; se arman por partes (`"https://" + "usuario" + ":" + "clave" + "@servidor.example/repo.git"`). Detector a mano sobre todos los archivos nuevos y modificados.
- **Sin red**: todo con `FakeProvider`; las bases de datos son archivos en `tmp_path`. `tests/spikes/compaction_sim.py` es código de pruebas: se puede **leer como modelo**, pero no se importa desde `src/` ni se copia a `src/`.

## Mapeo a tareas del sprint

| Tarea | Descripción (03-plan-sprints) | Presupuesto | Tareas aquí |
|---|---|---|---|
| **Sp2-14** | Disparar la compactación por umbral configurable por modelo | 180 min | T002 (40), T005 (parte) |
| **Sp2-15** | Resumir lo antiguo con una llamada aparte | 240 min | T004 (35), T005 (35), T005b (35) |
| **Sp2-16** | Reconstruir el contexto: resumen más mensajes recientes | 180 min | T003 (40), T008 (35), T009 (40) |
| **Sp2-17** | Marcar los eventos compactados sin borrarlos | 120 min | T006 (30), T007 (40) |
| — | Inicio, guardas/documentación y cierre | — | T001 (15), T010 (30), T011 (30) |

**Total de Claude: 405 min** (T001 15 + T002 40 + T003 40 + T004 35 + T005 35 + T005b 35 + T006 30 + T007 40 + T008 35 + T009 40 + T010 30 + T011 30) frente a 720 min presupuestados. **Humanas: H1–H8.**

---

## Phase 1: Inicio

- [x] T001 Inicio (15 min). Sin cambios de código:
  - **Línea base**: ejecutar las cuatro puertas y las guardas tal como están (`ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest --cov=harness_agent --cov-report=term-missing -q -rs` y `pytest tests/architecture -q`), todas en exit 0; anotar los conteos reales (pruebas pasadas y omitidas, número de archivos de `ruff` y `mypy`, pruebas de arquitectura) en la evidencia al final de este archivo. Si algo no está en verde, detente y avisa.
  - `docs/PROGRESO.md` (solo documentación; CRLF puro, un script que conserve los CRLF; deriva el de `prog029.py` del scratchpad cambiando el prefijo por `| [HU-02-03](04b-historias-estado.md#hu-02-03) |` y la cabecera por `**Observaciones de HU-02-03**:`): la fila **existente** de HU-02-03 pasa de `Pendiente` a `En curso` (responsable B; la implementa Claude en `gustavo`), una línea en *Registro de cambios* y un bloque **Observaciones de HU-02-03** con la spec 030 y las decisiones Q1 = A, Q2 = B, Q3 = A.
  - Comprobar que `.specify/feature.json` apunta a `specs/030-automatic-context-compaction`.

  **Hecho cuando**: la línea base está anotada y en verde, la fila está en `En curso` y `PROGRESO.md` sigue en CRLF puro con una sola fila existente modificada.

---

## Phase 2: Configuración y umbral (US1 · Sp2-14)

- [x] T002 [US1] `ContextSettings`, umbral por modelo y la sección `[context]` (40 min). Cubre FR-002, FR-020, SC-011 y R18. Archivos:
  - nuevo `src/harness_agent/core/context/settings.py`: `ContextSettings` (`@dataclass(frozen=True)`: `window_tokens=32_000`, `windows: tuple[tuple[str, int], ...] = ()`, `threshold_percent=80`, `recent_percent=30`, `min_recent_messages=4`, `summary_tokens=2_000`; `__post_init__` valida los rangos de `contracts/context_settings.md` y lanza `ContextConfigError` con mensaje fijo que **no repite el valor**), `window_for(model)`, `threshold_tokens(settings, model)`, `recent_budget_tokens(settings, model)` y `summary_cap_tokens(settings)` (`2 * summary_tokens`). Solo biblioteca estándar;
  - `src/harness_agent/core/context/__init__.py` y `src/harness_agent/core/__init__.py`: exportaciones;
  - `src/harness_agent/config.py`: `_check_context(table, present) -> ContextSettings` al estilo de `_check_limits` (los campos en el orden `window_tokens`, `windows`, `threshold_percent`, `recent_percent`, `min_recent_messages`, `summary_tokens`; un booleano no es un entero; los mensajes y nombres de campo exactos de la tabla del contrato; para `windows`, un único problema `context.windows` con el mensaje fijo si algo no es una tabla de nombre → entero válido), `_TABLE_FIELDS["context"]`, `HarnessConfig.context: ContextSettings = ContextSettings()` (campo nuevo **al final**, con valor por defecto) y `load_config` lo rellena;
  - `config.example.toml`: sección `[context]` **comentada** con los valores por defecto y un ejemplo de `[context.windows]`.

  Pruebas primero:
  - nuevo `tests/unit/core/context/test_settings.py`: la **tabla E2 exacta** del contrato (32000 → 25600 y 7680; `openai/gpt-4o` 128000 → 102400 y 30720; el mismo ajuste con `fake/test` → 25600 y 7680; `window_tokens=10000` y `threshold_percent=50` → 5000 y 1500); valores por defecto; `window_for` con modelo conocido y desconocido; cada campo fuera de rango, booleano o no entero → `ContextConfigError` cuyo texto no contiene el valor (centinela `VALOR-DE-PRUEBA-123`); inmutabilidad;
  - nuevo `tests/unit/test_config_context.py` (patrón de `config_support.py`): sin la sección rigen los valores por defecto; sección completa leída; **E1 del contrato** (`threshold_percent = 99` y `summary_tokens` con el centinela → los dos problemas en ese orden y ningún mensaje contiene `99` como valor recibido ni el centinela); `context` que no es una tabla; campo desconocido `context.otra`; **R18**: una clave entrecomillada con `/` y `.` como `"proveedor/modelo-1.5" = 128000` se acepta y `window_for("proveedor/modelo-1.5")` da 128000; valores inválidos **por modelo** (`0`, `-5`, `true` y un texto) → el problema `context.windows` con el mensaje fijo, sin el valor ni el nombre del modelo; el **límite conocido**: un nombre de modelo cuyo último fragmento parece una clave (por ejemplo terminado en `-key`) se rechaza como posible secreto; `config.example.toml` sigue cargando y, con la sección descomentada por la propia prueba, también.

  **Rojo esperado**: `ImportError` de `harness_agent.core.context.settings` y `AttributeError` de `HarnessConfig.context`. **Hecho cuando**: `settings.py` al 100 % de líneas y ramas; las suites existentes de configuración (`test_config_*.py`) pasan sin cambios; `tests/architecture/test_context_boundaries.py` y `test_core_reads_no_config.py` en verde.

---

## Phase 3: Los módulos puros (US2, US3, US5 · Sp2-15, Sp2-16)

- [x] T003 [US2] [US3] Partición del historial, ventana reciente y corte seguro (40 min). Cubre FR-005, FR-006, FR-007, FR-017 (parte) y SC-002. Archivos:
  - nuevo `src/harness_agent/core/context/cut.py`: `HistoryParts`, `split_history(history)`, `is_real(message)`, `choose_cut(history, region_start, budget_tokens, min_messages)` y `rebuild_history(history, region_start, cut, summary)` según `data-model.md` y `contracts/context_order.md`; puros y totales (nunca lanzan) y sin `raise`; la estimación de cada mensaje es `estimate_message` de HU-02-01; solo biblioteca estándar;
  - exportaciones en `core/context/__init__.py` y `core/__init__.py`.

  Pruebas primero:
  - nuevo `tests/unit/core/context/test_cut.py`: la **tabla exacta** de ejemplos E1 a E4 de `context_order.md` con el historial `H` (incluida la retirada de un resultado de herramienta hasta su llamada y el caso «nada antiguo» → `None`) y `rebuild_history` (mismos objetos, un solo resumen, cabeza intacta); `split_history` (sin petición → `None`; con varios `SYSTEM`; con resumen anterior justo después de la petición; un `USER` externo que **no** es el resumen no cuenta como petición); `is_real`; el mínimo de recientes y el presupuesto (un presupuesto grande alarga la ventana reciente y puede dejar `None`);
  - nuevo `tests/unit/core/context/test_cut_properties.py` (semilla fija **20261031**, solo `random`): 2 000 historiales válidos aleatorios (prefijo `SYSTEM`, petición, mensajes de asistente con una o varias llamadas y sus `TOOL` en cualquier orden de resultados, resumen opcional): `choose_cut` nunca lanza, es determinista, deja siempre al menos `min_messages` (o todos), **nunca** deja un `TOOL` sin su llamada del lado reciente y `rebuild_history` conserva los objetos del sufijo y de la cabeza.

  **Rojo esperado**: `ImportError` de `harness_agent.core.context.cut`. **Hecho cuando**: `cut.py` al 100 %; los ejemplos del contrato coinciden carácter a carácter (índices incluidos); si un ejemplo normativo no se pudiera cumplir tal como está escrito, detente y dime cuál y por qué.

- [x] T004 [US2] [US5] El prompt, la transcripción y el resumen enmarcado (35 min). Cubre FR-004, FR-005 (la entrada), FR-012, FR-013, FR-015 (parte) y SC-004, SC-005 (parte). Archivos:
  - nuevo `src/harness_agent/core/context/summary.py`: `summary_prompt`, `FRAME_HEADER`, `render_transcript`, `build_summary_request`, `clean_summary`, `check_summary`, `frame_summary`, `is_summary`, `summary_text` según `data-model.md` y `contracts/summary_prompt.md`; `clean_summary` oculta credenciales con `hide_url_credentials` (de `core/redaction.py`, sin cambiarlo); solo biblioteca estándar y núcleo;
  - `src/harness_agent/core/context/errors.py`: `SummaryRejected` (mensaje fijo que no repite el texto);
  - exportaciones en `core/context/__init__.py` y `core/__init__.py`.

  Pruebas primero, `tests/unit/core/context/test_summary.py`:
  - el **texto exacto del prompt** (con `summary_tokens = 2000`) y la petición: exactamente dos mensajes (`SYSTEM` con el prompt y `USER` con el cuerpo, con y sin resumen anterior); la función no recibe herramientas;
  - la **transcripción E1** exacta y las filas de la tabla (usuario, usuario externo, asistente con y sin llamadas —solo los nombres, nunca los argumentos: un `ToolCall` con un centinela en los argumentos no aparece—, resultado con y sin error, nombre de herramienta no encontrado → `herramienta`, corte a 2000 y 500 caracteres con `...`);
  - **E2**: el resumen con `chr(0x200B)` y una credencial de URL armada por partes sale limpio y con `<secreto oculto>`; `check_summary` rechaza no texto, vacío tras limpiar y por encima de `2 × summary_tokens` tokens estimados (16 000 caracteres con el valor por defecto) sin repetir el texto, y comprueba el tope sobre el texto **bruto antes de limpiarlo** (un texto de 1 MB se rechaza sin llegar a `hide_url_credentials`); **E3**: `frame_summary` exacto, `is_summary` y `summary_text`; un `USER` externo que no empieza por la cabecera no es resumen; un `SYSTEM` con la cabecera tampoco;
  - **azar** (semilla **20261031**): 1 000 textos hostiles (control, formato, `chr(0x202E)`, `chr(0x200B)`, URLs con credencial, saltos de línea): `clean_summary` nunca lanza, no deja caracteres `Cc`/`Cf`/`Cs`/`Co` salvo `\n`, ninguna credencial de prueba sobrevive y `is_summary(frame_summary(x))` siempre es verdadero.

  **Rojo esperado**: `ImportError` de `harness_agent.core.context.summary`. **Hecho cuando**: `summary.py` al 100 %; `core/redaction.py` sin diff.

---

## Phase 4: El orquestador (US1, US2, US3, US5 · Sp2-14, Sp2-15)

- [x] T005 [US1] [US2] [US3] `ContextCompactor`: núcleo y camino feliz (35 min). Cubre FR-001, FR-003, FR-004, FR-005, FR-006, FR-007, FR-016, FR-017 (una vez), FR-018, SC-001 y R4. Archivos:
  - nuevo `src/harness_agent/core/context/store.py`: `MessageEvent`, `CompactionCommit`, `CompactionReceipt` y el protocolo `CompactionStore` de `contracts/store_protocol.md` (sin importar `adapters/`); `errors.py`: `CompactionError`;
  - nuevo `src/harness_agent/core/context/compactor.py`: `ContextCompactor(provider, store, settings, *, model, definitions, emit, publish, warn, new_id)` con `async before_turn(history) -> CompactionResult | None` según `data-model.md`, `research.md` (R1, R4) y los contratos: estimación = `estimate_messages(history)` + `estimate_tool_definition` de cada definición; por debajo del umbral, nada; por encima, `split_history` → correspondencia de los mensajes reales con los eventos no cubiertos (orden y tipo: un `USER` real tiene siempre evento, un `ASSISTANT` solo si tiene contenido —el bucle publica `assistant_message` solo `if response.content`— y un `TOOL` siempre) con `through_seq` = seq del último mensaje con evento de la región antigua → `choose_cut` → petición sin herramientas → `check_summary` → `commit_compaction` → **sin ningún `await`** → reemplazo `history[:] = …` → `publish(receipt.event)`; como máximo una compactación por llamada. **En esta tarea todavía no se manejan los fallos** (las excepciones se propagan): lo hace T005b con sus pruebas en rojo primero;
  - exportaciones en `core/context/__init__.py` y `core/__init__.py`.

  Pruebas primero, `tests/unit/core/context/test_compactor.py` (almacén falso y `FakeProvider` de `tests/doubles/`; sin dobles nuevos):
  - por debajo del umbral, **0** llamadas y el historial no cambia; por encima, **una** llamada **sin herramientas** (`received_tools` es `None`) cuya entrada no contiene la cabeza protegida, la petición inicial ni los recientes; el historial queda en el orden `[SYSTEM…, petición, resumen externo, recientes]` con los mismos objetos; `commit_compaction` recibe `protected_seq` y `through_seq` del ejemplo E1 de `store_protocol.md`; `publish` recibe el evento del recibo;
  - idempotencia: el almacén devuelve `None` (o la región está vacía) → no se llama al proveedor y el historial no cambia; una segunda llamada de `before_turn` sin crecer no vuelve a compactar; **segunda compactación** con el resumen anterior como entrada y un solo resumen en el contexto (E4);
  - el umbral se **recalcula** si cambia el modelo devuelto por `model()` (el mismo historial compacta con la ventana pequeña y no con la grande);
  - la estimación incluye las definiciones de herramientas;
  - **E5** de `store_protocol.md`: un mensaje del asistente **sin contenido** (solo llamadas) no tiene evento y la correspondencia sigue siendo válida.

  **Rojo esperado**: `ImportError` de `harness_agent.core.context.compactor`. **Hecho cuando**: lo anterior en verde; `core/interfaces/` y `core/loop.py` sin diff.

- [x] T005b [US2] [US5] `ContextCompactor`: fallos, cancelación, R16 y advertencia (35 min). Cubre FR-011, FR-015, FR-017 (advertencia), SC-006 y R9, R16. Archivos: `src/harness_agent/core/context/compactor.py` (se completa) y `tests/unit/core/context/test_compactor_failures.py` (nuevo). Implementación, **después** de ver las pruebas en rojo: **solo** `except Exception` (nunca `BaseException`, nunca `CancelledError`); un fallo anterior al reemplazo de la vista publica `provider_error` con la carga fija de `compaction_events.md` (vía `emit`) y deja todo como estaba, y el turno continúa; un fallo de `publish` posterior al reemplazo **no** es un fallo de compactación: `warn` con el texto fijo de R16, sin `provider_error`; tras compactar, si la estimación sigue por encima del umbral, `warn` con el texto exacto del contrato y sin reintento.

  Pruebas primero:
  - fallos (cada uno: historial intacto, sin `commit` y `provider_error` con la carga fija y sin el texto de la excepción, con centinela en la excepción): error del proveedor, resumen vacío, resumen demasiado largo, el almacén lanza al guardar, correspondencia mensajes↔eventos que no coincide por tipo y por cuenta;
  - **cancelación**: `CancelledError` durante la llamada de resumen se propaga, no hay `commit` y el historial no cambia; también se propaga si ocurre en `publish`;
  - **R16**: un `publish` que lanza (con centinela) → el historial queda compactado, no hay `provider_error`, `warn` recibe el texto fijo y `before_turn` no lanza;
  - advertencia: si tras compactar sigue por encima del umbral, `warn` con el texto exacto de `compaction_events.md` y no hay segunda llamada;
  - **SC-006**: junto con los casos de T009, las pruebas de fallo suman **al menos 10** fallos simulados distintos (llamada, validación, correspondencia, guardado, cancelación y publicación).

  **Rojo esperado**: las pruebas de fallo fallan porque la excepción se propaga. **Hecho cuando**: `compactor.py` y `store.py` al 100 %; `core/interfaces/` y `core/loop.py` sin diff.

---

## Phase 5: El almacén (US4, US5 · Sp2-17)

- [x] T006 [US4] Esquema v3 y su migración desde 1 y 2 (30 min). Cubre FR-010 (esquema), SC-010 y R6. Archivos:
  - `src/harness_agent/adapters/storage/_schema.py`: `SCHEMA_VERSION = 3` y `_V3` con **solo** la tabla `resumenes` y su índice de `data-model.md` (`_STEPS = {1: _V1, 2: _V2, 3: _V3}`); `events` y `criterios*` no se tocan.

  Pruebas primero:
  - nuevo `tests/unit/adapters/storage/test_schema_v3.py`: bases **reales en `tmp_path` creadas con el esquema anterior** (el SQL literal de las versiones 1 y 2, como hace `test_schema_migration.py`) con datos (sesiones, eventos con y sin `compacted_by`, criterios y sello) → al abrirlas con `SqliteSessionStore` pasan a la versión 3, `resumenes` existe vacía y **todas las filas de todas las tablas anteriores son idénticas** a las de antes (volcado comparado); reabrir no cambia nada; una base nueva tiene la misma definición de `resumenes` que una migrada; las restricciones (`evento_hasta >= evento_desde`, texto no vacío, clave foránea de `sesion_id`) se cumplen;
  - **ajuste declarado** de `tests/unit/adapters/storage/test_schema_migration.py`: **solo** las cuatro aserciones de versión (2 → 3 en `SCHEMA_VERSION`, en las dos comprobaciones de `user_version` y la de «versión desconocida», que pasa a `user_version = 4`); ejecutar antes esas pruebas **sin tocarlas** y ver que fallan por la versión (esa es la razón del ajuste).
  - **ajustes declarados** (hallados por el análisis): `tests/unit/adapters/storage/test_schema.py` (`SCHEMA_VERSION == 2` → 3, una aserción) y `tests/integration/test_rejection_reason_agent_loop.py` (el conjunto exacto de tablas gana `"resumenes"`); ejecutarlas antes **sin tocarlas** y ver que fallan por la versión y por la tabla nueva.

  **Rojo esperado**: `resumenes` no existe y `SCHEMA_VERSION == 3` falla. **Hecho cuando**: toda la suite de `adapters/storage` en verde; ninguna otra prueba existente cambió.

- [x] T007 [US4] [US5] `SqliteCompactionArchive` y el parámetro `skip` del registrador (40 min). Cubre FR-008, FR-009, FR-010, FR-011, FR-015, AC-02, SC-003, SC-009 y R5, R17. Archivos:
  - nuevo `src/harness_agent/adapters/storage/compaction_archive.py`: `SqliteCompactionArchive(store: SqliteSessionStore, *, clock=…)` que implementa `CompactionStore` con las garantías de `contracts/store_protocol.md`: usa **`store.connection()`** y no abre otra conexión; `message_events`; `commit_compaction` en una transacción (`BEGIN IMMEDIATE`, selección de filas, `None` sin escribir si no hay ninguna, `INSERT` del resumen, `UPDATE` de **solo** `compacted_by`, `INSERT` del evento `context_compacted` con `seq = MAX(seq) + 1` y la carga `{"desde", "hasta", "eventos"}`, `COMMIT`; cualquier error → `ROLLBACK` y `SessionStoreError` con mensaje fijo, sin texto del resumen);
  - `src/harness_agent/adapters/storage/event_recorder.py`: `attach_event_recorder(bus, store, skip: Collection[EventType] = ())` (aditivo: sin `skip` se comporta igual; **posicional o por nombre**); `adapters/storage/__init__.py`: exportar `SqliteCompactionArchive`;
  - `tests/unit/adapters/storage/test_public_api.py`: **solo** el nombre nuevo en la lista esperada.

  Pruebas primero:
  - nuevo `tests/unit/adapters/storage/test_compaction_archive.py`, con un **archivo real** en `tmp_path` y eventos guardados con `save_event`: los ejemplos **E1 a E4** de `store_protocol.md` (rango 2 a 6, cinco eventos marcados, evento `{"desde": 2, "hasta": 6, "eventos": 5}` en el `seq` 11; idempotencia; segunda compactación sin el `context_compacted` ni el seq 1; rollback); **rollback** con fallos reales inyectados en cada uno de los tres pasos mediante disparadores SQL (`RAISE(ABORT)`) en `resumenes`, en la actualización de `events` y en la inserción de `context_compacted`: la base queda **idéntica**; `DuplicateEvent` si el `event_id` ya existe y nada parcial; **AC-02**: comparación de **todas las filas de `events` antes y después** (iguales salvo `compacted_by`) y `load_session` devuelve los mismos eventos más el de resumen; los eventos que no son de mensaje dentro del rango se marcan; `message_events` devuelve solo los tres tipos; el error del motor no contiene el texto del resumen (centinela);
  - **R17**: `sqlite3.connect` sustituido por una función que falla durante las operaciones del adaptador (no la llama); `save_event` antes y después de compactar en la misma base sin bloqueos; una segunda conexión de lectura lee el resultado tras el `COMMIT`;
  - **E5** de `store_protocol.md` con eventos reales: un asistente sin contenido no tiene evento, `message_events` devuelve solo `user`, `tool` y `assistant`, y con `through_seq = 4` se marcan los seq 2, 3 y 4 y no el 5;
  - nuevo `tests/unit/adapters/storage/test_event_recorder_skip.py`: por defecto sigue suscribiendo los 17 tipos; con `skip=(CONTEXT_COMPACTED,)` no guarda ese tipo y sí los demás; **duplicado**: con `skip` hay exactamente **una** fila de `context_compacted`; **sin `skip`** el segundo guardado falla con `DuplicateEvent`, que el bus en memoria entrega como `EventDeliveryError`, y sigue habiendo **una** sola fila.

  **Rojo esperado**: `ImportError` de `compaction_archive` y `TypeError` por `skip`. **Hecho cuando**: `compaction_archive.py` y `event_recorder.py` al 100 %; `core/interfaces/` sin diff (`SessionStore` no cambia).

---

## Phase 6: El cableado y la sesión larga (US1, US3, US4, US5 · Sp2-16)

- [x] T008 [US1] [US3] Cableado en `bootstrap.py` y la vista en memoria (35 min). Cubre FR-001, FR-002, FR-007, FR-019 y R11, R12. Archivos:
  - `src/harness_agent/bootstrap.py` (solo cableado; visto bueno de C en H2): crear `SqliteCompactionArchive(store)`; construir el `ContextCompactor` con el proveedor, el archivo, `config.context`, un `model` que devuelve `config.model`, las definiciones del registro (como las arma el bucle), un `emit` que fabrica el `Event` con el reloj y los identificadores inyectados (patrón de `_verifying_runner` de HU-11-04.1), `bus.emit` como `publish`, un `warn` que escribe una línea en la terminal y `new_id`; `attach_event_recorder(bus, store, (EventType.CONTEXT_COMPACTED,))` (**posicional**: ver la cabecera); `Composition.compactor` (con valor por defecto); `run_session` llama a `compactor.before_turn(history)` **antes de cada petición** y antes del verificador (la vista se reemplaza in situ). Sin tarea y con tarea funciona igual.

  Pruebas primero, nuevo `tests/unit/test_bootstrap_compaction.py` (patrón de `test_bootstrap_verification.py` y `bootstrap_support.py`): `compose()` entrega un `compactor` con `config.context`; por debajo del umbral una petición hace 0 llamadas de resumen; un contexto grande con una ventana pequeña en `[context]` compacta antes de la llamada del bucle (la petición que recibe el proveedor lleva prefijo, petición inicial, resumen externo y recientes); el `skip` funciona (un `context_compacted` emitido en el bus **no** se guarda dos veces); el aviso de `warn` llega a la salida de `run_session`; la vista compactada persiste entre las líneas de la sesión; si cambia el modelo del que lee el compactador el umbral se recalcula.

  **Rojo esperado**: `AttributeError` de `Composition.compactor`. **Hecho cuando**: todas las pruebas existentes de `bootstrap`, `cli` y `integration` pasan **sin cambios**; `tests/architecture/test_bootstrap_boundaries.py` en verde; `bootstrap.py` al 100 %.

- [x] T009 [US1] [US2] [US3] [US4] [US5] Sesión larga simulada, de punta a punta (40 min). Cubre AC-01, AC-02, FR-008, FR-011, FR-014, FR-015, FR-016, FR-018, SC-001 a SC-009, R13 y R16. Archivo nuevo `tests/integration/test_context_compaction_agent_loop.py` (`compose()` real con SQLite en `tmp_path`, `FakeProvider`; el generador de la sesión larga —mensajes con centinelas únicos y llamadas de herramienta con sus resultados— se escribe **dentro del archivo**, con el patrón de `build_long_session` del spike pero sin importarlo, e incluye mensajes del asistente **sin contenido** —solo llamadas a herramientas— además de los que tienen texto):
  - **AC-01**: una sesión larga supera el umbral; la petición siguiente dispara **una** llamada de resumen sin herramientas y el bucle recibe prefijo, petición inicial, resumen externo y los recientes **idénticos**; la entrada del resumen no contiene la cabeza protegida ni los recientes;
  - **AC-02**: los eventos guardados no bajan en número ni cambian de contenido (comparación de filas antes y después), los cubiertos llevan la marca y los demás no, hay una fila en `resumenes` y un `context_compacted` con `{desde, hasta, eventos}` sin texto; una **segunda** compactación usa el resumen anterior como entrada, deja un solo resumen en el contexto y su rango no solapa con el primero;
  - por debajo del umbral, nada: 0 llamadas y 0 filas nuevas;
  - **fallos** (nada parcial, el turno continúa y se publica el `provider_error` fijo sin texto): el proveedor falla, el resumen es vacío o enorme, el almacén falla (disparador SQL); **cancelación** (`CancelledError` en la llamada de resumen) propagada sin nada parcial;
  - **R16**: composición **sin `skip` a propósito** (un suscriptor que guarda `context_compacted` con `store.save_event`) → `DuplicateEvent` llega como `EventDeliveryError`: exactamente **una** fila de `context_compacted`, la vista compactada, el `warn` con el texto fijo y el turno que sigue;
  - **no filtración**: con centinelas en el historial, en el resumen que devuelve el proveedor simulado y en el texto de una excepción, y una credencial de URL armada por partes, ningún evento, `provider_error`, aviso ni fila de `events` los contiene; `resumenes.texto` **no** lleva la credencial;
  - **lo protegido**: con una tarea (`compose(task=…)`), los criterios en SQLite no cambian y su texto no entra a la llamada de resumen; el aviso de entorno y la petición inicial siguen idénticos;
  - ventana por modelo: el mismo historial compacta con una ventana pequeña configurada y no con la ventana grande; si tras compactar sigue sobre el umbral (prefijo enorme) hay advertencia y ninguna segunda llamada.

  **Rojo esperado**: retirando temporalmente el cableado de `bootstrap.py` (`git stash` solo de ese archivo, restaurándolo después) las pruebas de compactación fallan porque no se compacta nada; anota el número de fallos. **Hecho cuando**: todo en verde; `git stash list` conserva solo el `stash@{0}` de la spec 017; ninguna petición hace más de una llamada de resumen.

---

## Phase 7: Guardas, documentación y cierre

- [x] T010 Guardas de arquitectura y documentación (30 min). Archivos:
  - nuevo `tests/architecture/test_compaction_boundaries.py` (autoprueba con fragmentos sintéticos y mutación sobre una copia en `tmp_path`; reutiliza los detectores de las guardas existentes, no los copia): en `core/context/compactor.py` nunca se captura `BaseException`, un `except` desnudo ni `CancelledError` (`catches_cancellation`); la **única** llamada a `complete` del paquete va **sin herramientas** (un solo argumento); **entre la llamada a `commit_compaction` y el reemplazo de la vista no hay ningún `await`**; `cut.py` no tiene `raise`; ningún módulo de `core/context/` importa el bucle (`core.loop`), `adapters` ni `cli`; `adapters/storage/compaction_archive.py` no importa `core.loop`, no llama a `sqlite3.connect` (usa `.connection()`) y no define el puerto `SessionStore`; ningún módulo de `core/context/` importa `core.permissions` ni el puerto `TaskCriteria` (FR-014: la compactación no toca permisos ni criterios); `core/context/` sigue cubierto por `test_context_boundaries.py` sin cambios;
  - skills (dos copias idénticas, `.claude/skills/` y `.agents/skills/`): fila nueva en la tabla de `verificar-fronteras-hexagonales/SKILL.md`; `core/context/{settings,cut,summary,store,compactor}.py` y `adapters/storage/compaction_archive.py` en `estructura-carpetas-harness/references/arbol.md`;
  - `CLAUDE.md`: fila de HU-02-03 en «Qué existe hoy» y nota en las convenciones (la compactación corre en `run_session` antes de cada petición; la vista en memoria se reemplaza y el historial original no se toca; el ensamblador sigue sin cablear y la estimación es cruda; el evento `context_compacted` se guarda por el adaptador y el registrador lo omite);
  - revisar contra el código la lista de comprobación de `capas-y-reglas.md` de `plan.md` y anotar cualquier «no» (script que conserve CRLF);
  - **detector de secretos** a mano sobre todos los archivos nuevos y modificados (script con `secret_patterns_in` de `tests/architecture/test_no_secrets_in_repo.py`) y **caracteres ocultos y CRLF** en `specs/030-automatic-context-compaction/` y `docs/`.

  **Rojo esperado de la guarda**: la prueba de mutación (una copia del compactador con un `await` entre el `commit` y el reemplazo, con un `except BaseException`, o una copia del adaptador que llame a `sqlite3.connect`) la hace fallar. **Hecho cuando**: `pytest tests/architecture` en verde con la guarda nueva, las copias de las skills idénticas (`cmp`), el detector sin hallazgos y sin caracteres ocultos ni saltos de línea sueltos.

- [x] T011 Cierre (30 min). Depende de T010.
  - Ejecutar las cuatro puertas: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`, todas en exit 0; anotar los conteos reales respecto de la línea base de T001, el 100 % de líneas y ramas de `settings.py`, `cut.py`, `summary.py`, `store.py`, `compactor.py`, `compaction_archive.py`, `event_recorder.py` y `bootstrap.py`, y `pytest tests/architecture`.
  - Comprobar `git diff --exit-code $(git merge-base HEAD origin/main) -- <lo que no se toca, de arriba>` → 0, y revisar a mano que las únicas pruebas existentes modificadas son las dos de la lista de arriba.
  - Repetir el detector de secretos y la comprobación de caracteres ocultos y CRLF **después** de escribir `PROGRESO.md`.
  - En `docs/PROGRESO.md` (CRLF puro, **una fila** de HU-02-03 que pasa a **`En revisión`**, nunca `Hecha`; sin reescribir filas ajenas ni la tabla *Resumen*) con *Archivos* y *Evidencia* reales, una línea por tarea en *Registro de cambios* y, en la fila y en el bloque **Observaciones de HU-02-03**:
    1. las decisiones Q1 = A, Q2 = B y Q3 = A y R16 a R18; los dos ajustes de pruebas existentes;
    2. para **A y B**: el **ensamblador sigue sin cablear** y la estimación es **cruda, sin la calibración por sesión**; cuando se integre (HU-02-01, HU-02-06.1) debería pasar a `estimated_tokens`;
    3. para **A**: el **gancho futuro en el bucle** (opción B de Q1) cubriría el crecimiento dentro de una tarea larga; **limitación conocida** mientras tanto;
    4. para **A (HU-01-06)**: la llamada de resumen **no cuenta** en los límites de sesión; para **A (HU-03-04)**: las marcas, `resumenes` y el esquema 3 son la base para reconstruir al reanudar;
    5. para **B**: el **límite de nombres de modelo en `config.py`** (un nombre cuyo último fragmento parece una clave se rechaza como posible secreto);
    6. la correspondencia mensajes↔eventos por orden y tipo (falla cerrada si no coincide) y el valor por defecto de la ventana (32 000), el 80 %, el 30 % con mínimo 4 y unos 2 000 tokens a revisar por el PO;
    7. la nota de proceso con los rojos observados y los hallazgos;
    8. lo **pendiente** (H1–H8; SPK-03 con un modelo real no bloquea).
  - Marcar en este archivo solo T001–T011 con su evidencia (tabla al final), con un script que conserve los CRLF; H1–H8 quedan sin marcar.

  **Hecho cuando**: las cuatro puertas en verde, el diff de lo que no se toca vacío, el detector sin hallazgos, sin caracteres ocultos y `PROGRESO.md` en CRLF con una sola fila de HU-02-03 en `En revisión`.

---

## Phase 8: Tareas humanas (Claude no las marca)

- [ ] H1 **Acuerdo de A, B y C** sobre la carga del evento `context_compacted` (`{desde, hasta, eventos}`) y, como mejora futura, sobre el gancho de compactación en `core/loop.py` antes de cada llamada al modelo (A).
- [ ] H2 **Visto bueno de B** al esquema 3 de `adapters/storage/` y a `config.py`; **visto bueno de C** a `bootstrap.py`.
- [ ] H3 **Revisión cruzada** por A o C (la historia es de B).
- [ ] H4 El **PO revisa** los valores por defecto (ventana de 32 000 tokens, umbral del 80 %, ventana reciente del 30 % con mínimo 4 mensajes, resumen de unos 2 000 tokens), el tratamiento del resumen como contenido externo y que la llamada de resumen no cuente en los límites de sesión.
- [ ] H5 **Corrida de SPK-03 con un modelo real** cuando D-IA lo permita (calidad del resumen; no bloquea esta historia).
- [ ] H6 **CI remota** en verde en `ubuntu-latest` y `windows-latest`, con push y PR confirmados por una persona.
- [ ] H7 **Aviso a A**: (HU-01-06) la llamada de resumen no cuenta en los límites de sesión; (HU-03-04) las marcas, `resumenes` y el esquema 3 son la base para reconstruir al reanudar.
- [ ] H8 **Aviso a A y a B** (HU-02-01, HU-02-06.1): el ensamblador sigue sin cablear y la estimación de esta historia es cruda; debería pasar a la calibrada cuando se integre.

---

## Dependencias y orden

```text
T001 ─▶ T002 ─▶ T003 ─▶ T004 ─▶ T005 ─▶ T006 ─▶ T007 ─▶ T008 ─▶ T009 ─▶ T010 ─▶ T011 ─▶ (H1–H8)
```

- Es una cadena porque cada tarea añade exportaciones a `core/context/__init__.py` y `core/__init__.py` y la siguiente usa lo anterior. T006 (esquema) no depende de T003–T005 y podría adelantarse, pero no compensa.
- **US1** (umbral): T002, T005, T008, T009. **US2** (resumen con llamada aparte): T003, T004, T005, T009. **US3** (contexto reconstruido): T003, T005, T008, T009. **US4** (historial conservado): T006, T007, T009. **US5** (seguridad): T004, T005, T007, T009, T010.

## Estrategia de implementación

1. **MVP**: T001–T005. El orquestador ya decide, resume, compone y falla de forma segura (probado con falsos).
2. **Incremento**: T006 y T007 (el almacén atómico), T008 (el cableado) y T009 (de punta a punta).
3. **Cierre**: T010 y T011. Después, H1–H8 son humanas y la historia no pasa a `Hecha` hasta completarlas y ratificar HU-00-01.

---

## Evidencia

Resultados reales (2026-10-27). Línea base de T001: 6422 pasadas y 47 omitidas, 489 pruebas de arquitectura, ruff y mypy limpios (350 archivos).

| Tarea | Rojo observado | Resultado |
|---|---|---|
| T001 | — (sin cambios) | Línea base anotada; la fila de HU-02-03 pasa a `En curso` |
| T002 | `ImportError` de `ContextSettings` | `settings.py` al 100 %; suite 6496 pasadas |
| T003 | `ImportError` de `HistoryParts` y `choose_cut` | `cut.py` al 100 %; ejemplos E1-E4 y 2 000 historiales al azar (semilla 20261031) |
| T004 | `ImportError` de `SummaryRejected` | `summary.py` al 100 % |
| T005 | `ImportError` de `ContextCompactor` | Camino feliz; 3 fallos iniciales por el tamaño de mis datos de prueba, corregidos en las pruebas |
| T005b | Las excepciones se propagaban, sin aviso (primero fallaba por un guion vacío del doble, corregido) | `compactor.py` y `store.py` al 100 %; 15 fallos distintos, cancelación, R16 y advertencia |
| T006 | `no such table: resumenes`; las seis pruebas existentes de la lista fallan por la versión y la tabla nueva | Ajustes autorizados aplicados: `test_schema.py` (1), `test_schema_migration.py` (4), `test_rejection_reason_agent_loop.py` (1) |
| T007 | `ImportError` de `SqliteCompactionArchive` | `compaction_archive.py` y `event_recorder.py` al 100 %; rollback con disparadores SQL; `test_public_api.py` (nombre nuevo) |
| T008 | `AttributeError` de `Composition.compactor`; luego `test_every_event_type_emitted_on_the_bus_is_saved` fallaba por el `skip` | Ajuste de una línea autorizado por el usuario; `bootstrap.py` al 100 %; D4: los conversores aceptan el historial compactado |
| T009 | Sin el cableado (`bootstrap.py` de `HEAD`) fallan las 14 pruebas de integración (`AttributeError` de `warning_sink`) | 14 pruebas en verde con el cableado; `git stash list` conserva solo el `stash@{0}` de la spec 017 |
| T010 | Cada regla de `test_compaction_boundaries.py` falla sobre su copia mutada | 21 pruebas; copias de las skills idénticas (`cmp`); detector de secretos, caracteres ocultos y CRLF sin hallazgos |
| T011 | — | `ruff format --check .` y `ruff check .` en exit 0; `mypy src tests` sin errores (371 archivos); `pytest --cov=harness_agent --cov-branch` en exit 0: 6722 pasadas y 47 omitidas; 510 de arquitectura; 100 % de líneas y ramas de `settings.py`, `cut.py`, `summary.py`, `store.py`, `compactor.py`, `compaction_archive.py`, `event_recorder.py` y `bootstrap.py`; `git diff --exit-code` de lo protegido vacío; `PROGRESO.md` con una sola fila de HU-02-03 en `En revisión` |

Pruebas existentes modificadas, **autorizadas por el usuario y pendientes de ratificar**: `tests/unit/adapters/storage/test_schema.py` (una aserción), `test_schema_migration.py` (cuatro aserciones), `tests/integration/test_rejection_reason_agent_loop.py` (el conjunto de tablas), `tests/unit/adapters/storage/test_public_api.py` (el nombre nuevo) y `tests/unit/test_bootstrap_compose.py` (una línea, con un comentario con la razón).

Pendientes humanos: H1-H8, sin marcar.
