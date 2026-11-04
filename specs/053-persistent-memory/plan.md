# Plan: HU-04-01 y HU-04-02 — Memoria persistente separada del historial, con herramienta y carga al inicio

**Spec**: [spec.md](spec.md) · Skills: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness`, `verificar-fronteras-hexagonales`.
**Contexto técnico**: Python 3.12, sin dependencias nuevas; núcleo solo biblioteca estándar; pruebas con `FakeProvider`, el bucle real, la cadena de políticas real y archivos SQLite reales en `tmp_path`.

## Decision Gates (arquitectura-hexagonal-clean)

| Gate | Resultado |
|---|---|
| ¿Regla de negocio nueva en `core/`? | **Sí**: `core/context/memory.py` (ajustes `MemorySettings`, limpieza y topes de una entrada, selección por recencia dentro del presupuesto, texto y reconocimiento del bloque, puerto `MemoryLog`) y `core/context/memory_loader.py` (la carga). Puras, sin E/S. Dos errores nuevos en `core/context/errors.py`. |
| ¿Puerto nuevo? | **Uno pequeño, fuera de `core/interfaces/`**: `MemoryLog` (`Protocol` de `core/context/`, como `EssentialSource` y `MessageLog`). El puerto `MemoryStore` de HU-00-01 **no cambia** y `SqliteMemoryStore` lo implementa también (D-01). Sin cambios en `core/interfaces/`. |
| ¿Adaptador? | `adapters/storage/memory_store.py` (`SqliteMemoryStore`, sobre `store.connection()`) con el esquema v6 en `_schema.py`; `adapters/tools/memoria.py` (`MemoryTool`). |
| ¿Dónde se conecta? | Solo `bootstrap.py` y solo con `[memory] enabled`: registra la herramienta, la oculta a los subagentes (`RegistryView`), crea el `MemoryLoader` y lo llama al abrir `run_session` y en `/nueva`. |
| ¿Evento? | Ninguno nuevo (D-17): el catálogo no se toca; la carga se ve por el `WarningSink`. |
| ¿Toca algo protegido? | **No** (`core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/`, `tests/doubles/`). Sí `core/context/cut.py` (HU-02-03, de B): `split_history` salta el bloque de memoria (D-09); no está en la lista de archivos protegidos de `CLAUDE.md` pero se dice aquí y en H04. |
| ¿Cómo se prueba? | Núcleo con tablas y dobles simples; almacén con archivo SQLite real (migraciones, sin clave foránea, borrar y compactar una sesión); herramienta con un `MemoryLog` en memoria; integración con `compose()` + `FakeProvider` + bucle real + cadena de políticas real + `run_session` + SQLite real. |

## Estructura (estructura-carpetas-harness)

| Archivo | Fila de la tabla que lo justifica |
|---|---|
| `src/harness_agent/core/context/memory.py` | Regla de negocio → subpaquete de `core/` (`core/context/`); se exporta en `core/context/__init__.py` y `core/__init__.py` |
| `src/harness_agent/core/context/memory_loader.py` | Ídem (la carga con sus avisos) |
| `src/harness_agent/core/context/errors.py` (cambio) | Error de dominio → `errors.py` del subpaquete que lo lanza: `MemoryEntryInvalid`, `MemoryFull` |
| `src/harness_agent/core/context/cut.py` (cambio de una condición) | Regla de compactación (HU-02-03): `split_history` reconoce el bloque de memoria como cabeza |
| `src/harness_agent/adapters/storage/_schema.py` (cambio) | Código con `sqlite3` → `adapters/storage/`: versión 6, tabla `memorias` |
| `src/harness_agent/adapters/storage/memory_store.py` | Almacén → `adapters/storage/`; se exporta en su `__init__.py` |
| `src/harness_agent/adapters/tools/memoria.py` | Herramienta nativa → `adapters/tools/`; se exporta en su `__init__.py` |
| `src/harness_agent/config.py` (cambio) | Lectura de configuración → `config.py`: `[memory]`, `HarnessConfig.memory` |
| `config.example.toml` (cambio) | Sección `[memory]` comentada |
| `src/harness_agent/bootstrap.py` (cambio) | Unir piezas → `bootstrap.py`: herramienta, vista del registro, cargador, `Composition.memory` |
| `tests/unit/core/context/test_memory.py`, `test_memory_loader.py`, `test_cut_memory_block.py` | Equivalentes en `tests/` |
| `tests/unit/adapters/storage/test_schema_v6.py`, `test_memory_store.py` | Equivalentes en `tests/` |
| `tests/contracts/test_sqlite_memory_store_contract.py` | Contrato del puerto `MemoryStore` contra la implementación real (el doble ya tiene el suyo en `test_contracts.py`, que no se toca) |
| `tests/unit/adapters/tools/test_memoria.py` | Equivalente en `tests/` |
| `tests/unit/test_config_memory.py`, `tests/unit/test_bootstrap_memory.py` | Equivalentes en `tests/` |
| `tests/integration/test_persistent_memory_agent_loop.py` | Integración con el bucle real |
| `tests/architecture/test_memory_boundaries.py` | Guarda `ast` (plantilla de `verificar-fronteras-hexagonales`) |

## Diseño

1. **`MemorySettings(enabled=False, budget_tokens=2000, max_entries=200, max_content_chars=500)`**: `dataclass(frozen=True, slots=True)` que valida sus rangos (400–8 000, 1–1 000, 50–2 000) y lanza `ContextConfigError` con un texto fijo; `MEMORY_FIELD_RANGES` lo comparte con `config.py`.
2. **Limpieza (`make_entry`)**: `clean_key` (minúsculas, 1–60, `[a-z0-9._-]`), `flatten` (quita las categorías `Cc`, `Cf`, `Cs`, `Co`, `Cn`, colapsa espacios y saltos), `redact` inyectado (el `SecretRedactor` de la composición; por defecto `hide_url_credentials`), tope en caracteres sin truncar. Devuelve `CleanEntry(key, content, redacted)`.
3. **Bloque (`build_block`)**: `items` más recientes primero; para `k = 1…n` arma el texto con las `k` primeras y el aviso de omisión de las `n − k` restantes y se queda con el mayor `k` cuyo `estimate_message(Message(USER, texto, is_external=True))` cabe; para en la primera que no cabe. Sin entradas: `MemoryBlock(None, 0, 0)`. Formato: marca, aviso fijo, [aviso de omisión], una línea `- clave (AAAA-MM-DD): texto` por entrada.
4. **Reconocimiento**: `is_memory_block` (`USER` + `is_external` + marca al principio, sola o seguida de salto de línea) y `find_memory_block`, que **solo** mira justo después del prefijo `SYSTEM` (un mensaje que imita la marca en otra parte no cuenta). `place_memory_block` inserta una vez, en sitio, y no hace nada si ya está.
5. **`memory_budget`**: `min(settings.budget_tokens, umbral(modelo activo) × 20 %)` con `threshold_tokens` de HU-02-03.
6. **`MemoryLoader.load_into(history)`**: lee `recent()` (un fallo = aviso fijo, sin bloque), calcula el presupuesto con el modelo activo (`model: Callable[[], str]`), construye, coloca y, si colocó y hubo omitidas, avisa con cifras (`warn`).
7. **`cut.split_history`**: tras saltar el prefijo `SYSTEM`, si el mensaje siguiente es el bloque de memoria se salta también; el resto no cambia (`head_end`, resumen y `region_start` se calculan igual; `rebuild_history` ya conserva `history[:region_start]`).
8. **Esquema v6** (`_V6`): `memorias(id AUTOINCREMENT, clave UNIQUE, contenido, creada, actualizada)` y `idx_memorias_actualizada`; **sin `REFERENCES`**. Migra desde cualquier v1…v5 con la lógica existente (`_script`).
9. **`SqliteMemoryStore(store, *, max_entries, clock)`**: `remember` (una transacción `BEGIN IMMEDIATE`: actualiza si existe, si no cuenta y rechaza con `MemoryFull` si está llena, si no inserta), `forget`, `recent` (`ORDER BY actualizada DESC, id DESC`; fila ilegible = `SessionStoreError` fijo) y los nombres del puerto de HU-00-01 (`save`, `search`, `delete`). Errores del motor → `SessionStoreError` con texto fijo.
10. **`MemoryTool(log, settings, redact)`**: `memoria {accion: guardar|olvidar, clave, texto?}`, riesgo `HIGH`, `maxLength` del texto = `max_content_chars`; `guardar` = `make_entry` → `remember`; `olvidar` = `clean_key` → `forget`; errores etiquetados `[memoria_invalida]`, `[memoria_llena]`, `[accion_invalida]`, `[memoria_error]` con texto fijo; el resultado nunca repite el texto.
11. **`bootstrap.compose`**: con `config.memory.enabled`, crea `SqliteMemoryStore(store, max_entries=…, clock)`, registra `MemoryTool(log, config.memory, redactor)`, añade `MEMORY_TOOL_NAME` a lo que oculta el `RegistryView` de los subagentes y crea el `MemoryLoader(log, config.memory, config.context, model=lambda: switch.model, warn=warning_sink.write)`; `Composition.memory`. **`run_session`**: `memory.load_into(history)` tras crear el historial y antes de `capture.bind`; **`/nueva`**: tras `history[:] = prefix`. **No** en `/reanudar`.
12. **Config**: `[memory]` con `enabled`, `budget_tokens`, `max_entries`, `max_content_chars`; `_check_memory` valida contra `MEMORY_FIELD_RANGES`; `_TABLE_FIELDS` rechaza campos desconocidos.

## Dry run: pruebas existentes que cambian

Se aplicaron los cambios provisionales **reales** (`core/context/memory.py`, `memory_loader.py`, errores, `cut.py`, esquema v6, `memory_store.py`, `memoria.py`, los `__init__`, `config.py`, `config.example.toml` y el cableado de `bootstrap.py`), se comprobó con un guion de humo (SQLite real en `tmp_path`: guardar, tope, reemplazo, secreto oculto, carga con omisión, idempotencia, `split_history`, sin clave foránea) y se corrió la **suite completa dos veces** (`pytest --no-cov`, base de 9 127 pruebas pasadas, 48 omitidas, 4 deseleccionadas). Luego se revirtió todo (árbol limpio).

| Variante | Resultado |
|---|---|
| `[memory] enabled` **activa** por defecto | 69 pruebas fallan: las 39 de abajo y **30 de comportamiento más** (compactación de integración 11, reanudar 8, esencial 2, subagentes 1, `bootstrap` de compactación 5, `bootstrap` de herramientas 1, descubrimiento MCP 1, conmutación 1): la declaración de `memoria` suma tokens a cada petición. |
| `[memory] enabled` **apagada** por defecto (la elegida, D-14) | **39 pruebas fallan, todas mecánicas** (versión de esquema, conjunto de tablas, API pública); ninguna de compactación, prefijo, `compose`, configuración ni arquitectura. |

Con la memoria apagada no se movió ninguna prueba de compactación ni de prefijo: el cambio de `split_history` no altera ninguna historia sin bloque de memoria. `test_core_public_api` y `test_bootstrap_boundaries` (bootstrap importa solo API pública de `adapters.storage` y `adapters.tools`) **no** cambian.

Pruebas existentes que cambian, **autorizadas por el usuario, pendientes de ratificar** (cada una se ejecuta antes de tocarla, para ver el rojo previsto):

| # | Prueba(s) existente(s) | Cuántas | Por qué cambian | Ajuste | Tarea |
|---|---|---|---|---|---|
| 1 | `tests/unit/adapters/storage/test_schema.py::test_schema_version_is_current` | 1 | `SCHEMA_VERSION` pasa de 5 a 6 | Esperar 6 | T004 |
| 2 | `tests/unit/adapters/storage/test_schema_migration.py`: `test_schema_version_is_two`, `test_new_database_gets_the_criteria_tables`, `test_version_one_database_migrates_without_losing_data`, `test_unknown_versions_are_still_refused` | 4 | Versión y conjunto de tablas esperados (ahora 6 y con `memorias`); la «versión desconocida» pasa a ser la 7 | Esperar 6, añadir `memorias`, usar 7 | T004 |
| 3 | `tests/unit/adapters/storage/test_schema_v3.py`: `test_the_version_is_three` y las parametrizadas `test_an_old_database_migrates_to_three_and_keeps_every_row[1,2]`, `test_reopening_a_migrated_database_changes_nothing[1,2]`, `test_a_migrated_database_has_the_same_table_as_a_new_one[1,2]` | 7 | `user_version` y tablas esperadas | Esperar 6 y el conjunto de tablas con `memorias` | T004 |
| 4 | `tests/unit/adapters/storage/test_schema_v4.py`: `test_the_version_is_four` y las parametrizadas `…migrates_to_four…[1-3]`, `…changes_nothing[1-3]`, `…same_tables_as_a_new_one[1-3]` | 10 | Ídem | Ídem | T004 |
| 5 | `tests/unit/adapters/storage/test_schema_v5.py`: `test_the_version_is_five`, las parametrizadas `…migrates_to_five…[1-4]`, `…changes_nothing[1-4]`, `…same_tables_as_a_new_one[1-4]` y `test_a_version_six_database_is_refused_without_being_modified` | 14 | Ídem; la versión 6 ya es la actual, así que la «desconocida» de esa prueba es la 7 | Ídem y usar 7 | T004 |
| 6 | `tests/integration/test_rejection_reason_agent_loop.py::test_the_reason_is_not_stored_in_the_database` | 1 | Compara el conjunto exacto de tablas de la base | Añadir `memorias` | T004 |
| 7 | `tests/unit/adapters/storage/test_public_api.py::test_all_lists_exactly_the_public_names` | 1 | Exporta `SqliteMemoryStore` | Añadir el nombre | T005 |
| 8 | `tests/unit/adapters/tools/test_public_api.py::test_tools_expose_the_tools_and_the_limits` | 1 | Exporta `MemoryTool` | Añadir el nombre | T006 |

Total: **39** pruebas (8 archivos). Si al implementar falla cualquier otra prueba existente, se detiene el trabajo y se avisa. Los números de las pruebas parametrizadas son los índices de sus parámetros (cada uno cuenta como una prueba).

## Constitution Check

| Principio / regla | Resultado |
|---|---|
| Núcleo solo stdlib y `harness_agent.core`, sin E/S ni terminal; todo sale por el bus | Cumple: `memory.py` y `memory_loader.py` son puros; el aviso sale por el `warn` inyectado y la base la toca solo el adaptador. |
| V-02 falla cerrada | Cumple: la herramienta pregunta siempre y se deniega en solo lectura, sin aprobador y en subagentes; un error del almacén es un resultado fijo; lo ilegible se omite; el bloque solo añade datos. |
| V-13 redacción de secretos / sin secretos | Cumple: se redacta **antes** de escribir y el resultado, los avisos y el evento no repiten texto ni clave. |
| V-14 `FakeProvider` | Cumple: sin red ni claves. |
| Contratos protegidos (`core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/`, `tests/doubles/`) | Intactos. |
| `core/context/cut.py` (HU-02-03) | Cambia **una condición** de `split_history`, con prueba; sin él la compactación se desactivaría con el bloque puesto (D-09). Para B (H04). |

**Lista de comprobación de `capas-y-reglas.md`**

| Pregunta | Sí/No |
|---|---|
| ¿La regla de negocio está en `core/` y no en un adaptador? | Sí (topes, limpieza, selección, bloque); el adaptador solo guarda y cuenta las filas dentro de la misma transacción |
| ¿Todo lo externo pasa por un puerto con tipos del dominio? | Sí (`MemoryLog` y `MemoryStore`; `MemoryItem` del dominio) |
| ¿Puertos, entidades y eventos sin cambios? | Sí |
| ¿Los errores externos se traducen a errores de dominio sin reproducir valores? | Sí (`SessionStoreError`, `MemoryFull`, `MemoryEntryInvalid` con texto fijo) |
| ¿Dependencias por constructor y conexión solo en `bootstrap.py`? | Sí |
| ¿El núcleo se probó con dobles, sin red, disco ni claves? | Sí |
| ¿El adaptador real tiene prueba de contrato en `tests/contracts/`? | Sí (`MemoryStore` contra `SqliteMemoryStore`) |
| ¿Pasa `pytest tests/architecture` y la guarda nueva en Windows y Linux? | Sí en Windows local; Linux en la CI remota (H02) |
| ¿El núcleo emite eventos en lugar de imprimir? | Sí (no imprime; el aviso es una función inyectada) |
| ¿Lo público está exportado en `core/__init__.py`? | Sí |
| ¿Se respetan las decisiones de diseño (falla cerrada, historial intacto, secretos redactados)? | Sí |
| ¿Otro integrante revisó el cambio? | No todavía (H01) |

## Guarda de fronteras

`tests/architecture/test_memory_boundaries.py` (plantilla de `verificar-fronteras-hexagonales`, cada regla con su prueba de mutación):
1. `core/context/memory.py` y `memory_loader.py`: solo stdlib y núcleo, sin E/S (ni `sqlite3`, `os`, `pathlib`), sin entorno ni terminal, sin importar `adapters`, `cli`, `config`, el bucle ni `core.permissions`.
2. `memory.py` construye `Message` en un solo sitio, con `Role.USER` y `is_external=True`: **nunca** `Role.SYSTEM`; y el bloque no se concatena al prefijo (no se importa `prefix`).
3. `memory_loader.py` solo captura `Exception` (nunca `BaseException`, un `except` desnudo ni `CancelledError`) y ningún manejador liga la excepción (no se conserva el error del almacén).
4. `adapters/storage/memory_store.py`: no abre conexión propia (usa `.connection()`), no importa el bucle ni `cli`; el DDL `_V6` no contiene `REFERENCES` (sin clave foránea).
5. `adapters/tools/memoria.py`: solo stdlib, API pública del núcleo y su paquete; `remember` se llama solo con `entry.key` y `entry.content` (lo que salió de `make_entry`); no captura la cancelación ni importa un almacén ni el bucle (sus manejadores de los errores de dominio ligan el error solo para usar su texto fijo; el de `Exception` no).
6. `bootstrap.py`: `MemoryTool` se registra solo bajo `if config.memory.enabled`, `MEMORY_TOOL_NAME` está entre los nombres que oculta `RegistryView`, y `memory.load_into` no se llama desde `_resume_command`.
7. `core/context/cut.py` sigue sin importar `adapters`, `cli`, el bucle ni `TaskCriteria` (guarda de compactación existente, sin cambios).

`adapters/storage/` y `adapters/tools/` ya están cubiertas por `test_adapters_boundaries.py`; `bootstrap.py`, por `test_bootstrap_boundaries.py` (no cambia: solo importa API pública).

## Archivos protegidos (no tocar)

`core/interfaces/`, `core/events.py`, `core/loop.py`, `core/context/compactor.py`, `core/redaction.py`, `core/verification/`, `core/in_memory_event_bus.py`, `tests/doubles/`, `docs/archivo/`. No se toca `cli/` (la línea de pantalla usa el `WarningSink` y la herramienta usa el bloque de aprobación existente).

## Mapeo a tareas del plan de sprints

Sp4-03 «Tabla de memorias en la misma base» (1,5 h) → T004; Sp4-04 «Implementar MemoryStore» (2 h) → T005; Sp4-05 «Herramienta de escritura en memoria» (2 h) → T006; Sp4-06 «Carga al iniciar con presupuesto de tokens» (3 h) → T002, T003 y T008; Sp4-07 «Pruebas de recuperación entre sesiones» (2,5 h) → T009 y T010. T007 (configuración) y T011 (cierre) no tienen tarea `Sp4` propia.

## Hallazgos esperados

1. El puerto `MemoryStore` de HU-00-01 no alcanza para AC-02 (no informa de lo omitido); se añadió `MemoryLog` en `core/context/` en lugar de cambiar el contrato (D-01). Si A, B y C prefieren ampliar el puerto, `MemoryLog` desaparece.
2. `split_history` (HU-02-03) tiene que saltar el bloque (D-09): es el único cambio en código de la compactación. Una alternativa sin tocarlo sería un mensaje `SYSTEM` (descartada: eleva a instrucción lo que escribió un modelo).
3. La memoria no se carga al reanudar (D-10): una sesión reanudada no ve la memoria que la original recibió al abrirse.
4. La herramienta pregunta en cada `guardar` (D-07); si resulta incómodo, una opción `[memory]` para abrirla es trabajo de HU-04-04 o HU-04-05 (C).
5. La redacción de secretos es heurística (HU-10-02): HU-04-05 puede pedir negarse a guardar en lugar de ocultar.
6. HU-04-03 (memoria estructurada de la sesión), HU-04-04 (inspeccionar y editar) y HU-04-05 (no guardar secretos) quedan fuera; la tabla `memorias` no tiene columna de sesión de origen y HU-04-04 puede necesitarla (cambio aditivo en una versión 7).
7. El alcance es el archivo de la base de sesiones (D-03): dos proyectos que compartan archivo comparten memoria.
8. Las fichas HU-04-01 (PHU 2) y HU-04-02 (PHU 3) están en el reparto de Sprint 4 «por ratificar» (`docs/PROGRESO.md`).
