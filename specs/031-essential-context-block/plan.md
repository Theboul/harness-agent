# Implementation Plan: HU-02-06.1 — Contexto esencial persistente fuera del historial compactable

**Branch**: `gustavo` (directorio de la spec: `031-essential-context-block`) | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/031-essential-context-block/spec.md` (con sus Clarifications: Q1 = A, Q2 = A con condición y la decisión conservadora sobre sesiones sin tarea)

## Summary

Cada vez que el modelo es llamado en una sesión **con tarea**, el contexto lleva, íntegro y una sola vez, un **bloque esencial**: un mensaje de sistema con el ticket, el objetivo, las reglas y los criterios (estado actual), guardado aparte del historial. La compactación de HU-02-03 no lo toca, no lo resume y no lo ve; las instrucciones siguen siendo los mensajes provisionales de hoy, que el bloque no repite.

- `core/context/` (puro): `essential.py` (claves, topes, limpieza, `make_items`, `render_block`, marca y localización, `instruction_messages`, errores) y `renewer.py` (protocolos de solo lectura y `EssentialRenewer`, que sustituye el bloque in situ, idempotente y sin dos bloques).
- `adapters/storage/`: esquema SQLite **v4 aditivo** (tabla `contexto_esencial`) y `SqliteEssentialStore` (escritura única al crear la sesión, lectura después, sobre `store.connection()`).
- `bootstrap.py`: solo cablea. Valida antes de abrir nada, guarda los elementos tras `start_task`, y renueva **al empezar cada petición, antes de la compactación**, y antes de cada ronda de verificación, sin tocar `VerifyingRunner`.

No cambian `core/loop.py`, `core/interfaces/`, el catálogo de eventos, `core/redaction.py`, `core/verification/`, ni la lógica de `split_history` y del compactador de HU-02-03.

**Alcance honesto**: hoy una tarea solo entra a una sesión por `compose(task=…)` (R1). El bloque es alcanzable solo por composición, como el verificador de HU-11-04.1; no se arregla aquí.

## Technical Context

**Language/Version**: Python 3.12; solo biblioteca estándar en `core/`.

**Primary Dependencies**: ninguna nueva. Reutiliza el estimador (`estimate_message`), `ContextSettings` y `threshold_tokens` (HU-02-03), `clean_summary` (limpieza y credenciales con `core/redaction.py`), `TaskCriteriaItem`, `SqliteSessionStore` y su conexión compartida, y el patrón de composición de HU-11-04.1 y HU-02-03.

**Storage**: SQLite: esquema 4 (tabla `contexto_esencial`); `events`, `resumenes` y `criterios*` no cambian. Migración aditiva desde 1, 2 y 3.

**Testing**: pytest (`asyncio_mode = "auto"`), `FakeProvider` que graba lo recibido, bases reales en `tmp_path` (también creadas con los esquemas 1, 2 y 3), pruebas al azar con semilla 20261031, sesión larga simulada propia en `tests/`.

**Target Platform**: Windows y Linux (CI de ambos).

**Project Type**: biblioteca/CLI hexagonal.

**Performance Goals**: una renovación son una lectura de SQLite y armar un texto de ≤ 20 464 caracteres; la guarda no añade llamadas al modelo ni escrituras en el camino normal.

**Constraints**:
- sin cambios en `core/loop.py`, `core/interfaces/`, el catálogo de eventos, `core/redaction.py`, `core/verification/` ni en `split_history`, `choose_cut`, `rebuild_history` y el compactador;
- `core/` no importa `adapters/` ni `cli/`; el adaptador no abre conexión propia;
- el bloque nunca se resume, se trunca ni se escribe desde el modelo; rechazo explícito si no cabe;
- falla cerrada: la petición no se envía con un bloque viejo ni con criterios tomados del historial;
- ni el bloque ni el texto de un criterio en eventos, errores o avisos (centinelas);
- ningún evento nuevo; la lista de provisionales (`history_prefix`) no cambia.

**Scale/Scope**: 2 módulos nuevos en `core/context/`, 1 adaptador, un paso de esquema, ajustes pequeños en `bootstrap.py` (mover la construcción del prefijo, validar, guardar, renovar) y 10 archivos de pruebas nuevos más 1 guarda.

## Constitution Check

*GATE: pasa antes de la Fase 0 y se revisa tras la Fase 1.*

| Principio / regla | Cumplimiento |
|---|---|
| I. Una historia, una spec | Solo HU-02-06.1 (Sp2-18 a Sp2-20). Pasa |
| II. Microtareas de 15–40 min | 12 tareas de implementación de ≤ 40 min (T002–T010 con T004b, T007b y T009b) más inicio y cierre. Pasa |
| III. Código modular, tipado, Python 3.12 | Módulos pequeños y puros, `dataclass(frozen=True)`, `mypy` del repo. Pasa |
| IV. Pruebas y CI multiplataforma | Sin red ni claves; bases en `tmp_path`. Pasa |
| V. Criterios inmutables | Flujo, reglas y AC-01 a AC-03 copiados tal cual por script (comprobado en la spec). Pasa |
| VI. Disciplina de sprints | Fuera: HU-02-06.2, HU-03-04, HU-02-04, HU-02-05, HU-07-05, PD-06, cargar tareas desde la línea de comandos, el gancho en el bucle. Pasa |
| VII. Consulta quirúrgica | Ancla `#hu-02-06.1`, SPK-03 y el código citado. Pasa |
| VIII. PROGRESO.md | Fila de inicio y cierre (`En revisión`) con observaciones |
| IX. DoD estricta | Tareas humanas H1–H8 |
| X. `docs/archivo/` | No se toca. Pasa |
| V-03, V-04, V-17 | El historial original no se toca (V-03); lo esencial no se resume (V-04); el contenido externo sigue marcado como tal y el bloque solo contiene lo que fija la persona que define la tarea (V-17). Pasa |

