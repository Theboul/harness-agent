# Implementation Plan: HU-03-04 — Reanudar una sesión por identificador

**Branch**: `gustavo` (directorio de la spec: `032-resume-session-by-id`) | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/032-resume-session-by-id/spec.md` (con sus Clarifications: Q1 = B, Q2 = B —interpretación de la regla 1 pendiente de ratificar—, Q3 = A, las ocho precisiones y las contradicciones resueltas)

## Summary

El operador escribe `/reanudar <id>` en la sesión interactiva y el agente continúa donde quedó: se cargan los mensajes guardados, se reconstruye el contexto **como lo tenía el proceso al salir** (prefijo, petición inicial, resumen vigente y mensajes no cubiertos; sin resumen, el historial completo), la compactación de siempre corre antes de la primera petición y los eventos nuevos siguen en la **misma sesión**. Solo se reanudan sesiones **sin tarea**.

Como los eventos no llevan lo necesario para reconstruir los mensajes (hallazgo confirmado, `research.md` R1), el plan añade:

- `core/context/` (puro, solo stdlib): `conversation.py` (registro de mensaje ya limpio, redacción de credenciales de URL, rechazo sin motivo y `ConversationCapture`, que sigue los mensajes **por identidad** y guarda lo pendiente cuando el bus publica cada evento) y `resume.py` (identificador, errores de mensaje fijo, `rebuild_conversation` y `resume_session`, reconstrucción pura con cierre de llamadas sin resultado).
- `adapters/storage/`: esquema SQLite **v5 aditivo** (tabla `mensajes`) y `SqliteMessageStore` (guardado atómico e idempotente; lectura con cobertura de resúmenes y detección de sesión de tarea / sin detalle), sobre `store.connection()`.
- `cli/app.py` (cambio **mínimo**, área C): `argument_commands` para pasar el argumento a un comando.
- `bootstrap.py`: solo cablea. Suscribe el guardado **antes** del registrador de eventos, lo enlaza al historial en `run_session`, registra `/reanudar`, cambia de sesión con un titular local (fábrica del compactador, sin tocar su lógica) y publica, en la primera petición tras un corte, los `tool_finished` de cierre.

**No cambian**: `core/loop.py`, `core/interfaces/`, el catálogo de eventos, `core/redaction.py`, `core/verification/`, ni la lógica de `ContextCompactor`, `split_history` y del renovador de HU-02-06.1. Las pruebas que aseguran que los eventos no llevan argumentos ni el motivo del rechazo **no se tocan**.

**Alcance honesto**: hoy `main()` no carga tareas; las sesiones reales son sin tarea, y esas son las reanudables. Una sesión con tarea se rechaza con un mensaje claro. El presupuesto del sprint (3 PHU, 7 h) es una advertencia: el alcance real (persistir, reconstruir, comando y CLI) lo supera (ver *Estimación*).

## Technical Context

**Language/Version**: Python 3.12; solo biblioteca estándar en `core/`.

**Primary Dependencies**: ninguna nueva. Reutiliza `hide_url_credentials`, `rejection_message`, `is_real`, `frame_summary` (núcleo) y `SqliteSessionStore.connection()`.

**Storage**: SQLite: esquema 5 (tabla `mensajes`); `sessions`, `events`, `resumenes`, `criterios*` y `contexto_esencial` no cambian. Migración aditiva desde 1, 2, 3 y 4.

**Testing**: pytest (`asyncio_mode = "auto"`), `FakeProvider` que graba lo recibido, bases reales en `tmp_path` (también creadas con DDL literal de los esquemas 1 a 4), pruebas al azar con semilla 20261101, sin red.

**Target Platform**: Windows y Linux (CI de ambos).

**Project Type**: biblioteca/CLI de terminal con arquitectura hexagonal.

**Performance Goals**: reconstruir una sesión de 5 000 mensajes y dejarla lista en menos de 5 s (SC-007), sin contar la llamada de resumen de la primera petición.

**Constraints**: falla cerrada (nunca un historial parcial); el comando no escribe nada; el guardado no pierde mensajes en silencio; `core/` sin `sqlite3`, `adapters`, `cli`, `config`; las credenciales de URL se ocultan antes de guardar.

**Scale/Scope**: una tabla, dos módulos puros, un adaptador, un cambio de ~12 líneas en la CLI y el cableado; 19 tareas de ≤ 40 min (16 de implementación).

## Constitution Check

*GATE: pasa antes de la investigación y se revisa tras el diseño.*

| Principio / regla | Cómo se cumple |
|---|---|
| I. Una historia por especificación | Una spec (032) y una PR; las tareas se ordenan: persistir, reconstruir, comando y CLI, integración y cierre |
| II. Microtareas de 15 a 40 min | 19 tareas, ninguna pasa de 40 min (tabla de estimación) |
| III. Código modular, tipado | Dos módulos puros con dataclasses `frozen`, protocolos pequeños, adaptador aparte; `mypy` estricto |
| IV. Pruebas, calidad y CI | TDD con rojo observado; cuatro puertas; CI en Windows y Linux (H7) |
| V. Criterios inmutables | AC-01 y AC-02 copiados literal; el plan no los cambia |
| VI. Disciplina de sprints | La historia es de Sprint 2, sprint activo; no se implementa nada de HU-06-04, HU-03-03 ni HU-10-02 |
| VII. Consulta documental quirúrgica | Se leyeron la ficha, las specs 029–031 y el código tocado |
| VIII. Registro en `PROGRESO.md` | T001 (a `En curso`) y T012 (a `En revisión`) |
| IX. DoD estricta | `En revisión`, nunca `Hecha`; revisión cruzada y CI remota humanas |
| X. `docs/archivo/` inmutable | No se toca |
| V-02 / falla cerrada | Todo error de reanudar es un mensaje fijo; sin historial parcial; el guardado que falla detiene el turno |
| V-03 (compactación no destructiva) | No se borra ni se reescribe nada; el historial completo sigue guardado |
| V-11 (cancelación limpia) | La llamada sin resultado se contesta al continuar, con un resultado de error (R10) |
| V-13 (secretos) | **Parcial**: solo credenciales de URL; la redacción general es HU-10-02 (ver *Complexity Tracking* y H4) |
| V-14 (proveedor simulado) | Todas las pruebas con `FakeProvider` y dobles |

**Resultado del gate**: pasa, con una desviación justificada (V-13 parcial) y los avisos de *Complexity Tracking*. **No se activó ninguna condición de parada**: ninguna decisión obliga a tocar `core/loop.py`, `core/interfaces/`, el catálogo de eventos, `core/redaction.py`, `core/verification/` ni la lógica de `ContextCompactor`/`split_history`/renovador (R4, R6, R10, R12).

### Recorrido de los *Decision Gates* (`arquitectura-hexagonal-clean`)

| Pregunta | Respuesta |
|---|---|
| ¿Es regla o comportamiento nuevo? | Sí → `core/context/` (`conversation.py`, `resume.py`), exportado en `core/__init__.py` |
| ¿Necesita algo de fuera? | Sí: guardar y leer mensajes → **protocolos** `MessageLog` y `ResumeSource` de `core/context/` (mismo patrón que `CompactionStore` y las fuentes de HU-02-06.1); `core/interfaces/` no cambia |
| ¿Quién lo implementa? | `SqliteMessageStore` en `adapters/storage/` |
| ¿Cómo se conecta? | por constructor en `compose()`; `run_session` enlaza el historial y registra el comando |
| ¿Cómo se prueba? | núcleo con dobles locales y `FakeProvider`; adaptador con prueba de contrato (`tests/contracts/`) y bases reales |
| ¿Es asíncrono? | No: guardar, leer y reconstruir son síncronos; solo la compactación y el bucle existentes son async |

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa de nuevo al cerrar)

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿La regla de negocio está en `core/` y no en un adaptador? | **Sí** (captura, redacción, rechazo sin motivo, cobertura, reconstrucción) |
| 2 | ¿Todo lo externo pasa por un puerto de `core/interfaces/`? | **No, justificado**: pasa por protocolos propios de `core/context/` porque cambiar `core/interfaces/` exige el acuerdo de A, B y C y no hace falta (patrón ya usado en HU-02-03 y HU-02-06.1) |
| 3 | ¿Puertos, entidades y eventos siguen sin cambios? | **Sí** (los cierres usan `tool_finished`, tipo existente) |
| 4 | ¿Los errores externos se traducen sin reproducir valores? | **Sí** (`SessionStoreError` y errores de dominio con mensaje fijo, sin causa encadenada) |
| 5 | ¿Dependencias por constructor, conectadas solo en `bootstrap.py`? | **Sí** |
| 6 | ¿El núcleo se probó con dobles, sin disco ni claves? | **Sí** (T002–T005b) |
| 7 | ¿El adaptador real tiene prueba de contrato en `tests/contracts/`? | **Sí** (T007) |
| 8 | ¿Pasa `pytest tests/architecture` y la guarda nueva en Windows y Linux? | **Pendiente**: guarda nueva en T011; Windows y Linux en la CI remota (H7) |
| 9 | ¿El núcleo emite eventos en lugar de imprimir? | **Sí** (no imprime; el aviso fijo sale por el avisador de la composición y la línea de estado se devuelve a la CLI) |
| 10 | ¿Lo público está exportado en `core/__init__.py`? | **Sí** (T002, T004, T005b) |
| 11 | ¿Se respetan falla cerrada, historial intacto y secretos redactados? | **Sí** con el matiz de V-13 (solo URLs) |
| 12 | ¿Otro integrante revisó el cambio? | **No todavía** (H6) |

### Revisión de la lista contra el código (T011, 2026-10-28)

Los once «Sí» de diseño se confirman contra el código: la regla vive en `core/context/conversation.py` y `resume.py` (stdlib y núcleo; `test_context_boundaries.py`, `test_compaction_boundaries.py`, `test_essential_boundaries.py` y `test_conversation_boundaries.py` en verde); lo externo entra por los protocolos `MessageLog` y `ResumeSource`; `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py` y `core/verification/` no tienen diff; los errores y avisos son textos fijos sin el identificador ni el historial; la conexión, la suscripción y el comando están solo en `bootstrap.py`; el núcleo se prueba con dobles y SQLite solo en `tmp_path` (`tests/contracts/test_message_log_contract.py` corre la misma batería contra el doble y el adaptador); lo público está exportado en `core/__init__.py`; la reanudación falla cerrada y no filtra valores. La fila 8 (guardas en Windows y Linux) queda en la CI remota (H7) y la 12 en la revisión cruzada (H6): **dos «No» siguen en pie, ambos humanos**.

Ajustes frente al diseño, hallados al implementar (ninguno cambia un puerto, un evento ni un contrato de otra área):

- `clean_message(message, *, replacement=None)` y `ConversationCapture(log, *, warn, rejected_text)`: el texto estándar del rechazo lo **inyecta** la composición (`rejection_message(nombre, None)`), porque `core/context/` tiene prohibido importar `core.permissions` (guarda de HU-02-03).
- La captura **retiene** los resultados de cierre (`held`): el cierre del turno (`flush`) nunca los guarda sin su evento; solo los guarda su propio `tool_finished`. Sin esto un fallo a medias de la publicación dejaba un mensaje sin evento y la compactación posterior fallaba cerrada.
- `bind` mantiene el fallo de una sesión que ya falló (`session_id in incomplete_sessions`): no se vuelve a escribir en ella aunque `run_session` se ejecute de nuevo en la misma composición.
- `/reanudar` se registra en **todas** las composiciones; con tarea responde «Reanudar no está disponible en esta sesión.» (en lugar de ser un comando desconocido).
- Las líneas de tres pruebas existentes de la tabla se corrigieron al ajustarlas: la 5 es la 158 (no la 157), la segunda aserción de 7–8 es la 156 y la 23 es la 301.
- Se añadieron `tests/unit/resume_support.py` (siembra de sesiones en un archivo real y conducción de composiciones) y se reutilizan `Smart`, `process` y `rebuilt` de `tests/integration/test_resume_agent_loop.py`.

## Project Structure

### Documentation (this feature)

```text
specs/032-resume-session-by-id/
├── plan.md              # este archivo
├── research.md          # R1–R20 (decisiones y hallazgos)
├── data-model.md        # esquema 5 y tipos del núcleo
├── quickstart.md        # cómo validar
├── contracts/
│   ├── message_log_protocol.md  # protocolos del registro (escritura y lectura)
│   ├── capture_rules.md         # qué se guarda en cada evento, orden y fallos
│   ├── rebuild_rules.md         # reconstrucción, cobertura, cierre y ejemplos E1–E10
│   ├── resume_command.md        # comando, CLI, cambio de sesión y primer turno
│   └── error_messages.md        # mensajes fijos
├── checklists/requirements.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code y fila de `estructura-carpetas-harness` que justifica cada ruta

