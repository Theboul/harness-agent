# Plan: HU-05-05 y HU-10-01 — Registro de auditoría de decisiones y trazas estructuradas de cada llamada

**Spec**: [spec.md](spec.md) · Skills: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness`, `verificar-fronteras-hexagonales`.
**Contexto técnico**: Python 3.12, sin dependencias nuevas; núcleo solo biblioteca estándar; pruebas con `FakeProvider`, el bucle real, la cadena de políticas real y archivos SQLite reales en `tmp_path`.

## Decision Gates (arquitectura-hexagonal-clean)

| Gate | Resultado |
|---|---|
| ¿Regla de negocio nueva en `core/`? | **Sí**: `core/audit.py` (entrada de auditoría, preparación de argumentos, resolución, origen, `ArgumentsTap`, `AuditRecorder`, tabla de `/auditoria`, puerto `AuditLog`) y `core/tracing.py` (registro de traza, categorías, `TracingProvider`, `TracingRegistry`, aviso único, tabla de `/trazas`, puerto `TraceLog`). Puras: reloj, reloj monótono, redactor y avisos se inyectan. |
| ¿Puerto nuevo? | **Dos pequeños, fuera de `core/interfaces/`**: `AuditLog` y `TraceLog` (`Protocol` en sus módulos, como `MemoryLog` o `MessageLog`). No se cambia ningún puerto de `core/interfaces/`. |
| ¿Adaptador? | `adapters/storage/audit_store.py` (`SqliteAuditStore`) y `adapters/storage/trace_store.py` (`SqliteTraceStore`), sobre `store.connection()`, con el esquema v7 en `_schema.py`. |
| ¿Dónde se conecta? | Solo `bootstrap.py`: `ArgumentsTap` como política más externa, suscripción del `AuditRecorder` (después del registrador de eventos), `TracingProvider` y `TracingRegistry` para el bucle principal y para cada subagente (atados a su sesión), `Composition.audit`/`traces`, comandos `/auditoria` y `/trazas`. |
| ¿Evento? | Ninguno nuevo ni cambiado (D-01, D-08). |
| ¿Toca algo protegido? | **No** (`core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/`, `cli/`, `tests/doubles/`). |
| ¿Cómo se prueba? | Núcleo con registros en memoria y relojes falsos; almacenes con archivo SQLite real (migración, sin clave foránea, bytes del archivo); integración con `compose()` + `FakeProvider` + bucle real + cadena de políticas real + `run_session` + SQLite real. |

## Estructura (estructura-carpetas-harness)

| Archivo | Fila de la tabla que lo justifica |
|---|---|
| `src/harness_agent/core/audit.py` | Regla de negocio → módulo de `core/` (como `core/limits.py`); se exporta en `core/__init__.py` |
| `src/harness_agent/core/tracing.py` | Ídem |
| `src/harness_agent/adapters/storage/_schema.py` (cambio) | Código con `sqlite3` → `adapters/storage/`: versión 7, `_V7` |
| `src/harness_agent/adapters/storage/audit_store.py`, `trace_store.py` | Almacén → `adapters/storage/`; se exportan en su `__init__.py` |
| `src/harness_agent/config.py` (cambio) | Lectura de configuración → `config.py`: `[traces]`, `TraceSettings`, `HarnessConfig.traces` |
| `config.example.toml` (cambio) | Sección `[traces]` comentada |
| `src/harness_agent/bootstrap.py` (cambio) | Unir piezas → `bootstrap.py`: envoltura, suscriptores, envoltorios, comandos |
| `tests/unit/core/test_audit.py`, `test_tracing.py` | Equivalentes en `tests/` |
| `tests/unit/adapters/storage/test_schema_v7.py`, `test_audit_store.py`, `test_trace_store.py` | Equivalentes en `tests/` |
| `tests/contracts/test_sqlite_audit_log_contract.py`, `test_sqlite_trace_log_contract.py` | Contrato de cada puerto pequeño contra su implementación real |
| `tests/unit/test_config_traces.py`, `tests/unit/test_bootstrap_audit_traces.py` | Equivalentes en `tests/` |
| `tests/integration/test_audit_agent_loop.py`, `test_traces_agent_loop.py` | Integración con el bucle real |
| `tests/architecture/test_audit_boundaries.py`, `test_tracing_boundaries.py` | Guardas `ast` (plantilla de `verificar-fronteras-hexagonales`) |

## Diseño

1. **Auditoría en el núcleo (`core/audit.py`).** `AuditEntry` (sesión, llamada, herramienta, argumentos, decisión, resolución, motivo, acción, fuente, origen, `decided_at`, `resolved_at`), `AuditRow` (lectura: con `parent_id`), `AuditLog` (`record_decision`, `record_resolution`, `rows(session_id, limit)`, `count`). `prepare_arguments(arguments, redact)` → texto JSON ASCII redactado y acortado (D-04), nunca lanza. `ArgumentsTap(inner, redact)` es un `PermissionPolicy`: llama a `inner.evaluate(call)`, guarda `prepare_arguments` en un mapa acotado a 256 por `call.id` (un fallo guarda «sin dato») y devuelve la decisión de dentro; una excepción de dentro sube igual. `AuditRecorder(log, tap)` tiene `on_decided(event)` y `on_resolved(event)`: lee la carga con tolerancia (campos que faltan o con tipo raro = «sin dato»), toma los argumentos del mapa (`pop`), calcula la resolución (D-03) y el origen por prefijo (D-05) y **no captura** errores del almacén (D-06). `format_audit(rows, total, session_id)` da la tabla de `/auditoria`.
2. **Trazas en el núcleo (`core/tracing.py`).** `TraceRecord` (sesión, tipo, nombre, inicio, duración en ms, tokens de entrada y de salida o `None`, resultado, tamaño), `TraceLog` (`record`, `rows(session_id, limit)`, `count`). `TraceSink(log, warn)` guarda con captura de `Exception` y un único aviso fijo por ejecución (D-11). `TracingProvider(inner, sink, session, model, *, clock, monotonic, redact)` implementa `Provider.complete`: mide, delega, y en un `finally` (sin capturar `BaseException`) anota `ok`, el nombre de la clase del error o `cancelado` (D-10); tokens de `response.usage`. `TracingRegistry(inner, sink, session, *, clock, monotonic, redact)` implementa `ToolRegistry`: `get` devuelve una herramienta medida con el mismo nombre, descripción, esquema y riesgo; `register`, `list` y `validate_args` delegan. `format_traces(rows, total, session_id)` da la tabla de `/trazas` («sin dato» para los tokens nulos). Aquí se cumple **D-09**: el registro solo tiene esos campos de metadatos.
3. **Esquema v7 (`_V7`).** `auditoria(id AUTOINCREMENT, sesion_id, llamada_id, herramienta, argumentos, decision, resolucion, razon, accion, fuente, origen, decidida, resuelta)` con índice `(sesion_id, id)`; `trazas(id AUTOINCREMENT, sesion_id, tipo, nombre, inicio, duracion_ms, tokens_entrada, tokens_salida, resultado, tamano)` con índice `(sesion_id, id)`. **Sin `REFERENCES` y sin `CHECK` de valores** (D-07). Migra desde cualquier v1…v6 con la lógica existente (`_script`).
4. **`SqliteAuditStore(store)`**: `record_decision` (un `INSERT` y `commit`), `record_resolution` (`UPDATE` de la fila de mayor `id` de esa sesión y llamada; sin fila no hace nada), `rows(session_id, limit)` (últimas `limit` de la sesión y de sus hijas directas, en orden cronológico, con `LEFT JOIN sessions` para `parent_id`) y `count`. Errores del motor → `SessionStoreError` con texto fijo. **`SqliteTraceStore(store)`**: `record`, `rows`, `count` con la misma forma.
5. **`bootstrap.compose`** (siempre, sin interruptor): `tap = ArgumentsTap(policy, redactor.value)` y esa es la política de todo (bucle, subagentes, verificador, rutina); tras el registrador de eventos, `AuditRecorder` suscrito a `permission_decided` y `approval_resolved`. Con `config.traces.enabled`: el proveedor base se envuelve con `TracingProvider` atado a `cursor.value` para el bucle y el compactador, y el registro del bucle con `TracingRegistry`; en `run_child` se envuelven el proveedor base y la vista del registro con la sesión hija. `Composition.audit` y `Composition.traces` guardan los registros de lectura (el segundo es `None` con las trazas apagadas). `TracingProvider` expone `inner` para que las pruebas lo atraviesen.
6. **Comandos.** `/auditoria [id]` y `/trazas [id]` en `argument_commands` de `run_session` (`cli/` no cambia): `check_session_id` valida, sin id se usa `active.session_id`, la lectura nunca lanza (línea fija) y el texto sale de `format_audit` y `format_traces`.
7. **Config**: `[traces]` con `enabled`; `_TABLE_FIELDS["traces"] = ("enabled",)`; `_check_traces` valida el booleano sin repetir el valor; `HarnessConfig.traces: TraceSettings = TraceSettings()`.

## Dry run: pruebas existentes que cambian

Se aplicaron los cambios provisionales **reales** (esquema v7 con las dos tablas, `ArgumentsTap`, `AuditRecorder`, `TracingProvider`, `TracingRegistry`, los dos almacenes, `[traces]` y el cableado de `bootstrap.py` sobre el proveedor, el registro del bucle y la política) y se corrió la **suite completa** (`pytest --no-cov`, base de 9 366 pruebas pasadas, 48 omitidas, 4 deseleccionadas). Resultado: **60 fallaron** y se desglosan abajo; después se comprobó que las dos que sobraban no son del diseño y se revirtió todo (árbol limpio).

| Variante | Resultado |
|---|---|
| Trazas **encendidas** por defecto (la elegida, D-14) | **60 pruebas** cambian: 55 mecánicas (versión del esquema, conjunto de tablas, API pública de `adapters.storage`) y **5 de comportamiento** (el proveedor del bucle, o el del subagente, es ahora la envoltura de trazas; la quinta, de subagentes, apareció al implementar porque el dry run no envolvía al subagente). Ninguna de compactación, prefijo, permisos, verificación, reanudar ni de comandos (las de `/ayuda` comprueban con `in`, no con la lista exacta). |
| Trazas apagadas por defecto | Solo las 55 mecánicas; no hace falta: 4 queda por debajo del umbral de unas 5. |

La décima fila la **autorizó la persona usuaria durante la implementación** (T008) cuando falló al envolver al subagente. Las dos fallas restantes del dry run **no son del diseño**: `test_bootstrap_boundaries` falló porque el cableado provisional importaba un módulo que no es API pública (el real importará nombres públicos de `adapters.storage` y de `core`, sin cambiar esa guarda), y `TestTheRecorder::test_every_event_type_emitted_on_the_bus_is_saved` falló porque el suscriptor provisional no toleraba la carga vacía que esa prueba emite; con el suscriptor tolerante (D-06) pasó sin tocarla.

Pruebas existentes que cambian, **autorizadas por el usuario, pendientes de ratificar** (cada una se ejecuta antes de tocarla, para ver el rojo previsto):

| # | Prueba(s) existente(s) | Cuántas | Por qué cambian | Ajuste | Tarea |
|---|---|---|---|---|---|
| 1 | `tests/unit/adapters/storage/test_schema.py::test_schema_version_is_current` | 1 | `SCHEMA_VERSION` pasa de 6 a 7 | Esperar 7 | T004 |
| 2 | `test_schema_migration.py`: `test_schema_version_is_two`, `test_new_database_gets_the_criteria_tables`, `test_version_one_database_migrates_without_losing_data`, `test_unknown_versions_are_still_refused` | 4 | Versión y conjunto de tablas (7 y con `auditoria` y `trazas`); la «desconocida» pasa a ser la 8 | Esperar 7, añadir las dos tablas, usar 8 | T004 |
| 3 | `test_schema_v3.py`: `test_the_version_is_three` y las parametrizadas `…migrates_to_three…[1,2]`, `…changes_nothing[1,2]`, `…same_table_as_a_new_one[1,2]` | 7 | `user_version` y tablas esperadas | Esperar 7 y el conjunto con las tablas nuevas | T004 |
| 4 | `test_schema_v4.py`: `test_the_version_is_four` y las parametrizadas `[1-3]` de migrar, reabrir y mismas tablas | 10 | Ídem | Ídem | T004 |
| 5 | `test_schema_v5.py`: `test_the_version_is_five`, las parametrizadas `[1-4]` de migrar, reabrir y mismas tablas y `test_a_version_six_database_is_refused_without_being_modified` | 14 | Ídem; la «desconocida» de esa prueba es hoy la 7, que ya es la anterior a la actual | Ídem y que use la 8 | T004 |
| 6 | `test_schema_v6.py`: `test_the_version_is_six`, las parametrizadas `[1-5]` de migrar, reabrir y mismas tablas y `test_a_version_seven_database_is_refused_without_being_modified` | 17 | Ídem; la 7 deja de ser desconocida | Ídem y usar la 8 | T004 |
| 7 | `tests/integration/test_rejection_reason_agent_loop.py::test_the_reason_is_not_stored_in_the_database` | 1 | Compara el conjunto exacto de tablas | Añadir `auditoria` y `trazas` | T004 |
| 8 | `tests/unit/adapters/storage/test_public_api.py::test_all_lists_exactly_the_public_names` | 1 | Exporta `SqliteAuditStore` y `SqliteTraceStore` | Añadir los nombres | T005 |
| 9 | `tests/unit/test_bootstrap_failover.py`: `test_by_default_there_is_no_failover`, `test_the_wrapper_is_the_provider_of_the_loop_and_sits_outside_the_retries`, `test_when_no_alias_is_usable_there_is_no_wrapper_but_there_is_a_notice`; `tests/unit/test_bootstrap_retries.py::test_the_wrapper_is_the_provider_the_loop_uses` | 4 | El proveedor del bucle es `TracingProvider` (comprueban identidad o tipo del proveedor del bucle) | Atravesar la envoltura de trazas con su propiedad `inner` antes de comprobar | T008 |
| 10 | `tests/unit/test_bootstrap_subagents.py::test_the_loop_of_the_subagent_shares_provider_policy_and_bus_with_its_own_limits` | 1 | Comprueba que el hijo comparte el mismo objeto de proveedor que el bucle principal y que su registro es una `RegistryView`; ahora el hijo tiene su propio `TracingProvider` atado a su sesión y su registro es un `TracingRegistry` sobre la `RegistryView` (D-12) | Esperar el mismo `inner` y no el mismo objeto, y el `TracingRegistry` sobre la `RegistryView`; la política, el bus, los límites y el aprobador siguen iguales | T008 |

Total: **60** pruebas (11 archivos). Las pruebas de las filas 5 y 6 usan hoy la versión 7 como «desconocida» (así las dejó la spec 053) y pasan a la 8. Si al implementar falla cualquier otra prueba existente, se detiene el trabajo y se avisa. Los números de las parametrizadas son los índices de sus parámetros (cada uno cuenta como una prueba).

## Constitution Check

| Principio / regla | Resultado |
|---|---|
| Núcleo solo stdlib y `harness_agent.core`, sin E/S ni terminal; todo sale por el bus | Cumple: `audit.py` y `tracing.py` son puros (reloj, redactor, avisos y almacenes inyectados; la tabla es texto devuelto, no impreso). |
| V-02 falla cerrada | Cumple: la auditoría que no se puede escribir impide ejecutar la herramienta (D-06); los argumentos que no se pueden preparar se guardan como «sin dato», nunca en claro. Las trazas no son control de acceso: su fallo avisa y sigue (D-11). |
| V-13 redacción de secretos / sin secretos | Cumple: argumentos y nombres pasan por el `SecretRedactor` **antes** de escribirse; las trazas no guardan contenido; centinelas y claves se buscan en los bytes del archivo. |
| V-14 `FakeProvider` | Cumple: sin red ni claves. |
| Contratos protegidos | Intactos (ver FR-017). |
| Principio VI (sprint activo) | HU-05-05 es de Sprint 3 y HU-10-01 de Sprint 4; ambas dentro del reparto de Sprint 4 por ratificar (D-17). |

**Lista de comprobación de `capas-y-reglas.md`**

| Pregunta | Sí/No |
|---|---|
| ¿La regla de negocio está en `core/` y no en un adaptador? | Sí (qué se guarda, redacción, resolución, categorías, tablas); el adaptador solo escribe y lee filas |
| ¿Todo lo externo pasa por un puerto con tipos del dominio? | Sí (`AuditLog`, `TraceLog`, `Provider`, `ToolRegistry`, `PermissionPolicy`, `EventBus`) |
| ¿Puertos, entidades y eventos sin cambios? | Sí |
| ¿Los errores externos se traducen a errores de dominio sin reproducir valores? | Sí (`SessionStoreError` con texto fijo; el aviso de traza es fijo) |
| ¿Dependencias por constructor y conexión solo en `bootstrap.py`? | Sí |
| ¿El núcleo se probó con dobles, sin red, disco ni claves? | Sí |
| ¿Cada adaptador real tiene prueba de contrato en `tests/contracts/`? | Sí (`AuditLog` y `TraceLog` contra SQLite) |
| ¿Pasa `pytest tests/architecture` y las guardas nuevas en Windows y Linux? | Sí en Windows local; Linux en la CI remota (H02) |
| ¿El núcleo emite eventos en lugar de imprimir? | Sí (no imprime; devuelve texto y llama a funciones inyectadas) |
| ¿Lo público está exportado en `core/__init__.py`? | Sí |
| ¿Se respetan las decisiones de diseño (falla cerrada, historial intacto, secretos redactados)? | Sí; la excepción deliberada es que las trazas no fallan cerrado (D-11) |
| ¿Otro integrante revisó el cambio? | No todavía (H01) |

## Guardas de fronteras

`tests/architecture/test_audit_boundaries.py` y `test_tracing_boundaries.py` (plantilla de `verificar-fronteras-hexagonales`, cada regla con su prueba de mutación):
1. `core/audit.py` y `core/tracing.py`: solo stdlib y núcleo, sin E/S (ni `sqlite3`, `os`, `pathlib`, `time`), sin entorno ni terminal, sin importar `adapters`, `cli`, `config`, el bucle, `core.verification` ni `core.startup`.
2. `ArgumentsTap.evaluate` devuelve solo lo que devolvió la política de dentro (nunca nombra `PermissionDecision`) y no captura excepciones de ella.
3. `AuditRecorder` no tiene ningún `except` (un fallo del almacén sube: D-06) y solo lee los argumentos del mapa de la envoltura (no del evento).
4. `core/tracing.py`: las envolturas solo capturan `Exception` en el sumidero (nunca `BaseException`, un `except` desnudo ni `CancelledError`), el `finally` de la medición no lo hace, ningún manejador liga el error, no se lee `content`, `arguments` ni `tool_calls` fuera de `len(...)` del contenido y ningún campo de `TraceRecord` es texto libre.
5. `adapters/storage/audit_store.py` y `trace_store.py`: no abren conexión propia (usan `.connection()`), no importan el bucle ni `cli`; el DDL `_V7` no contiene `REFERENCES` ni `CHECK`.
6. `bootstrap.py`: la política que reciben el bucle, los subagentes, el verificador y la rutina es `ArgumentsTap` (se construye una sola vez y es la última asignación a `policy`), el `AuditRecorder` se suscribe **sin** condición de configuración y `TracingProvider`/`TracingRegistry` solo bajo `if config.traces.enabled`.

`adapters/storage/` ya está cubierta por `test_adapters_boundaries.py`; `bootstrap.py`, por `test_bootstrap_boundaries.py` (no cambia: solo importa API pública).

## Archivos protegidos (no tocar)

`core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/`, `core/startup/`, `core/in_memory_event_bus.py`, `tests/doubles/`, `docs/archivo/`, `cli/`.

## Mapeo a tareas del plan de sprints

Sp3-29 «Tabla de auditoría» (1,5 h) → T004, T005; Sp3-30 «Registrar decisiones y validar la redacción de argumentos» (2 h) → T002, T008, T010; Sp4-21 «Suscribir un registrador de trazas» (1,5 h) → T003, T008 (con envoltorios, D-08); Sp4-22 «Formato estructurado consultable» (2 h) → T004, T006; Sp4-23 «Comando o consulta para ver una traza» (1,5 h) → T009. T007 (configuración), T011 y T012 (cierre) no tienen tarea `Sp` propia.

## Hallazgos esperados

1. Los eventos no llevan argumentos (decisión vigente): la auditoría usa una envoltura de la política y depende de que cada `evaluate` vaya seguido de su evento sin `await` (D-15). Si A decide ampliar la carga de `permission_decided`, la envoltura se retira sin cambiar la tabla.
2. No hay evento de llamada al modelo con duración ni tokens: las trazas se miden con envoltorios y no por el bus (D-08); la tarea Sp4-21 del plan queda cumplida con otra técnica.
3. La auditoría falla cerrado y las trazas no (D-06, D-11): si B prefiere que ambas avisen y sigan, es un cambio de una línea en el suscriptor.
4. Sin retención ni purga (D-16); crecerán con el uso.
5. `verificacion-` y `arranque-` son hoy literales de `core/verification/` y `core/startup/`: el origen de la auditoría depende de ellos (D-05); una prueba lo vigila y, si cambian, el cambio es de A.
6. Los argumentos redactados siguen pudiendo incluir texto de la persona o fragmentos de archivos (acotados a 200 por valor); la redacción es heurística (HU-10-02).
7. La conmutación por fallo mueve el modelo activo: la traza lleva el modelo al terminar, no el del primer intento.