**Hard Rules de las skills del proyecto**

- **`arquitectura-hexagonal-clean`**: la regla (formato, topes, marca, sustitución) es pura y vive en `core/context/`. Lo externo entra por protocolos de **solo lectura** definidos en `core/context/` (no en `core/interfaces/`, para no cambiar contratos): `EssentialSource` y `CriteriaReader`. Los implementan `SqliteEssentialStore` (adaptador nuevo de B) y `SqliteTaskStore` (sin cambios). Se conectan solo en `bootstrap.py`. El núcleo no captura excepciones de SQLite: captura `Exception` de la fuente y lanza un error de dominio de mensaje fijo.
- **`estructura-carpetas-harness`**: rutas en la tabla de abajo; ninguna carpeta nueva.
- **`verificar-fronteras-hexagonales`**: `core/context/` ya tiene su guarda (`test_context_boundaries.py`) y `test_compaction_boundaries.py` recorre todos sus archivos (los módulos nuevos deben cumplirla sin tocarla); se añade `test_essential_boundaries.py`.

### Recorrido de los *Decision Gates* (`arquitectura-hexagonal-clean`)

| Pregunta | Respuesta |
|---|---|
| ¿Regla o comportamiento nuevo? | Sí: qué contiene el bloque, cómo se arma, se localiza y se sustituye, en `core/context/`, exportado en `core/__init__.py` |
| ¿Necesita algo de fuera? | Sí: el almacén de elementos y la fuente de criterios (protocolos de solo lectura en `core/context/`) |
| ¿Quién lo implementa? | `SqliteEssentialStore` (adaptador nuevo) y `SqliteTaskStore` (existente) |
| ¿Cómo se conecta? | Inyección en constructor; `bootstrap.py` lo monta y lo llama |
| ¿Cómo se prueba? | Núcleo con falsos de los protocolos y `FakeProvider`; adaptador con bases reales; integración con `compose()` |
| ¿Es asíncrono? | No: leer y armar texto es síncrono; solo la compactación (existente) espera al proveedor |

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa de nuevo al cerrar)