| Ruta | Fila de la tabla | Contenido |
|---|---|---|
| `src/harness_agent/core/context/conversation.py` (nuevo) | «Regla de negocio (…compactación…) → subpaquete de `core/`» | `MessageRecord`, `StoredMessage`, `MessageLog`, `clean_message` (redacción y rechazo sin motivo), `ConversationCapture` |
| `src/harness_agent/core/context/resume.py` (nuevo) | idem | `check_session_id`, `StoredConversation`, `ResumeSource`, `Resumed`, `rebuild_conversation`, `resume_session`, `check_structure` |
| `src/harness_agent/core/context/errors.py` (modifica) | «Error de dominio → `errors.py` del subpaquete» | `ResumeError` y subclases, `ConversationSaveError` |
| `src/harness_agent/core/context/__init__.py`, `core/__init__.py` (modifican) | «Todo lo público de `core/` se exporta» | nombres nuevos |
| `src/harness_agent/adapters/storage/message_store.py` (nuevo) | «Código con `sqlite3` → `adapters/<subpaquete>/`» | `SqliteMessageStore` |
| `src/harness_agent/adapters/storage/_schema.py`, `__init__.py` (modifican) | idem | `_V5`, versión 5; exporta `SqliteMessageStore` |
| `src/harness_agent/cli/app.py` (modifica, área **C**) | «Imprime o lee de la terminal → `cli/`» | `argument_commands` y ayuda |
| `src/harness_agent/bootstrap.py` (modifica) | «Unir piezas y elegir implementaciones → `bootstrap.py`» | suscripción, enlace, `/reanudar`, titular de sesión, cierres |
| `tests/unit/core/context/` (nuevos) | «`tests/` refleja `src/`» | `conversation_support.py`, `test_conversation_records.py`, `test_conversation_capture.py`, `test_conversation_capture_failures.py`, `test_resume_ids.py`, `test_resume_rebuild.py`, `test_resume_session.py`, `test_resume_properties.py` |
| `tests/unit/adapters/storage/` (nuevos) | idem | `test_schema_v5.py`, `test_message_store.py` |
| `tests/contracts/test_message_log_contract.py` (nuevo) | «prueba de contrato del adaptador» | doble en memoria y SQLite |
| `tests/unit/cli/test_app_argument_commands.py` (nuevo) | idem | comando con argumento y ayuda |
| `tests/unit/test_bootstrap_capture.py`, `test_bootstrap_resume.py`, `test_bootstrap_closure.py` (nuevos) | idem | cableado, orden y fallo del guardado; `/reanudar` y cambio de sesión; cierres y nada atado a la sesión abandonada |
| `tests/integration/test_resume_agent_loop.py`, `test_resume_cuts.py`, `test_resume_security.py`, `test_resume_errors.py` (nuevos) | pruebas con el `AgentLoop` real | AC-01 y AC-02; cortes y cierre idempotente; seguridad; errores y marca «sin detalle» |
| `tests/architecture/test_conversation_boundaries.py` (nuevo) | «guardas `ast` de la frontera nueva» | pureza, sin conexión propia, solo la composición suscribe y reanuda |
| `.claude/skills/` y `.agents/skills/` (`verificar-fronteras-hexagonales/SKILL.md`, `estructura-carpetas-harness/references/arbol.md`), `CLAUDE.md` | «si cambia una skill propia, actualizar ambas copias» | filas nuevas |