| Punto | Resp. | Justificación |
|---|---|---|
| ¿Regla de negocio en `core/` y no en un adaptador? | Sí | `core/context/essential.py` y `renewer.py` |
| ¿Todo lo externo pasa por un puerto o protocolo con tipos del dominio? | Sí | `EssentialSource` y `CriteriaReader` (protocolos internos de solo lectura) |
| ¿Puertos, entidades y eventos sin cambios? | Sí | Ninguno cambia; no hay eventos nuevos |
| ¿Errores sin reproducir valores? | Sí | Mensajes fijos de `EssentialContextError` y `SessionStoreError` |
| ¿Inyección y conexión solo en `bootstrap.py`? | Sí | Adaptador, renovador y llamadas se montan ahí |
| ¿Núcleo probado con dobles, sin red ni claves? | Sí | Falsos de los protocolos y `FakeProvider`; SQLite solo en pruebas del adaptador y de integración, en `tmp_path` |
| ¿Prueba de contrato del adaptador? | Sí | `test_essential_store.py` fija las garantías de `contracts/essential_store.md` |
| ¿`pytest tests/architecture` con la guarda nueva? | Sí (diseño) | `test_essential_boundaries.py` |
| ¿Eventos en lugar de imprimir? | Sí | El fallo se informa por el aviso de la composición (`WarningSink`); la alteración de criterios sigue publicando `criteria_tampered` desde el almacén de tareas |
| ¿Lo público exportado en `core/__init__.py`? | Sí | Lista en el modelo de datos |
| ¿Falla cerrada y secretos? | Sí | Petición no enviada si el bloque no cabe o la fuente falla; credenciales de URL ocultas antes de guardar; sin valores en eventos ni avisos |
| ¿Otro integrante revisó el cambio? | No (pendiente) | H3 |

**Resultado del gate**: pasa. Desviaciones en *Complexity Tracking*.

### Revisión de la lista contra el código (T010, 2026-10-27)

Los once «Sí» de diseño se confirman contra el código: la regla vive en `core/context/essential.py` y `renewer.py` (stdlib y núcleo; `test_context_boundaries.py`, `test_compaction_boundaries.py` y `test_essential_boundaries.py` en verde); lo externo entra por los protocolos de solo lectura `EssentialSource` y `CriteriaReader`; `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py` y `core/verification/` no tienen diff; los mensajes de error y de aviso son textos fijos que nombran el elemento y el tope y no un valor; la conexión y las llamadas están solo en `bootstrap.py`; el núcleo se prueba con falsos y `FakeProvider` y SQLite solo en `tmp_path`; `test_essential_store.py` fija las garantías del contrato; lo público está exportado en `core/__init__.py`; la renovación falla cerrada y no filtra valores. **Un «No» sigue en pie**: la revisión de otro integrante (H3).

Ajustes frente al diseño, hallados al implementar (ninguno cambia un puerto ni un contrato):

- `check_block` y `check_creation` nacieron en T003 (necesitan `render_block`).
- Una prueba existente más tuvo que ajustarse además de las 14 previstas (`test_a_tampered_database_runs_nothing`): la falla cerrada de la renovación intercepta la fuente alterada antes de la primera ronda.

## Project Structure

### Documentation (this feature)

```text
specs/031-essential-context-block/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── essential_store.md       # protocolos de solo lectura, garantías del adaptador, falla cerrada
│   ├── block_format.md          # texto exacto del bloque con ejemplos normativos
│   ├── block_marker.md          # la marca, quién es el bloque y reglas de sustitución
│   ├── context_order.md         # orden del contexto actualizado, ejemplos recalculados a mano
│   └── renewal_points.md        # cuándo y quién renueva; fallos
├── checklists/requirements.md
└── tasks.md                     # lo genera /speckit-tasks
```

### Source Code y fila de `estructura-carpetas-harness` que justifica cada ruta

| Ruta | Fila de la tabla de Decision Gates | Notas |
|---|---|---|
| `src/harness_agent/core/context/essential.py` (nuevo) | «Regla de negocio nueva … subpaquete de `core/`» | Claves, topes, limpieza, `make_items`, `criteria_reference`, `render_block`, `block_fits`, `check_block`, `check_creation`, `find_blocks`, `block_message`, `instruction_messages` |
| `src/harness_agent/core/context/renewer.py` (nuevo) | «Regla de negocio» + protocolos propios | `EssentialSource`, `CriteriaReader`, `RenewalOutcome`, `EssentialRenewer` |
| `src/harness_agent/core/context/errors.py` (mod.) | «Error de dominio → `errors.py` del subpaquete» | `EssentialContextError`, `…TooLarge`, `…Unavailable` |
| `src/harness_agent/core/context/__init__.py`, `core/__init__.py` (mod.) | «Todo lo público de `core/` se exporta» | Exportaciones |
| `src/harness_agent/adapters/storage/_schema.py` (mod.) | «Código con `sqlite3` … `adapters/<subpaquete>/`» | `SCHEMA_VERSION = 4` y `_V4` |
| `src/harness_agent/adapters/storage/essential_store.py` (nuevo) | Ídem; receta «almacén» de `recetas.md` | `SqliteEssentialStore` sobre `store.connection()` |
| `src/harness_agent/adapters/storage/__init__.py` (mod.) | Exportación del subpaquete | Nombre nuevo |
| `src/harness_agent/bootstrap.py` (mod.) | «Unir piezas y elegir implementaciones → `bootstrap.py`» | Solo cableado |
| `tests/unit/core/context/test_essential_items.py`, `test_essential_block.py`, `test_essential_renewer.py`, `test_essential_renewer_failures.py`, `test_essential_renewer_properties.py` (nuevos) | «`tests/` refleja `src/`» | Núcleo |
| `tests/unit/adapters/storage/test_schema_v4.py`, `test_essential_store.py` (nuevos) | Ídem | Esquema y adaptador |
| `tests/unit/test_bootstrap_essential.py` (nuevo) | Ídem; patrón de `test_bootstrap_compaction.py` | Cableado |
| `tests/integration/test_essential_context_agent_loop.py`, `tests/integration/test_essential_context_security.py` (nuevos) | `tests/integration/` | Sesión larga de punta a punta; falla cerrada; seguridad |
| `tests/architecture/test_essential_boundaries.py` (nuevo) | `tests/architecture/` | Guarda |
| `.claude/skills/` y `.agents/skills/` (`verificar-fronteras-hexagonales/SKILL.md`, `estructura-carpetas-harness/references/arbol.md`), `CLAUDE.md` | Documentación del proyecto | Dos copias idénticas |

**Structure Decision**: sin carpetas nuevas; dos módulos puros, un adaptador y el cableado.

### Decisiones clave (detalle en `research.md`)

1. **El bloque es un `SYSTEM` tras los provisionales y antes de la petición** (R3): cae en la cabeza protegida que HU-02-03 ya reconoce; ninguna línea de la compactación cambia.
2. **Marca fija buscada solo entre los `SYSTEM` del prefijo contiguo** (R4): un texto externo no puede suplantarlo ni ser sustituido.
3. **Renovar antes de compactar y antes de cada ronda** (R5): en la composición; `VerifyingRunner` no se toca; limitación conocida dentro de una ronda.
4. **Instrucciones sin repetir** (R8): los provisionales siguen como están; el registro (texto exacto, una fila por mensaje, etiqueta de origen) solo sirve para reconstruir.
5. **Topes como constantes; manda el 20 % del umbral** (R7).
6. **Validar antes de abrir; guardar tras `start_task`** (R9): no atómico con la sesión (riesgo conocido, sin tocar el almacén de tareas de A).
7. **Falla cerrada visible** (R11, R16): mensaje fijo que nombra el elemento y el tope, por el aviso de la composición, y excepción que termina la sesión con código 1.
8. **Sin tarea frente a con tarea sin elementos** (R15): sin tarea no hay renovador ni bloque; con tarea el renovador exige objetivo, criterios y alguna instrucción y falla cerrado si faltan (no existe un resultado «sin bloque»).
9. **Fallo del segundo guardado** (R17): `compose` lanza y cierra el almacén; no queda una composición usable.

## Pruebas existentes que cambian (lista completa y exacta)

Búsqueda en `tests/` y **corrida en seco** del esquema 4 (tabla nueva y versión 4, restaurada después con `cmp`): 13 fallos y 6 741 pasadas. Más una prueba por la API pública. **Regla**: ejecutarlas **antes, sin tocar**, y ver que fallan por la versión o por la tabla nueva; solo entonces ajustar las líneas declaradas, y registrarlas como «autorizado por el usuario, pendiente de ratificar»; cualquier **otra** prueba que falle detiene la implementación y se pregunta antes de tocarla.