**Archivos protegidos que NO se tocan** (se verifica con `git diff` al cerrar): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/`, `core/context/{compactor,cut,summary,store,essential,renewer}.py`, `core/permissions/`, `adapters/storage/{compaction_archive,essential_store,task_store,event_recorder}.py`, `adapters/converters/`, `tests/doubles/`, `docs/archivo/`.

### Decisiones clave (detalle en `research.md`)

| # | Decisión | Dónde |
|---|---|---|
| 1 | Cada fila apunta al **identificador del evento** que la disparó; sin emparejar por orden | R2 |
| 2 | Cobertura de resúmenes derivada de las marcas de los eventos, con regla para los mensajes sin evento; una divergencia sin efecto (respuesta vacía en el corte) | R3 |
| 3 | El guardado se suscribe **antes** del registrador y es inerte hasta enlazarse | R4 |
| 4 | Pendientes por **identidad**; cuatro eventos y un vaciado al cerrar el turno; sin guardado en sesiones con tarea | R5 |
| 5 | Rechazo reconocido por `category == "approval_rejected"` de `tool_finished` (señal fiable, sin tocar el bucle) | R6 |
| 6 | Fallo al guardar: aviso fijo + `ConversationSaveError` → el turno falla (código 1); la sesión queda no reanudable | R7 |
| 7 | Redacción solo de URLs; la base ya está protegida; secretos generales = decisión del PO | R8 |
| 8 | Reconstrucción pura; réplica de la validación estructural del bucle | R9 |
| 9 | **Hallazgo**: el cierre sintético se publica como `tool_finished` real en la primera petición tras reanudar (si no, la compactación fallaría cerrada para siempre) | R10 |
| 10 | Cambio de sesión con un titular local y una fábrica del compactador; no se vuelve a componer | R12 |
| 11 | CLI: parámetro opcional `argument_commands` (y nada más en `cli/`) | R13, R25 |
| 12 | El cierre se **deriva del estado guardado** y se retira uno a uno al publicarse: una vez por llamada | R21 |
| 13 | Marca «sin detalle» no saltable: fallo pegajoso + memoria de la ejecución + ausencia de fila | R22 |
| 14 | Reanudar la sesión activa: `AlreadyCurrentSession`; dos procesos no soportado | R23 |
| 15 | Nada atado a la sesión abandonada (inventario y guarda `ast`) | R24 |

## Pruebas existentes que cambian (lista completa y exacta)

Búsqueda en `tests/` y **corrida en seco** del esquema 5 provisional (tabla `mensajes` y versión 5; `_schema.py` restaurado y verificado con `cmp`): **23 fallos**, 6 933 pasadas y 47 omitidas. Más una prueba por la API pública. **Regla**: ejecutarlas **antes, sin tocar**, y ver que fallan por la razón de la tabla; solo entonces se ajustan. **Cualquier otra prueba existente que falle: detener la implementación y avisar.**

| # | Prueba | Línea (hoy) | Por qué falla | Ajuste |
|---|---|---|---|---|
| 1 | `tests/unit/adapters/storage/test_schema.py::test_schema_version_is_current` | 46 | `SCHEMA_VERSION == 4` | `== 5` |
| 2 | `…/test_schema_migration.py::test_schema_version_is_two` | 84 | `SCHEMA_VERSION == 4` | `== 5` |
| 3 | `…/test_schema_migration.py::test_new_database_gets_the_criteria_tables` | 90 | `user_version == 4` | `== 5` |
| 4 | `…/test_schema_migration.py::test_version_one_database_migrates_without_losing_data` | 124 | `user_version == 4` | `== 5` |
| 5 | `…/test_schema_migration.py::test_unknown_versions_are_still_refused` | 158 | `PRAGMA user_version = 5` ya es válida | `= 6` |
| 6 | `…/test_schema_v3.py::test_the_version_is_three` | 140 | `SCHEMA_VERSION == 4` | `== 5` |
| 7–8 | `…/test_schema_v3.py::test_an_old_database_migrates_to_three_and_keeps_every_row[1]` y `[2]` | 153 y 156 | `user_version == 4` y la tabla nueva aparece en el volcado | `== 5` y una línea `assert after.pop("mensajes") == []` tras el `pop("contexto_esencial")` |
| 9–10 | `…/test_schema_v3.py::test_reopening_a_migrated_database_changes_nothing[1]` y `[2]` | 172 | `user_version == 4` | `== 5` |
| 11–12 | `…/test_schema_v3.py::test_a_migrated_database_has_the_same_table_as_a_new_one[1]` y `[2]` | 185 | `user_version == 4` | `== 5` |
| 13 | `…/test_schema_v4.py::test_the_version_is_four` | 161 | `SCHEMA_VERSION == 4` | `== 5` |
| 14–16 | `…/test_schema_v4.py::test_an_old_database_migrates_to_four_and_keeps_every_row[1]`, `[2]`, `[3]` | 172 y 174 | `user_version == 4` y la tabla nueva en el volcado | `== 5` y `assert after.pop("mensajes") == []` tras el `pop("contexto_esencial")` |
| 17–19 | `…/test_schema_v4.py::test_reopening_a_migrated_database_changes_nothing[1]`, `[2]`, `[3]` | 190 | `user_version == 4` | `== 5` |
| 20–22 | `…/test_schema_v4.py::test_a_migrated_database_has_the_same_tables_as_a_new_one[1]`, `[2]`, `[3]` | 202 | `user_version == 4` | `== 5` |
| 23 | `tests/integration/test_rejection_reason_agent_loop.py::test_the_reason_is_not_stored_in_the_database` | 301 | El conjunto exacto de tablas | Añadir `"mensajes"` (el resto de la prueba —los bytes de todos los archivos y las filas de `events`— no cambia) |
| 24 | `tests/unit/adapters/storage/test_public_api.py::test_all_lists_exactly_the_public_names` | 7–26 (`EXPECTED`) | El adaptador nuevo se exporta | Añadir `"SqliteMessageStore"` (la de importabilidad itera la misma lista y no falla) |

Total: **24 pruebas** (23 de la corrida en seco más la de la API pública) en **6 archivos**; los cambios son de una a dos líneas por prueba. Las 23 de esquema y de tablas (números 1 a 23) se ajustan en **T006**, la tarea del esquema; la 24 en **T007**. Las 23 de la corrida en seco ya se ejecutaron sin tocar y fallaron exactamente por esas razones; la 24 es de la API pública y se ejecutará antes de tocarla.

**Revisadas y sin cambio esperado** (se ejecutan sin tocar; si alguna falla se detiene la implementación):

| Qué fija | Dónde | Por qué no cambia |
|---|---|---|
| Que los eventos no llevan argumentos ni contenido | `tests/core/test_loop_events.py::test_payloads_follow_the_contract_and_carry_no_tool_arguments`, `tests/integration/test_permission_policy_agent_loop.py` (el valor del argumento no está en las cargas) | Los eventos y el bucle no cambian (Q1 = B) |
| Que el motivo del rechazo no está en ningún byte de la base | `tests/integration/test_rejection_reason_agent_loop.py` (resto) | El rechazo se guarda sin motivo; además esa prueba llama al bucle directamente y el guardado es inerte sin `run_session` (T010c repite la comprobación pasando por `run_session`) |
| Eventos y suscriptores del registrador | `test_event_recorder*.py`, `test_bootstrap_compose.py` | Ningún evento nuevo (los cierres usan `tool_finished`); el `skip` no cambia |
| Ayuda de la CLI | `tests/unit/cli/*`, `tests/integration/test_cli_agent_loop.py`, `test_bootstrap_verification.py` | `run_cli` sin `argument_commands` es idéntico; las pruebas de arranque con tarea no registran el comando |
| `history_prefix` y el recorte `[2:]` | `test_bootstrap_shell.py`, `test_bootstrap_git.py`, `test_bootstrap_main.py` | El prefijo no cambia |
| Sesiones con tarea y el bloque | `test_bootstrap_essential.py`, `test_essential_context_*.py`, `test_criteria_verification_agent_loop.py` | Las composiciones con tarea no instalan el guardado |
| Compactación | `test_compactor*.py`, `test_cut*.py`, `test_context_compaction_agent_loop.py`, `test_bootstrap_compaction.py` | La lógica no cambia; el guardado solo escribe en `mensajes` |
| `core.__all__` | `test_core_public_api.py`, `test_context_assembler_loop.py`, `test_cli_boundaries.py` | Comprueban inclusión y unicidad, no igualdad |
| Guardas de arquitectura de `bootstrap`/`adapters` | `test_bootstrap_boundaries.py`, `test_adapters_boundaries.py` | Solo importan la API pública de `core` y `adapters.storage` |

## Tabla FR / AC / SC → tarea → prueba

(No habrá `/speckit-analyze` en esta historia.) Tareas: ver «Estimación de tareas» y `tasks.md`.

| Requisito | Tarea | Prueba (archivo y qué comprueba) |
|---|---|---|
| FR-001 (comando con identificador; en la ayuda) | T008, T009b | `test_app_argument_commands.py` (el argumento llega; ayuda), `test_bootstrap_resume.py` (registrado siempre; con tarea responde que no está disponible) |
| FR-002 (identificador inexistente: mensaje fijo; sesión actual intacta) | T004, T005b, T009b, T010d | `test_resume_ids.py`, `test_resume_session.py`, `test_resume_errors.py` (historial y eventos de la sesión actual idénticos) |
| FR-003 (vacío, inválido, largo, control: sin consultar) | T004, T005b | `test_resume_ids.py` (E9), `test_resume_session.py` (el origen no se consulta) |
| FR-004 (ningún mensaje reproduce lo escrito ni el historial) | T004, T010c | `test_resume_ids.py`, `test_resume_security.py` (centinelas) |
| FR-005 (reconstruir mensajes con llamadas, argumentos, resultados, orden) | T002, T003, T005, T007, T009, T010 | `test_conversation_records.py`, `test_resume_rebuild.py` (E1), `test_message_store.py`, `test_bootstrap_capture.py`, `test_resume_agent_loop.py` |
| FR-006 (igual a la memoria; tres excepciones declaradas) | T005, T005b, T010 | `test_resume_properties.py` (azar), `test_resume_agent_loop.py` (con y sin compactación), `test_resume_rebuild.py` (E6, E7) |
| FR-007 (estructura válida para el bucle) | T004, T005 | `test_resume_ids.py` (`check_structure` frente a la validación real del bucle), `test_resume_rebuild.py` (el resultado la cumple) |
| FR-008 (no se republican eventos) | T009b, T010 | `test_bootstrap_resume.py` (el comando no emite), `test_resume_agent_loop.py` (0 eventos nuevos tras reanudar) |
| FR-009 (sin detalle; marca no saltable, también en la misma ejecución) | T003b, T005b, T007, T010d | `test_conversation_capture_failures.py` (fallo pegajoso), `test_resume_session.py` (`known_incomplete`), `test_message_store.py` (`events_without_row`), `test_resume_errors.py` (almacén que falla a mitad de un turno; base reabierta en archivo real y en otro proceso) |
| FR-010 (incoherencia: falla cerrada) | T004, T005, T010d | `test_resume_ids.py` (estructura), `test_resume_rebuild.py` (E8), `test_resume_errors.py` (filas borradas o alteradas: 0 llamadas al modelo) |
| FR-011 (prefijo de la composición actual; nada de prefijo/bloque/resumen en la tabla) | T003, T005b, T009, T010 | `test_conversation_capture.py` (no se guardan), `test_resume_session.py` (el prefijo), `test_bootstrap_capture.py`, `test_resume_agent_loop.py` |
| FR-012 (sesión de tarea rechazada) | T005b, T007, T010d | `test_resume_session.py`, `test_message_store.py` (criterios o contexto esencial), `test_resume_errors.py` (también la fila huérfana) |
| FR-013 (contexto = resumen vigente + no cubiertos; compactar si supera el umbral; primera petición incluida) | T005, T009b, T010 | `test_resume_rebuild.py` (E2, E3), `test_resume_agent_loop.py` (una llamada de resumen antes de la primera petición; cambio de modelo) |
| FR-014 (compactación sin cambios; correspondencia) | T010 | `test_resume_agent_loop.py`: tras reanudar la compactación real compacta y no falla cerrada |
| FR-015 (el comando no escribe) | T005, T009b, T010 | `test_resume_rebuild.py` (función pura), `test_bootstrap_resume.py` y comparación de todas las tablas antes/después de reanudar |
| FR-016 (misma sesión; siguiente `seq`; sin duplicados) | T009c, T010 | `test_bootstrap_closure.py`, `test_resume_agent_loop.py` (eventos anteriores idénticos, nuevos con `seq` continuo) |
| FR-017 (la sesión abandonada no se vuelve a escribir; nada atado a ella) | T009c, T010, T011 | `test_bootstrap_closure.py` (volcado idéntico; evento a mano con el identificador viejo sin filas), `test_resume_agent_loop.py`, guarda `ast` de `test_conversation_boundaries.py` |
| FR-018 (sesión activa: error; entre ejecuciones y ir y volver: mismo historial, 0 eventos) | T005b, T009b, T010d | `test_resume_session.py`, `test_bootstrap_resume.py`, `test_resume_errors.py` |
| FR-019 (llamada sin resultado: cierre sintético, persistido al continuar, una sola vez) | T005, T009c, T010b | `test_resume_rebuild.py` (E4), `test_bootstrap_closure.py`, `test_resume_cuts.py` (cierre idempotente, dos cortes, publicación a medias; la compactación posterior funciona) |
| FR-020 (aviso de corte; historial válido) | T005, T010b | `test_resume_rebuild.py` (línea de estado), `test_resume_cuts.py` (corte en cada punto) |
| FR-021 (sesión vacía) | T005, T005b, T010d | `test_resume_rebuild.py` (E10), `test_resume_session.py`, `test_resume_errors.py` |
| FR-022 (límites no se reinician) | T009b, T010 | `test_bootstrap_resume.py` / `test_resume_agent_loop.py` con `max_turns` bajo |
| FR-023 (una línea; sin repintar) | T005, T008, T009b | `test_resume_rebuild.py` (formato), `test_app_argument_commands.py`, `test_bootstrap_resume.py` (salida) |
| FR-024 (redacción y base protegida) | T002, T010c | `test_conversation_records.py` (URLs en contenido y argumentos), `test_resume_security.py` (el modelo no lee ni edita la tabla) |
| FR-025 (esquema aditivo, migración v1–v4) | T006, T007 | `test_schema_v5.py` (bases reales con DDL literal v1–v4, filas antes y después), `test_message_store.py` |
| FR-026 (nada protegido cambia; pruebas existentes; `cli/` solo `argument_commands`) | T001, T006, T007, T008, T011, T012 | Las 24 de la lista, ejecutadas antes sin tocar; `git diff` vacío de lo prohibido; `git diff --stat -- src/harness_agent/cli` solo `app.py` |
| FR-027 (proveedor simulado) | T010 | `test_resume_agent_loop.py` con `FakeProvider` que graba lo recibido |
| FR-028 (qué se guarda y cuándo) | T002, T003, T007, T009 | `test_conversation_capture.py`, `test_message_store.py`, `test_bootstrap_capture.py`, `test_resume_agent_loop.py` |
| FR-029 (solo mensajes reales) | T003, T009, T010c | `test_conversation_capture.py`, `test_bootstrap_capture.py`, `test_resume_security.py` (tras compactar y con salida de verificador simulada) |
| FR-030 (por identidad; una vez) | T003, T003b | `test_conversation_capture.py`, `test_conversation_capture_failures.py` (mismo evento repetido) |
| FR-031 (URLs ocultas; resultados ya recortados) | T002, T010c | `test_conversation_records.py`, `test_resume_security.py` (bytes de la base) |
| FR-032 (rechazo sin motivo) | T002, T003, T010c | `test_conversation_records.py`, `test_resume_security.py` (centinela del motivo en 0 bytes), prueba de contrato de la categoría |
| FR-033 (relación mensaje ↔ rangos de eventos) | T005, T007, T010 | `test_resume_rebuild.py` (E2, E3, E7), `test_message_store.py` (`covered`), `test_resume_agent_loop.py` (dos compactaciones) |
| FR-034 (mensaje antes que evento; fallo no silencioso) | T003b, T009, T010d | `test_conversation_capture_failures.py`, `test_bootstrap_capture.py` (orden de llamada y fallo), `test_resume_errors.py` (almacén que falla) |
| AC-01 (contexto reconstruido y el agente continúa) | T010 | `test_resume_agent_loop.py`: igual a la memoria, con y sin compactación; la primera llamada tras reanudar |
| AC-02 (se compacta si supera el umbral) | T010 | `test_resume_agent_loop.py`: sesión larga reanudada; una llamada de resumen antes de la primera petición |
| Regla 1 (historial completo, no el resumen; interpretación Q2 = B) | T005, T010 | El historial completo sigue guardado e intacto; vista = resumen vigente + no cubiertos |
| Regla 2 (identificador inexistente: error claro) | T004, T005b, T010d | `test_resume_ids.py`, `test_resume_errors.py` |
| SC-001, SC-003, SC-005 | T010 | `test_resume_agent_loop.py` |
| SC-002, SC-009 | T010d | `test_resume_errors.py` |
| SC-008 | T010c | `test_resume_security.py` |
| SC-004 | T010b | Corte en cada punto de un turno (5 o más) |
| SC-006 | T005b, T009b, T009c, T010b, T010d | Sesión activa, entre ejecuciones, ir y volver, cierre una sola vez |
| SC-007 | T010 | Una base real con 5 000 mensajes: lista en menos de 5 s |
| SC-010 | T005, T009b | Formato de la línea y salida de la terminal |
| SC-011 | T006, T012 | `test_schema_v5.py` y la suite completa |
| SC-012 | T002, T003, T010c | `test_conversation_records.py`, `test_conversation_capture.py`, centinelas sobre los bytes de la base |
| SC-013 | T003b, T009, T010d | Corte entre mensaje y evento: reanudable; evento sin mensaje: falla cerrada |

## Estimación de tareas (RITMO: 16 de implementación de ≤ 40 min, TDD, más inicio, guarda y cierre)

| Tarea | Contenido | Min | Sp2 |
|---|---|---|---|
| T001 | Inicio: línea base (suite 6 956 pasadas y 47 omitidas, ruff, mypy, 533 de arquitectura), sin cambios de código; las 24 pruebas pasan sin tocar; fila de HU-03-04 a `En curso` | 15 | — |
| T002 | `conversation.py` (1): `MessageRecord`, `StoredMessage`, `MessageLog`, `clean_message` (URLs en contenido, resultado y argumentos; rechazo sin motivo), errores (rojo primero) | 35 | Sp2-21 |
| T003 | `conversation.py` (2): `ConversationCapture`: `bind`, eventos, pendientes por identidad, `evento_id`, `flush`, inerte sin enlazar | 40 | Sp2-21 |
| T003b | Captura: fallos (aviso fijo, error fijo, estado intacto), fallo pegajoso e `incomplete_sessions`, cancelación no capturada, mismo evento repetido | 35 | Sp2-21 |
| T004 | `resume.py` (1): `check_session_id`, errores de mensaje fijo (incl. `AlreadyCurrentSession`), `StoredConversation`, `ResumeSource`, `check_structure` | 30 | Sp2-21 |
| T005 | `resume.py` (2): `Resumed`, `rebuild_conversation` (cobertura, resumen vigente, cierre de la cola, línea de estado) con los ejemplos E1–E8 y E10 | 40 | Sp2-21 |
| T005b | `resume_session` (sesión actual, `known_incomplete`, tarea, sin detalle, vacía, línea de estado) y azar de semilla fija (guardar y reconstruir) | 40 | Sp2-21 |
| T006 | Esquema 5 y migración con bases reales v1–v4 (DDL literal, filas antes/después); las 23 pruebas (sin tocar primero) | 40 | Sp2-21 |
| T007 | `SqliteMessageStore` (`append` atómico e idempotente, `load_conversation`) y prueba de contrato; la prueba 24 | 40 | Sp2-21 |
| T008 | `cli/app.py`: `argument_commands` y ayuda (área C; solo eso) con sus pruebas | 25 | Sp2-23 |
| T009 | `bootstrap.py` (1): suscribir el guardado antes del registrador, enlazar en `run_session`, `flush`, aviso fijo ante fallo; pruebas de orden | 40 | Sp2-21 |
| T009b | `bootstrap.py` (2): `/reanudar`, titular de sesión, fábrica del compactador, errores y sesión activa | 40 | Sp2-23 |
| T009c | `bootstrap.py` (3): cierres en la primera petición, uno a uno e idempotentes, y nada atado a la sesión abandonada | 35 | Sp2-23 |
| T010 | Integración central (AC-01, AC-02, igualdad con y sin compactación, dos compactaciones, misma sesión, 0 duplicados, límites, 5 000 mensajes) | 40 | Sp2-22 |
| T010b | Integración de cortes (cada punto de un turno, cierre idempotente, dos cortes, publicación a medias, compactación posterior) | 40 | Sp2-22 |
| T010c | Seguridad (centinelas, URLs, rechazo, el modelo no edita la tabla, qué no se guarda, repetir la marca) | 35 | Sp2-22 |
| T010d | Integración de errores (sin detalle: almacén que falla, archivo real y otro proceso; tarea; vacía; incoherente; sesión activa; inexistente) | 35 | Sp2-22 |
| T011 | Guarda de arquitectura, skills (dos copias), `arbol.md`, `CLAUDE.md`, lista de comprobación y detector de secretos | 30 | — |
| T012 | Cierre: cuatro puertas, cobertura, diff vacío de lo prohibido, `PROGRESO.md` (`En revisión`), evidencia | 30 | — |

Total de Claude: **665 min (11,1 h)**; las dieciséis de implementación suman 590 min frente a 420 min (7 h) de Sp2-21 a Sp2-23 (Sp2-21: 340 min frente a 180; Sp2-22: 150 frente a 120; Sp2-23: 100 frente a 120): **el presupuesto es una advertencia, no un límite**. La diferencia sale de persistir los mensajes (esquema, adaptador, guardado) que la ficha no contaba, y de partir las tareas que superaban 40 min. Una sola spec y una sola PR; orden: persistir (T002–T003b, T006–T007, T009), reconstruir (T004–T005b), comando y CLI (T008, T009b, T009c), integración y cierre (T010–T012).

## Tareas humanas (Claude no las marca)

- **H1**: acuerdo de A, B y C sobre la forma de lo persistido (tabla de mensajes desde la composición, sin tocar el bucle ni los eventos) y sobre la **interpretación de la regla 1** (Q2 = B). El usuario actúa como A: «autorizado por el usuario, pendiente de ratificar».
- **H2**: visto bueno de **B** al esquema 5 y al modo de leer resúmenes y marcas al reanudar.
- **H3**: visto bueno de **C** al cambio mínimo de `cli/app.py` y a `bootstrap.py` (suscripción, enlace, comando, titular de sesión, cierres).
- **H4**: el **PO** decide si el contenido de los resultados de herramientas puede guardarse en disco sin redacción general (HU-10-02 no existe), y los topes de tamaño.
- **H5**: el **PO** ratifica la interpretación de Q2, que solo se reanudan sesiones sin tarea, que los contadores de límites no se reinician en la misma ejecución, que una sesión sin mensajes se reanuda como nueva, que el cierre de llamadas se publica como un `tool_finished` real al continuar (R10, una vez por llamada, R21) y que dos procesos sobre la misma sesión no se soportan (R23).
- **H6**: revisión cruzada por B o C (la historia es de A).
- **H7**: CI remota en `ubuntu-latest` y `windows-latest`, con push y PR confirmados por una persona.
- **H8**: avisos. **B** (HU-02-03): la reanudación reutiliza la compactación sin cambios y se apoya en las marcas y en `resumenes`; **B** (HU-02-06.1): las sesiones de tarea se rechazan; **C** (HU-06-04): el comando con argumento es el primero y la CLI mostrará la línea genérica de error para la categoría `tool_interrupted` (mejora de su texto); **B** (HU-03-03): el estado guardado de la sesión nunca cambia; **A y B** (HU-10-02): ya se guardan resultados de herramientas en disco y la redacción general deberá cubrirlos.

## Complexity Tracking

| Desviación / aviso | Por qué hace falta | Alternativa más simple rechazada porque |
|---|---|---|
| V-13 se cumple solo en parte (redacción de URLs, no de claves en general) | HU-10-02 (redacción general) no existe; `core/redaction.py` es lo único que hay y no se puede ampliar aquí | No guardar resultados de herramientas (opción C de la pregunta 1) degradaba AC-01; la decisión es del PO (H4) y la base ya está protegida por la política |
| Protocolos propios en `core/context/` en vez de un puerto en `core/interfaces/` | Cambiar un puerto exige acuerdo de A, B y C | Un puerto nuevo bloquearía la historia hasta el acuerdo; el patrón ya existe (HU-02-03, HU-02-06.1) |
| `bootstrap.py` crece (suscripción, enlace, comando, titular, cierres) | Es la única raíz de composición; no hay otro lugar donde unir bus, historial, almacén y CLI | Volver a componer duplicaría el registrador de eventos y los contadores (R12) |
| Cierre de llamadas publicado como `tool_finished` con categoría `tool_interrupted` | Sin evento el compactador de HU-02-03 falla cerrado para siempre en esa sesión (R10) | Tocar el compactador (prohibido) o aceptar la degradación silenciosa |
| Dos excepciones más a la igualdad con la memoria (credenciales ocultas; respuesta vacía en el corte) | Coste/riesgo de la alternativa exacta (R3, R8) | Un segundo mecanismo de cobertura o no redactar |
| El presupuesto del sprint (7 h) se supera (11,1 h) | La ficha no contaba persistir los mensajes | Partir en dos historias (lo decidió el usuario: una spec y una PR) |
| Cambio en `cli/` (área C) | El mecanismo de comandos no pasa argumentos | Un comando por línea de arranque (fuera de alcance) |