| # | Prueba | Línea (hoy) | Por qué falla | Ajuste |
|---|---|---|---|---|
| 1 | `tests/unit/adapters/storage/test_schema.py::test_schema_version_is_current` | 46 | `SCHEMA_VERSION == 3` | `== 4` |
| 2 | `tests/unit/adapters/storage/test_schema_migration.py::test_schema_version_is_two` | 84 | `SCHEMA_VERSION == 3` | `== 4` |
| 3 | `…/test_schema_migration.py::test_new_database_gets_the_criteria_tables` | 90 | `user_version == 3` | `== 4` |
| 4 | `…/test_schema_migration.py::test_version_one_database_migrates_without_losing_data` | 124 | `user_version == 3` | `== 4` |
| 5 | `…/test_schema_migration.py::test_unknown_versions_are_still_refused` | 158 | `PRAGMA user_version = 4` ya es válida | `= 5` |
| 6 | `tests/unit/adapters/storage/test_schema_v3.py::test_the_version_is_three` | 140 | `SCHEMA_VERSION == 3` | `== 4` |
| 7–8 | `…/test_schema_v3.py::test_an_old_database_migrates_to_three_and_keeps_every_row[1]` y `[2]` | 153 y 154–158 | `user_version == 3` y la tabla nueva aparece en el volcado | `== 4` y una aserción `after.pop("contexto_esencial") == []` junto a la de `resumenes` |
| 9–10 | `…/test_schema_v3.py::test_reopening_a_migrated_database_changes_nothing[1]` y `[2]` | 171 | `user_version == 3` | `== 4` |
| 11–12 | `…/test_schema_v3.py::test_a_migrated_database_has_the_same_table_as_a_new_one[1]` y `[2]` | 184 | `user_version == 3` | `== 4` |
| 13 | `tests/integration/test_rejection_reason_agent_loop.py::test_the_reason_is_not_stored_in_the_database` | 295 | El conjunto exacto de tablas | Añadir `"contexto_esencial"` |
| 14 | `tests/unit/adapters/storage/test_public_api.py::test_all_lists_exactly_the_public_names` | 7–26 (`EXPECTED`) | El adaptador nuevo se exporta | Añadir `"SqliteEssentialStore"` (la de importabilidad itera la misma lista y pasa sola) |

Total: **14 pruebas** (13 de la corrida en seco más la de la API pública) en **5 archivos**; los cambios son de una a dos líneas por prueba. Las 13 de esquema y de tablas (números 1 a 13) se ajustan en **T005**, la tarea del esquema 4; la 14 en **T006**, porque su nombre solo se exporta cuando existe el adaptador (R20). `test_schema_v3.py` queda como prueba histórica de la migración al esquema 3 con las aserciones de versión puestas al día.

**Revisadas y sin cambio esperado** (se ejecutan sin tocar; si alguna falla se detiene la implementación):

| Qué fija | Dónde | Por qué no cambia |
|---|---|---|
| `history_prefix` (longitud y contenido) | `test_bootstrap_shell.py`, `test_bootstrap_git.py`, `test_bootstrap_task_commands.py`, `test_task_commands_agent_loop.py` | El bloque no entra en `history_prefix` (FR-022) |
| El recorte `[2:]` de la sesión | `test_bootstrap_main.py:96` | Sesión sin tarea: no hay bloque (FR-002) |
| Eventos y suscriptores del registrador | `test_event_recorder*.py`, `test_bootstrap_compose.py` | Ningún evento nuevo; el `skip` de HU-02-03 no cambia |
| Conjunto de tablas y `SCHEMA_VERSION + 1` | `test_schema.py` (otras), `test_sqlite_session_store.py` | Usan `SCHEMA_VERSION` simbólico o comprueban subconjuntos |
| `core.__all__` | `test_core_public_api.py`, `test_context_assembler_loop.py` | Comprueban inclusión y unicidad, no igualdad |
| Sesiones con tarea por el ejecutor (`runner.run`, `run_session`) | `test_bootstrap_verification.py`, `test_criteria_verification_agent_loop.py` | Filtran por `is_external` o leen `[-1]`; el bloque es un `SYSTEM` más. La descripción de un criterio aparece en el bloque, pero el comando y la salida no |
| Compactación | `test_compactor*.py`, `test_cut*.py`, `test_context_compaction_agent_loop.py`, `test_bootstrap_compaction.py` | No pasan por la composición con tarea o no usan el renovador |

## Tabla FR / AC → tarea → prueba

(No habrá `/speckit-analyze` en esta historia.) Tareas: ver «Estimación de tareas».

| Requisito | Tarea | Prueba (archivo y qué comprueba) |
|---|---|---|
| FR-001 (cinco elementos aparte, con clave y origen) | T002, T005, T006 | `test_essential_items.py` (`make_items`), `test_schema_v4.py`, `test_essential_store.py` (E1: 7 filas) |
| FR-002 (al crear la sesión; ausente no inventado; sin tarea, sin bloque) | T002, T007, T009 | `test_essential_items.py` (omitidos), `test_bootstrap_essential.py` (con y sin tarea: 0 filas sin tarea), integración (el contexto sin tarea es el de hoy) |
| FR-003 (íntegro, una vez, sin instrucciones dentro) | T003, T004, T008 | `test_essential_block.py` (E1, E3), `test_essential_renewer.py`, integración (el proveedor graba cada llamada) |
| FR-004 (orden y posición) | T004, T007b, T008 | `test_essential_renewer.py` (E1 y E2 de la marca), `test_bootstrap_essential.py` (posición `len(history_prefix)`), integración (orden en cada llamada) |
| FR-005 (la compactación no lo toca; idéntico) | T004b, T008 | `test_essential_renewer_properties.py` (estable), integración (dos compactaciones, byte a byte, misma posición) |
| FR-006 (la entrada del resumen no lo contiene) | T009b | Integración con la llamada **real** del compactador |
| FR-007 (el modelo no lo escribe) | T009b | Integración: herramientas de archivo y shell sobre la base denegadas por la política; la tabla no cambia; ninguna herramienta nombra la tabla; repetir la marca no sustituye al bloque |
| FR-008 (criterios por referencia, desde su fuente) | T004, T008 | `test_essential_renewer.py` (lee por la referencia guardada), integración (resumen con copia vieja: gana el bloque) |
| FR-009 (orden, descripción, estado; nunca el comando) | T003, T009b | `test_essential_block.py` (E1, E5), integración (el texto enviado no contiene comando, condición ni evidencia) |
| FR-010 (falla cerrada, también con tarea sin elementos) | T004b, T007b, T009 | `test_essential_renewer_failures.py` (fuente y lector fallan; faltan elementos), `test_bootstrap_essential.py` (mensaje fijo, 0 llamadas, código 1), integración (sello alterado; filas borradas) |
| FR-011 (sin criterios; bloque vacío no se envía) | T003, T004b, T009 | `test_essential_block.py` (E3, E4), `test_essential_renewer_failures.py` (elementos obligatorios), integración (lista vacía de criterios) |
| FR-012 (renovación; sustituye; no dos bloques) | T004, T004b, T007b, T008 | `test_essential_renewer*.py` (sustituir, azar), `test_bootstrap_essential.py` (los dos puntos y el orden), integración (criterio cumplido entre rondas) |
| FR-013 (topes; rechazo sin truncar; mensaje con elemento y tope) | T002, T003, T004b, T007, T009 | `test_essential_items.py` (8 000 por elemento), `test_essential_block.py` (E7, 20 %), `test_essential_renewer_failures.py` (cambio de modelo), `test_bootstrap_essential.py` (no arranca), integración (ventana pequeña) |
| FR-014 (cuenta en el umbral) | T008 | Integración (ejemplo E4 de `context_order.md`: con y sin bloque cambia el disparo) |
| FR-015 (reconstruir desde el almacén) | T003, T006 | `test_essential_block.py` y `test_essential_store.py` (`instruction_messages` igual al prefijo; `render_block` igual al enviado) |
| FR-016 (sin filtración; mensajes fijos; sin eventos nuevos) | T002, T007b, T009b, T010 | `test_essential_items.py` (mensajes sin centinela), `test_bootstrap_essential.py` (ningún evento nuevo), integración de seguridad (0 apariciones con centinelas), `test_essential_boundaries.py` |
| FR-017 (SYSTEM del prefijo; sin tocar el bucle) | T008, T011 | Integración (el bucle acepta el historial); `git diff` vacío de lo prohibido |
| FR-018 (esquema aditivo y migración) | T005 | `test_schema_v4.py` (bases reales v1, v2 y v3, filas antes y después) |
| FR-019 (proveedor simulado; AC-03) | T008 | Integración: proveedor local que responde desde el contexto recibido |
| FR-020 (pruebas existentes) | T005, T006, T011 | Las 14 de la lista, ejecutadas antes sin tocar; suite completa al cerrar |
| FR-021 (instrucciones intactas, una sola vez; registro no inyectado) | T003, T008 | `test_essential_block.py` (la clave se ignora), integración (cada instrucción una vez en cada llamada) |
| FR-022 (`history_prefix` no cambia) | T007 | `test_bootstrap_essential.py` (la lista antes y después) y las siete pruebas de arranque sin tocar |
| AC-01 (lo esencial idéntico tras compactar) | T008 | Integración: cinco centinelas, varias llamadas y dos compactaciones |
| AC-02 (instrucciones intactas y criterios desde su fuente) | T008, T009 | Integración: provisionales idénticos tras compactar; criterios leídos de su fuente; fuente alterada |
| AC-03 (objetivo recordado) | T008 | Integración: respuesta del proveedor local que depende del bloque; con un resumen que lo pierde sigue bien |
| SC-001, SC-002, SC-004, SC-008, SC-009 | T008 | Integración |
| SC-003, SC-007 | T009b | Integración de seguridad |
| SC-005, SC-006, SC-010 | T004b, T009 | `test_essential_renewer_failures.py` e integración |
| SC-011 | T005, T011 | `test_schema_v4.py` y la suite completa |

## Estimación de tareas (RITMO: 12 de implementación de ≤ 40 min, TDD, más inicio y cierre)

| Tarea | Contenido | Min | Sp2 |
|---|---|---|---|
| T001 | Inicio: línea base (suite, ruff, mypy, guardas), las 14 pruebas pasan sin tocar, fila de HU-02-06.1 a `En curso` | 15 | — |
| T002 | `essential.py` (parte 1) y errores: claves, topes por elemento, limpieza, `make_items`, `criteria_reference`, mensajes fijos (rojo primero) | 40 | Sp2-18 |
| T003 | `essential.py` (parte 2): `render_block`, `block_fits`, `check_block`, `check_creation`, `instruction_messages` con los ejemplos E1–E7 | 35 | Sp2-19 |
| T004 | `renewer.py`: `find_blocks`, `block_message`, protocolos y `EssentialRenewer` (insertar, sustituir, idempotencia, imitación de la marca) | 40 | Sp2-19 |
| T004b | `renewer.py`: falla cerrada, elementos obligatorios (R15), cambio de modelo, azar de semilla fija | 35 | Sp2-19 |
| T005 | Esquema 4 y migración con bases reales v1, v2 y v3; las 13 pruebas de esquema (sin tocar primero, luego ajuste) | 30 | Sp2-18 |
| T006 | `SqliteEssentialStore` y la prueba de la API pública (la 14) | 35 | Sp2-18 |
| T007 | `compose()`: prefijo antes de abrir (refactor y siete pruebas de arranque), validar, guardar tras `start_task`, fallar cerrado | 40 | Sp2-19 |
| T007b | `run_session` y las rondas: renovar antes de compactar y antes de cada ronda; mensaje fijo y código 1 | 35 | Sp2-19 |
| T008 | Integración (AC-01, AC-02, AC-03, cambios a mitad de tarea, orden, umbral) | 40 | Sp2-20 |
| T009 | Integración de falla cerrada (sin tarea frente a con tarea sin elementos, fuente alterada, no cabe, guardado que falla) | 40 | Sp2-20 |
| T009b | Integración de seguridad (centinelas, llamada de resumen real, el modelo no edita la tabla, criterios sin comando) | 35 | Sp2-20 |
| T010 | Guarda de arquitectura, skills (dos copias), CLAUDE.md, lista de comprobación y detector de secretos | 30 | — |
| T011 | Cierre: cuatro puertas, cobertura, diff vacío de lo prohibido, `PROGRESO.md` (`En revisión`), evidencia | 30 | — |

Total de Claude: **480 min (8 h)**; las doce de implementación suman 420 min frente a 300 min (5 h) de Sp2-18 a Sp2-20: el presupuesto es una advertencia, no un límite. La diferencia sale de partir tres tareas que superaban 40 min (T004, T007 y T009) y de las decisiones de falla cerrada. Si otra supera 40 min al ejecutarse, se parte y se registra.

## Tareas humanas (Claude no las marca)

- **H1**: **acuerdo de A** sobre un único gancho futuro en `core/loop.py` antes de cada llamada al modelo (resolvería la renovación del bloque y la compactación **dentro** de una tarea larga), y **aviso a A** de que el paso 5 del flujo de HU-11-01 (inyectar objetivo, reglas y criterios) estaba sin hacer y lo cubre esta historia. Cualquier cambio del bucle, de los puertos o del catálogo necesita el acuerdo de A, B y C.
- **H2**: visto bueno de **B** al esquema 4 de `adapters/storage/`; visto bueno de **C** a `bootstrap.py`.
- **H3**: revisión cruzada por A o C (la historia es de B).
- **H4**: el **PO** decide qué entra al bloque (los cuatro elementos, que los criterios se muestren sin comando, que el contexto libre de la tarea quede fuera), los **topes** (8 000 caracteres por elemento y 20 % del umbral; el analizador de tareas admite 20 000 por sección, así que una tarea válida de HU-11-01 puede no arrancar) y si las **sesiones sin tarea** deberían recibir también un bloque.
- **H5**: corrida de SPK-03 con un modelo real cuando D-IA lo permita (no bloquea).
- **H6**: CI remota en `ubuntu-latest` y `windows-latest`, con push y PR confirmados por una persona.
- **H7**: aviso a **A** (HU-03-04): el bloque y el registro de instrucciones se rearman desde el almacén; a **B** (HU-02-06.2): las decisiones acumuladas se añadirán a la misma tabla; a **A y B** (HU-02-01): el bloque debería formar parte del prefijo del ensamblador cuando se integre.
- **H8**: aviso a **A** y **C**: `main()` no carga tareas, así que el bloque solo se alcanza con `compose(task=…)`; en un issue de GitHub el identificador del ticket es el título (el número no se conserva).

## Complexity Tracking

| Desviación | Por qué | Alternativa descartada |
|---|---|---|
| `compose()` construye el prefijo provisional **antes** de abrir el almacén | Para validar topes antes de crear la sesión y no dejar huérfanos | Validar después de `start_task` (deja una sesión sin elementos) |
| Guardar los elementos en una segunda transacción tras `start_task` | No tocar el almacén de tareas (de A) | Un gancho dentro de `start_task` |
| La primera ronda renueva dos veces (una idempotente) | Compactar necesita el bloque vigente antes y la ronda necesita renovar en las siguientes | Renovar solo en la ronda (la compactación no vería el bloque vigente) |
| El tope por elemento (8 000) es más estricto que el del analizador (20 000) | Lo manda la spec (FR-013) y protege la ventana | Igualar al analizador (el bloque podría pesar el 31 % del umbral) |
| El renovador de una sesión con tarea no tiene resultado «sin bloque» (exige objetivo, criterios e instrucciones) | Que «sin elementos» no se confunda con «sin tarea» y la petición salga sin contexto en silencio (R15) | Un resultado `NONE` |
| Un criterio semántico en espera de validación humana se muestra como `pendiente` | El puerto de lectura no expone el tipo y la spec pide solo pendiente o cumplido | Ampliar `TaskCriteriaItem` (cambia un contrato) |
