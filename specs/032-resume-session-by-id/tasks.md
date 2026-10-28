# Tasks: HU-03-04 — Reanudar una sesión por identificador

**Input**: `specs/032-resume-session-by-id/` (spec.md con Clarifications, plan.md, research.md R1–R26, data-model.md, contracts/ ×5, quickstart.md)
**Rama**: `gustavo` (sin commit, push ni cambio de rama por parte de Claude)
**Responsable**: A — Núcleo (la implementa Claude; el usuario actúa como A) | **PHU**: 3 (ficha) | **Sprint**: 2
**Tareas de referencia**: Sp2-21, Sp2-22, Sp2-23

## Cómo leer este documento

- **Regla RITMO**: 3 PHU y 7 h de sprint, pero el alcance real (persistir los mensajes, reconstruir, comando y CLI, integración) pide **16 tareas de implementación de ≤ 40 min** (T002–T010d, con T003b, T005b, T009b, T009c, T010b, T010c y T010d), agrupadas por módulo, más el inicio (T001), la guarda y documentación (T011) y el cierre (T012). **El presupuesto del sprint es una advertencia, no un límite.** Si una tarea supera 40 min, se parte sin recortar alcance.
- **TDD dentro de cada tarea**:
  1. escribir las pruebas;
  2. ejecutarlas y ver el **rojo por la razón esperada** (anotarlo en la evidencia);
  3. implementar lo mínimo;
  4. pasar `ruff format --check .`, `ruff check .`, `mypy src tests` y las pruebas del módulo con cobertura (100 % de líneas y ramas del módulo nuevo al terminar la última tarea que lo toca).
- **Formato**: `- [ ] Tnnn [USn] descripción con ruta`.
  - US1: reanudar una sesión anterior y continuar donde quedó (FR-001, FR-005, FR-006, FR-008, FR-011, FR-013, FR-016, FR-028 a FR-033; AC-01).
  - US2: error claro cuando el identificador no existe o no es válido (FR-002 a FR-004, FR-009, FR-012, FR-018; regla 2).
  - US3: compactar al reanudar si el contexto supera el umbral (FR-013, FR-014; AC-02).
  - US4: un corte abrupto no deja un historial inválido (FR-007, FR-010, FR-019 a FR-021).
  - US5: reanudar no cambia lo guardado y no duplica eventos (FR-015, FR-017, FR-024 a FR-027, FR-034).
  - US6: un aviso breve al reanudar, sin repintar la conversación (FR-023).
- **Decisiones añadidas al plan** (research R21 a R26, de `/speckit-tasks`):
  1. (R21) El cierre `tool_interrupted` se **deriva del estado guardado** y se publica **una sola vez** por llamada interrumpida: reanudar dos veces sin petición no escribe; reanudar, pedir y reanudar de nuevo no duplica; dos cortes consecutivos se cierran cada uno una vez; cada cierre sale de la lista pendiente solo tras publicarse.
  2. (R22) La marca «sin detalle» no se puede saltar: el guardado falla de forma **pegajosa** (tras un fallo no escribe más en esa sesión) y recuerda `incomplete_sessions`; `/reanudar` rechaza la sesión tanto si falta una fila (marca en la base, también con la base reabierta y desde otro proceso) como si el guardado falló en esa ejecución.
  3. (R23) Reanudar la sesión activa da `Esa ya es la sesión actual.` sin leer ni escribir; **dos procesos sobre la misma sesión: no soportado** (supuesto de la spec y observación de `PROGRESO.md`).
  4. (R24) Tras `/reanudar` nada escribe en la sesión abandonada (compactador reemplazado, guardado reenlazado y que ignora otras sesiones, cierres con `active.session_id`); guarda `ast`: dentro de `run_session` ninguna función interna usa `composition.session_id`.
  5. (R25) Los cambios en `cli/` se limitan al parámetro opcional `argument_commands` (y su uso para `/reanudar` y la ayuda); **cualquier otro cambio en `cli/` es un hallazgo: detenerse y avisar**.
  6. (R26) Los contratos, la spec y el plan ya reflejan estas decisiones.
- **Mensajes fijos** (exactos; ver `contracts/error_messages.md`):
  - `Uso: /reanudar <identificador de la sesión>.`
  - `El identificador de sesión no es válido.`
  - `Esa ya es la sesión actual.`
  - `No existe una sesión con ese identificador.`
  - `Las sesiones de tarea no se pueden reanudar todavía.`
  - `Esa sesión se guardó sin el detalle de sus mensajes y no se puede reanudar.`
  - `Los mensajes guardados de la sesión no son coherentes y no se puede reanudar.`
  - `No se pudo leer la sesión; la sesión actual sigue sin cambios.`
  - `Reanudar no está disponible en esta sesión.`
  - `No se pudo guardar un mensaje de la conversación; la sesión no podrá reanudarse.`
  - cierre sintético: `[tool_interrupted] La ejecución se interrumpió antes de obtener el resultado; verifique el estado antes de repetirla.`
  - rechazo estándar guardado: `[approval_rejected] Tool '<nombre>' was rejected by the user.`
- **Lo que no se toca** (diff vacío al cerrar): `src/harness_agent/core/loop.py`, `core/interfaces/`, `core/events.py`, `core/in_memory_event_bus.py`, `core/redaction.py`, `core/permissions/`, `core/tasks/`, `core/verification/`, `core/context/{compactor,cut,summary,store,essential,renewer,estimator,settings,prefix,assembler}.py`, `adapters/storage/{compaction_archive,essential_store,task_store,event_recorder,criteria_export,sqlite_session_store}.py`, `adapters/converters/`, `adapters/providers/`, `adapters/tools/`, `adapters/system/`, `tests/doubles/`, `docs/archivo/`. En `cli/` solo cambia `app.py` y solo por `argument_commands` (R25).
- **Pruebas existentes que cambian** (y solo estas 24; ejecutarlas **antes, sin tocar**, y ver que fallan por la versión del esquema, por la tabla nueva o por el nombre exportado; solo entonces ajustar las líneas declaradas y registrarlas como «autorizado por el usuario, pendiente de ratificar»):

  | # | Prueba | Línea | Ajuste | Tarea |
  |---|---|---|---|---|
  | 1 | `tests/unit/adapters/storage/test_schema.py::test_schema_version_is_current` | 46 | `SCHEMA_VERSION == 4` → `== 5` | T006 |
  | 2 | `tests/unit/adapters/storage/test_schema_migration.py::test_schema_version_is_two` | 84 | `== 4` → `== 5` | T006 |
  | 3 | `…/test_schema_migration.py::test_new_database_gets_the_criteria_tables` | 90 | `user_version == 4` → `== 5` | T006 |
  | 4 | `…/test_schema_migration.py::test_version_one_database_migrates_without_losing_data` | 124 | `user_version == 4` → `== 5` | T006 |
  | 5 | `…/test_schema_migration.py::test_unknown_versions_are_still_refused` | 158 | `PRAGMA user_version = 5` → `= 6` | T006 |
  | 6 | `tests/unit/adapters/storage/test_schema_v3.py::test_the_version_is_three` | 140 | `SCHEMA_VERSION == 4` → `== 5` | T006 |
  | 7–8 | `…/test_schema_v3.py::test_an_old_database_migrates_to_three_and_keeps_every_row[1]` y `[2]` | 153 y 156 | `user_version == 4` → `== 5` y una línea `assert after.pop("mensajes") == []` tras el `pop("contexto_esencial")` | T006 |
  | 9–10 | `…/test_schema_v3.py::test_reopening_a_migrated_database_changes_nothing[1]` y `[2]` | 172 | `user_version == 4` → `== 5` | T006 |
  | 11–12 | `…/test_schema_v3.py::test_a_migrated_database_has_the_same_table_as_a_new_one[1]` y `[2]` | 185 | `user_version == 4` → `== 5` | T006 |
  | 13 | `tests/unit/adapters/storage/test_schema_v4.py::test_the_version_is_four` | 161 | `SCHEMA_VERSION == 4` → `== 5` | T006 |
  | 14–16 | `…/test_schema_v4.py::test_an_old_database_migrates_to_four_and_keeps_every_row[1]`, `[2]`, `[3]` | 172 y 174 | `user_version == 4` → `== 5` y `assert after.pop("mensajes") == []` tras el `pop("contexto_esencial")` | T006 |
  | 17–19 | `…/test_schema_v4.py::test_reopening_a_migrated_database_changes_nothing[1]`, `[2]`, `[3]` | 190 | `user_version == 4` → `== 5` | T006 |
  | 20–22 | `…/test_schema_v4.py::test_a_migrated_database_has_the_same_tables_as_a_new_one[1]`, `[2]`, `[3]` | 202 | `user_version == 4` → `== 5` | T006 |
  | 23 | `tests/integration/test_rejection_reason_agent_loop.py::test_the_reason_is_not_stored_in_the_database` | 301 | el conjunto de tablas gana `"mensajes"` (el resto de la prueba no cambia) | T006 |
  | 24 | `tests/unit/adapters/storage/test_public_api.py::test_all_lists_exactly_the_public_names` | 7–26 (`EXPECTED`) | gana `"SqliteMessageStore"` | T007 |

  - **Revisadas y sin cambio esperado** (se ejecutan sin tocar; si una falla, es un hallazgo): `tests/core/test_loop_events.py` y `tests/integration/test_permission_policy_agent_loop.py` (los eventos no llevan argumentos), el resto de `test_rejection_reason_agent_loop.py`, `test_event_recorder*.py`, `test_bootstrap_compose.py`, todo `tests/unit/cli/`, `test_cli_agent_loop.py`, `test_bootstrap_verification.py`, `test_bootstrap_main.py`, `test_bootstrap_shell.py`, `test_bootstrap_git.py`, `test_bootstrap_essential.py`, `test_essential_context_*.py`, `test_criteria_verification_agent_loop.py`, `test_compactor*.py`, `test_cut*.py`, `test_context_compaction_agent_loop.py`, `test_bootstrap_compaction.py`, `test_core_public_api.py`, `test_bootstrap_boundaries.py` y `test_adapters_boundaries.py`.
  - **Cualquier otra prueba existente que falle: detente y avisa con la razón antes de ajustarla.**
- **Caracteres ocultos**: en `specs/` y `docs/` escribe `U+202E` y `U+200B` como texto. En código y pruebas se construyen con `chr(0x202E)`, `chr(0x200B)` y `chr(27)`, nunca con secuencias `\u...` en el texto que escribe la herramienta.
- **Finales de línea**: todo archivo de `specs/` y `docs/` en CRLF, con scripts que lean y escriban bytes; nunca `sed -i`. Rutas siempre relativas al repositorio.
- **Secretos**: ninguna asignación con forma de clave ni URL con credenciales literales; se arman por partes (`"https://" + "usuario" + ":" + "clave" + "@servidor.example/repo.git"`). Detector a mano sobre todos los archivos nuevos y modificados (`secret_patterns_in` de `tests/architecture/test_no_secrets_in_repo.py`).
- **Sin red**: todo con `FakeProvider` (o un proveedor de prueba local en el archivo cuando haga falta responder según el contexto recibido); las bases de datos son archivos en `tmp_path`.
- **Dobles de prueba**: viven en `tests/unit/core/context/conversation_support.py` (se crea en T002 y se amplía en T005b); `tests/doubles/` no se toca.
- **Ventanas de prueba**: la compactación de las pruebas de integración usa un `ContextSettings` pequeño (como `test_context_compaction_agent_loop.py`) para que dos compactaciones ocurran con pocos mensajes.

## Mapeo a tareas del sprint

| Tarea | Descripción (03-plan-sprints) | Presupuesto | Tareas aquí |
|---|---|---|---|
| **Sp2-21** | Reconstruir el contexto desde los eventos | 180 min | T002 (35), T003 (40), T003b (35), T004 (30), T005 (40), T005b (40), T006 (40), T007 (40), T009 (40) |
| **Sp2-22** | Aplicar compactación si hace falta | 120 min | T010 (40), T010b (40), T010c (35), T010d (35) |
| **Sp2-23** | Comando de reanudar | 120 min | T008 (25), T009b (40), T009c (35) |
| — | Inicio, guarda/documentación y cierre | — | T001 (15), T011 (30), T012 (30) |

**Total de Claude: 665 min** (T001 15 + T002 35 + T003 40 + T003b 35 + T004 30 + T005 40 + T005b 40 + T006 40 + T007 40 + T008 25 + T009 40 + T009b 40 + T009c 35 + T010 40 + T010b 40 + T010c 35 + T010d 35 + T011 30 + T012 30) frente a 420 min presupuestados en Sp2-21 a Sp2-23. **Humanas: H1–H8.**

---

## Phase 1: Inicio

- [x] T001 Inicio (15 min). Sin cambios de código:
  - **Línea base**: ejecutar las cuatro puertas y las guardas tal como están (`ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest --cov=harness_agent --cov-report=term-missing -q -rs` y `pytest tests/architecture -q`), todas en exit 0; anotar los conteos reales (pruebas pasadas y omitidas, archivos de `ruff` y `mypy`, pruebas de arquitectura) en la evidencia al final de este archivo. Esperado: 6 956 pasadas y 47 omitidas, 533 de arquitectura, 387 archivos.
  - Ejecutar **sin tocar** las 24 pruebas de la lista de arriba con el esquema 4 vigente: deben pasar (es la línea base de lo que luego cambia).
  - `docs/PROGRESO.md` (solo documentación; CRLF puro; un script que lea y escriba bytes y conserve los CRLF, derivado del que se usó para HU-02-06.1 cambiando el prefijo por `| [HU-03-04](04b-historias-estado.md#hu-03-04) |` y la cabecera por `**Observaciones de HU-03-04**:`): la fila **existente** de HU-03-04 pasa de `Pendiente` a `En curso` (responsable A; la implementa Claude en `gustavo`; `specs/032-resume-session-by-id/`), una línea en *Registro de cambios* y un bloque **Observaciones de HU-03-04** con dos viñetas (alcance y decisiones Q1 = B, Q2 = B —interpretación de la regla 1 pendiente de ratificar— y Q3 = A; y el hallazgo de que los eventos no bastan). No se toca ninguna otra fila ni la tabla *Resumen*.
  - Comprobar que `.specify/feature.json` apunta a `specs/032-resume-session-by-id`.

  **Hecho cuando**: la línea base está anotada y en verde, las 24 pruebas pasan sin tocar, la fila está en `En curso` y `PROGRESO.md` sigue en CRLF puro con una sola fila existente modificada. **Cubre**: FR-026 (parte), Principio VIII.

---

## Phase 2: Registro de mensajes — núcleo puro (US1, US5 · Sp2-21)

- [x] T002 [US1] [US5] Registro de un mensaje, redacción y rechazo sin motivo (35 min). Cubre FR-005 (parte), FR-024, FR-028 (parte), FR-031, FR-032 y SC-012 (parte). Archivos:
  - `src/harness_agent/core/context/errors.py`: `ConversationSaveError(Exception)` con el mensaje fijo de guardado (sin recibir ni repetir valores);
  - nuevo `src/harness_agent/core/context/conversation.py` (parte 1): `MessageRecord` (`@dataclass(frozen=True)`: `position`, `message`, `event_id`), `StoredMessage` (`record`, `covered: bool | None`), `MessageLog` (`Protocol`: `append`, `last_position`) y `clean_message(message, *, rejected_tool=None) -> Message`: devuelve una **copia** con `hide_url_credentials` aplicado al contenido, al contenido del `ToolResult` y a **cada valor de texto de los argumentos** (recursivo en listas y diccionarios, sin tocar claves ni valores que no son texto); con `rejected_tool` el contenido (del mensaje y de su `ToolResult`) pasa a ser `rejection_message(rejected_tool, None)`; conserva `call_id`, `is_error`, `is_external` y `usage`;
  - exportaciones en `core/context/__init__.py` y `core/__init__.py`;
  - nuevo `tests/unit/core/context/conversation_support.py` con `InMemoryMessageLog` (graba lotes, puede fallar a pedido), un grabador de avisos y un constructor de mensajes y eventos que imita el orden del bucle (se añade primero el mensaje y después se publica el evento).

  Pruebas primero, `tests/unit/core/context/test_conversation_records.py`:
  - `MessageRecord` y `StoredMessage` son inmutables;
  - una credencial de URL armada por partes sale con `<secreto oculto>` en el contenido, en el contenido de un resultado y en un argumento anidado (lista dentro de diccionario); la clave **no** está en ningún valor; un entero o un booleano no cambian; el original no se muta;
  - rechazo: el contenido de un `TOOL` que lleva el motivo centinela `VALOR-DE-PRUEBA-123` sale como `[approval_rejected] Tool 'shell' was rejected by the user.` en el mensaje **y** en su `ToolResult`; `call_id`, `is_error` e `is_external` se conservan; el centinela no está en la copia;
  - sin `rejected_tool`, un texto que empieza por `[approval_rejected]` (de un archivo leído) **no** se toca;
  - `ConversationSaveError` tiene exactamente el mensaje fijo y no lleva causa.

  **Rojo esperado**: `ImportError` de los símbolos nuevos de `harness_agent.core.context.conversation`. **Hecho cuando**: `clean_message`, los tipos y el error al 100 %; `core/redaction.py`, `core/loop.py` y `core/interfaces/` sin diff.

- [x] T003 [US1] [US5] La captura de mensajes: enlazar, pendientes por identidad y eventos (40 min). Cubre FR-005, FR-011, FR-028, FR-029, FR-030, FR-032 y SC-012 (parte). Archivos:
  - `src/harness_agent/core/context/conversation.py` (parte 2): `ConversationCapture(log, *, warn)` con `bind(session_id, history, next_position, saved_count)`, `on_event(event)`, `flush()` y la propiedad `incomplete_sessions` (vacía por ahora); reglas de `contracts/capture_rules.md`: inerte hasta enlazar, ignora eventos de otra sesión, pendientes = mensajes **reales** (`is_real`) después del último guardado localizado **por identidad**, `evento_id` solo al mensaje que corresponde al evento (`user_message`, `assistant_message`, `tool_finished` por `call_id`), `tool_requested` y `flush` sin `evento_id`, rechazo reconocido por `payload["category"] == "approval_rejected"`, posición siguiente que solo avanza si el lote se guardó;
  - exportaciones en `core/context/__init__.py` y `core/__init__.py`.

  Pruebas primero, `tests/unit/core/context/test_conversation_capture.py` (con los dobles de T002 y una secuencia que imita el orden del bucle):
  - sin enlazar no escribe nada; con un evento de otra sesión tampoco;
  - turno con herramientas: petición (`evento_id`), respuesta solo con llamadas (guardada al `tool_requested`, sin `evento_id`), dos resultados (cada uno con su `evento_id`), respuesta final con texto (con `evento_id`): 5 registros, posiciones 1 a 5 consecutivas;
  - respuesta final vacía: se guarda solo con `flush()`, sin `evento_id`; `flush()` sin pendientes no escribe;
  - dos mensajes **iguales** se guardan los dos (identidad); un evento repetido no guarda de nuevo;
  - **compactación en medio**: la lista se reemplaza in situ con un resumen (`USER` externo) y el bloque (`SYSTEM`) de por medio; el siguiente turno guarda solo lo nuevo y ni el resumen ni el bloque ni el prefijo ni una salida de verificador (`USER` externo) llegan al registro;
  - rechazo: un `tool_finished` con categoría `approval_rejected` guarda el texto estándar y el centinela del motivo no está en ningún registro; otra categoría con el mismo texto no se toca;
  - `bind` a una sesión reanudada con `saved_count` fija el último guardado y no vuelve a guardar los mensajes cargados.

  **Rojo esperado**: `AttributeError`/`ImportError` de `ConversationCapture`. **Hecho cuando**: los caminos felices en verde, `conversation.py` al 100 % de lo ejercido (el 100 % total llega con T003b); `core/loop.py` sin diff.

- [x] T003b [US5] Fallos del guardado: aviso fijo, fallo pegajoso y sin detalle (35 min). Cubre FR-009 (parte), FR-030, FR-034 y SC-013 (parte). Archivos: `src/harness_agent/core/context/conversation.py` y `tests/unit/core/context/test_conversation_capture_failures.py`.

  Pruebas primero:
  - un almacén que falla en el 3.er lote: se escribe **una** línea fija por el avisador y sale `ConversationSaveError` (mensaje fijo, sin el centinela del contenido, sin `__cause__` ni contexto encadenado); el último guardado y la posición no cambian;
  - **fallo pegajoso (R22)**: el evento siguiente lanza `ConversationSaveError` **sin llamar al almacén** y sin repetir el aviso; `incomplete_sessions` contiene la sesión; `bind` a otra sesión permite guardar de nuevo y **conserva** el recuerdo;
  - incoherencias que fallan con el mismo error fijo: el último guardado ya no está en el historial; `user_message` cuyo último pendiente no es una petición; `tool_finished` con un `call_id` que no está pendiente; contenido del mensaje distinto del de su `ToolResult`;
  - `CancelledError` y `KeyboardInterrupt` del almacén **no** se capturan, no hacen el fallo pegajoso y dejan el estado intacto;
  - el mismo evento entregado dos veces tras un éxito no duplica; tras un fallo siguen sin escribirse mensajes posteriores.

  **Rojo esperado**: el fallo no se avisa y se propaga la excepción cruda del almacén; no existe el estado pegajoso (`incomplete_sessions` vacío). **Hecho cuando**: `conversation.py` al 100 % de líneas y ramas; sin captura de `BaseException`.

---

## Phase 3: Reconstrucción pura (US1, US2, US3, US4 · Sp2-21)

- [x] T004 [US2] Identificador, errores de reanudar, datos leídos y validación estructural (30 min). Cubre FR-002, FR-003, FR-004, FR-007, FR-010 (parte) y la regla 2. Archivos:
  - `src/harness_agent/core/context/errors.py`: `ResumeError(Exception)` y sus subclases `InvalidSessionId`, `AlreadyCurrentSession`, `UnknownSession`, `TaskSessionNotResumable`, `SessionDetailMissing`, `ConversationInconsistent`, cada una con su **mensaje fijo exacto** de `contracts/error_messages.md` (ninguna recibe ni repite un valor);
  - nuevo `src/harness_agent/core/context/resume.py` (parte 1): `check_session_id(text) -> str`, `StoredConversation` (`@dataclass(frozen=True)`: `session_id`, `model`, `is_task`, `messages: tuple[StoredMessage, ...]`, `summary`, `events_without_row`, `last_event_type`), `ResumeSource` (`Protocol`: `load_conversation`) y `check_structure(messages) -> str | None` (réplica de la validación del bucle: `SYSTEM` solo al principio, identificadores de llamada no vacíos y únicos, cada grupo contestado por completo antes de otro mensaje, ningún resultado sin llamada);
  - exportaciones en `core/context/__init__.py` y `core/__init__.py`.

  Pruebas primero, `tests/unit/core/context/test_resume_ids.py`:
  - E9 de `rebuild_rules.md`: `""` y solo espacios → `InvalidSessionId` con el texto de uso; `"../x"`, 129 caracteres, salto de línea, carácter de control, `chr(0x200B)` y `chr(0x202E)` → el texto de «no es válido»; 128 caracteres y `"a-B_9.x"` → aceptado y sin espacios exteriores; un valor que no es texto → «no es válido»;
  - los siete mensajes de reanudar y el de guardado coinciden **carácter a carácter** con `error_messages.md`; con un centinela en el identificador ninguno lo contiene;
  - `check_structure`: historial válido; `SYSTEM` en medio; identificador repetido; identificador vacío; grupo sin contestar; resultado huérfano; resultados en cualquier orden aceptados; **coincide con la validación real del bucle** (`AgentLoop._check_history`, solo en la prueba) sobre un conjunto de historiales válidos e inválidos.

  **Rojo esperado**: `ImportError` de `harness_agent.core.context.resume`. **Hecho cuando**: lo nuevo de `errors.py` y `resume.py` (parte 1) al 100 %; `core/loop.py` sin diff.

- [x] T005 [US1] [US3] [US4] Reconstrucción pura: cobertura, resumen vigente, cierre de la cola y línea de estado (40 min). Cubre FR-005, FR-006, FR-007, FR-010, FR-013, FR-015 (parte), FR-019 (parte), FR-020, FR-021, FR-023, FR-033, la regla 1 y SC-010. Archivos: `src/harness_agent/core/context/resume.py` (parte 2: `Resumed`, `SYNTHETIC_RESULT_TEXT`, `rebuild_conversation(prefix, stored, current_model) -> Resumed`, línea de estado) y exportaciones.

  Pruebas primero, `tests/unit/core/context/test_resume_rebuild.py`:
  - los ejemplos **E1 a E8 y E10** de `contracts/rebuild_rules.md` **mensaje a mensaje** (E1 sin compactar: 7 mensajes; E2 una compactación: `[P, 1, resumen, 4, 5, 6]`; E3 dos compactaciones con el resumen vigente de mayor `evento_hasta`; E4 corte entre llamada y resultado con `saved_count`, `closed_calls` y `cut_off`, y con dos cierres si ninguna llamada tiene resultado; E5 petición sin respuesta; E6 rechazo guardado sin motivo; E7 la divergencia declarada de la respuesta vacía en el corte; E8 incoherencias → `ConversationInconsistent`; E10 sesión vacía);
  - el resumen es `frame_summary(texto)` y es igual al de la vista viva; el historial completo (`messages`) no se modifica;
  - el texto del cierre sintético es exactamente el del contrato, con el mismo `call_id`, `is_error` y sin contenido externo; una llamada sin resultado **en medio** → `ConversationInconsistent`;
  - la regla de cobertura: fila sin evento toma la del siguiente con evento; primera fila cubierta, filas cubiertas sin resumen y resumen sin filas cubiertas → incoherente;
  - la línea de estado de la tabla del contrato (normal, con resumen, vacía, con corte, con interrupción, con modelo distinto) y que ninguna contiene identificador, contenido ni nombres de herramientas;
  - determinista (dos llamadas iguales) y el resultado pasa `check_structure`.

  **Rojo esperado**: `ImportError` de `rebuild_conversation`. **Hecho cuando**: `resume.py` (parte 2) al 100 %; los ejemplos coinciden mensaje a mensaje (si uno no se pudiera cumplir tal como está escrito, detente y dime cuál y por qué).

- [x] T005b [US2] [US5] `resume_session` y la prueba al azar de guardar y reconstruir (40 min). Cubre FR-002, FR-003, FR-006, FR-009, FR-011, FR-012, FR-018, FR-021 y SC-006 (parte). Archivos: `src/harness_agent/core/context/resume.py` (`resume_session(source, text, *, prefix, current_model, current_session_id, known_incomplete=frozenset()) -> Resumed`), exportaciones, `tests/unit/core/context/conversation_support.py` (se amplía con `InMemoryConversationSource`, que modela eventos y marcas de cobertura) y los archivos de prueba de abajo.

  Pruebas primero, `tests/unit/core/context/test_resume_session.py`:
  - orden de las comprobaciones (R23): identificador inválido → es la sesión actual → está en `known_incomplete` → no existe → es de tarea → falta detalle → reconstruir; **la fuente no se consulta** en los tres primeros casos (espía);
  - sesión de tarea (con `is_task`) → `TaskSessionNotResumable`; `events_without_row > 0` → `SessionDetailMissing`; sesión vacía → historial igual al prefijo y `empty`; modelo guardado distinto → `model_changed`;
  - un identificador de `known_incomplete` → `SessionDetailMissing` **aunque la fuente devuelva una sesión coherente**.

  Pruebas primero, `tests/unit/core/context/test_resume_properties.py` (semilla 20261101): historiales válidos generados (peticiones, respuestas con y sin texto, grupos de llamadas, errores, contenido externo) pasados por `ConversationCapture` y el doble de la fuente con compactaciones simuladas: lo reconstruido es la vista viva (salvo las excepciones declaradas: la prueba las genera aparte), nunca queda un resultado huérfano ni una llamada sin resultado, la reconstrucción es determinista y cortar el guardado en cualquier punto da un historial reconstruible o un error fijo de dominio.

  **Rojo esperado**: `ImportError` de `resume_session`. **Hecho cuando**: `resume.py` al 100 %; las propiedades pasan con la semilla fija.

---

## Phase 4: El esquema 5 y el adaptador (US1, US5 · Sp2-21)

- [x] T006 [US1] [US5] Esquema 5 y migración desde bases reales v1–v4 (40 min). Cubre FR-025, FR-026 (parte) y SC-011. Archivos: `src/harness_agent/adapters/storage/_schema.py` (`SCHEMA_VERSION = 5`, `_V5` con el DDL de `data-model.md`, `_STEPS[5]`, docstring) y las 23 pruebas existentes de la lista (1 a 23).

  Orden de trabajo:
  1. **Pruebas primero**, nuevo `tests/unit/adapters/storage/test_schema_v5.py`: bases **reales** creadas con el DDL **literal** de cada versión 1 a 4 (copiado como texto en la prueba, no importado de `_schema`) y rellenas (sesiones, eventos, criterios, resúmenes, contexto esencial); abrirlas con el almacén y comprobar **fila por fila antes y después** que cada tabla anterior queda idéntica y `mensajes` vacía, `user_version == 5`, reabrir no cambia nada, el DDL de `mensajes` es el de una base nueva, los `CHECK` (rol, fila `tool` con `resultado_id` y `resultado_error`, `llamadas` solo en `assistant`, posición ≥ 1), la clave primaria, la clave foránea a la sesión y el índice `idx_mensajes_evento`, y una versión 6 se rechaza sin modificarse. Rojo: versión 4.
  2. Implementar el esquema.
  3. **Ejecutar las 23 pruebas existentes sin tocar**: deben fallar **exactamente** por la versión o por la tabla nueva de la lista (la corrida en seco ya lo mostró: 23 fallos y nada más). Si falla otra, detente y avisa.
  4. Ajustarlas línea por línea como dice la tabla («autorizado por el usuario, pendiente de ratificar») y comprobar que todo el archivo y la suite completa quedan en verde.

  **Hecho cuando**: `test_schema_v5.py` y las 23 ajustadas en verde; `_schema.py` al 100 %; el resto de la suite igual que la línea base; ninguna otra prueba existente tocada.

- [x] T007 [US1] [US5] `SqliteMessageStore`, prueba de contrato y la prueba 24 (40 min). Cubre FR-005, FR-009, FR-012, FR-025, FR-026 (parte), FR-028, FR-033. Archivos: nuevo `src/harness_agent/adapters/storage/message_store.py` (`SqliteMessageStore(store, *, clock)` con `append`, `last_position` y `load_conversation`, sobre `store.connection()`), `src/harness_agent/adapters/storage/__init__.py` (exporta `SqliteMessageStore`) y la prueba existente 24.

  Pruebas primero:
  - `tests/unit/adapters/storage/test_message_store.py`: `append` atómico (un lote con una fila inválida no guarda ninguna); idempotente (fila idéntica con la misma posición se ignora; distinta falla con el error fijo, sin contenido); argumentos y resultados ida y vuelta por JSON; fila dañada o rol desconocido → `SessionStoreError` fijo; `last_position`; `load_conversation`: `None` sin sesión, `is_task` por filas en `criterios` o en `contexto_esencial` (con los almacenes reales), `events_without_row`, `last_event_type` sin contar `context_compacted`, `summary` = el de mayor `evento_hasta`, `covered` de cada fila con **compactaciones reales** (`SqliteCompactionArchive.commit_compaction`), una fila con `evento_id` de un evento que nunca se guardó sale con `covered = None`; almacén cerrado → `SessionStoreError`; sin conexión propia (usa la del almacén);
  - `tests/contracts/test_message_log_contract.py`: la misma batería de `contracts/message_log_protocol.md` contra el doble en memoria de `conversation_support.py` y contra `SqliteMessageStore`;
  - la prueba 24: ejecutarla **antes, sin tocar** (pasa); tras exportar el adaptador falla por la lista `EXPECTED`; ajustarla («autorizado por el usuario, pendiente de ratificar»).

  **Rojo esperado**: `ImportError` de `SqliteMessageStore`. **Hecho cuando**: `message_store.py` al 100 %; el contrato en verde con ambos; la 24 ajustada; `adapters/storage/{compaction_archive,essential_store,task_store,event_recorder,sqlite_session_store}.py` sin diff.

---

## Phase 5: El comando y el cableado (US1, US2, US4, US5, US6 · Sp2-21, Sp2-23)

- [x] T008 [P] [US6] Comando con argumento en la CLI (25 min, área **C**). Cubre FR-001, FR-023 (parte), FR-026 (parte). Archivos: `src/harness_agent/cli/app.py` (**solo** `argument_commands`, R25) y nuevo `tests/unit/cli/test_app_argument_commands.py`. No depende de T002–T007.

  Pruebas primero:
  - el comando recibe el texto después del nombre, sin espacios exteriores, y puede ser vacío (`""`); lo que devuelve se escribe con una línea;
  - aparece en `/ayuda` después de los comandos de `commands` y antes de la línea final; coexiste con `commands`;
  - **sin** `argument_commands` todo es idéntico: `HELP_TEXT`, el mensaje de comando desconocido y los códigos de salida (las pruebas existentes de `tests/unit/cli/` y `test_cli_agent_loop.py` pasan **sin tocar**);
  - los parámetros de `run_cli` son exactamente los anteriores más `argument_commands`;
  - una función que lanza una excepción ordinaria se propaga como lo hace hoy una de `commands` (no se añade captura).

  **Rojo esperado**: `TypeError` por el parámetro inesperado. **Hecho cuando**: `git diff --stat -- src/harness_agent/cli` lista **solo** `app.py` y el diff contiene solo el parámetro, su alias de tipo, la rama de despacho y la línea de ayuda; si hace falta cualquier otro cambio, **detente y avisa**. No se exporta nada nuevo en `__all__`.

- [x] T009 [US1] [US5] Cableado del guardado de mensajes (40 min). Cubre FR-005, FR-011, FR-028, FR-029, FR-034, SC-013. Archivos: `src/harness_agent/bootstrap.py` (`Composition.capture` y `Composition.messages`; en `compose` sin tarea: `SqliteMessageStore(store)` y `ConversationCapture(log, warn=warning_sink.write)` suscrita a `user_message`, `assistant_message`, `tool_requested` y `tool_finished` **justo antes** de `attach_event_recorder`; con tarea no se instala; en `run_session`: `bind` con la lista del historial y la posición siguiente, y `flush()` en un `finally` de `run_turn` cuyo propio fallo escribe el aviso fijo sin ocultar la excepción original) y nuevo `tests/unit/test_bootstrap_capture.py`.

  Pruebas primero:
  - **orden**: con espías en el almacén de eventos y en el registro de mensajes, para cada uno de los cuatro tipos la llamada a `append` ocurre **antes** que `save_event` y que la escritura de la CLI;
  - fallo del registro a mitad de un turno (se sustituye `SqliteMessageStore` por una subclase que falla con `monkeypatch`): la línea fija sale **una** vez, el registrador **sí** guardó el evento (la tabla `events` lo tiene y `mensajes` no), `run_cli` termina con código 1 y el centinela del contenido no está en la salida;
  - inerte sin enlazar: `composition.loop.run_turn(...)` directo no escribe filas; con `run_session` sí;
  - con tarea no hay captura ni suscripción;
  - la respuesta final vacía se guarda por el `flush` del cierre de turno;
  - las pruebas existentes de arranque (`test_bootstrap_compose.py`, `test_bootstrap_main.py`, etc.) pasan **sin tocar**.

  **Rojo esperado**: `AttributeError` de `Composition.capture`. **Hecho cuando**: el código nuevo de `bootstrap.py` al 100 %; `test_bootstrap_boundaries.py` en verde sin tocar.

- [x] T009b [US1] [US2] [US6] `/reanudar`, titular de sesión y fábrica del compactador (40 min). Cubre FR-001, FR-002, FR-008, FR-013, FR-015, FR-018, FR-022, FR-023, SC-006 (parte), SC-010. Archivos: `src/harness_agent/bootstrap.py` (`Composition.compactor_for`, `Composition.model` y el origen de lectura; en `run_session`: titular local `active` con `session_id` y `compactor`, la lista del historial reemplazada **en sitio**, el manejador de `/reanudar` registrado con `argument_commands` en toda composición (con tarea responde que no está disponible); el manejador convierte cada error de dominio en su mensaje fijo, `SessionStoreError` en el de lectura y nunca lanza) y nuevo `tests/unit/test_bootstrap_resume.py`.

  Pruebas primero:
  - el comando está registrado y en `/ayuda`; con tarea responde «Reanudar no está disponible en esta sesión.» y no cambia nada;
  - cada error (vacío, inválido, inexistente, tarea, sin detalle, incoherente, lectura que falla) devuelve su línea fija y **no cambia** el historial (misma lista, mismo contenido), el titular ni el enlace del guardado;
  - éxito: la lista se reemplaza **en sitio**, `active.session_id` cambia, `compactor_for` se llama con el identificador pedido, el guardado queda enlazado a la sesión nueva con la posición siguiente correcta, la salida es **una línea**, y **ninguna tabla cambia** (volcado completo antes y después idéntico) ni se publica ningún evento;
  - reanudar el identificador de la sesión activa → «Esa ya es la sesión actual.» sin leer ni escribir; reanudar `X`, luego `X` → ese error; reanudar `Y` y luego `X` → funciona (R21, R23);
  - los contadores de límites **no** se reinician (un `max_turns` agotado sigue deteniendo la petición siguiente tras reanudar);
  - `Composition.essential` es `None` en toda composición reanudable.

  **Rojo esperado**: el comando no existe (`Comando desconocido`). **Hecho cuando**: lo nuevo de `bootstrap.py` al 100 %; `_compactor` y `core/context/compactor.py` sin diff.

- [x] T009c [US4] [US5] Cierres en la primera petición, idempotentes, y nada atado a la sesión abandonada (35 min). Cubre FR-016, FR-017, FR-019, SC-006. Archivos: `src/harness_agent/bootstrap.py` (en el `run_turn` de `run_session`, antes de compactar y de llamar al bucle: publicar un `tool_finished` por cada cierre pendiente de `active`, **retirando cada uno solo después de publicarlo**) y nuevo `tests/unit/test_bootstrap_closure.py`.

  Pruebas primero:
  - tras reanudar una sesión con una llamada sin resultado **no hay ningún evento ni fila nuevos** hasta la primera petición; reanudar dos veces (con `Y` en medio) sin pedir nada tampoco escribe;
  - primera petición: **exactamente un** `tool_finished` con categoría `tool_interrupted`, `is_error` verdadero y el `call_id`, y **una** fila de `mensajes` con el texto fijo y su `evento_id`; el `seq` y la posición continúan sin huecos; reanudar otra vez después **no** cierra nada y no duplica (R21);
  - dos cortes consecutivos en la misma sesión: cada uno se cierra **una vez**;
  - publicación a medias: un suscriptor que falla en el segundo cierre deja el primero publicado y el segundo pendiente; la excepción sale; al reanudar solo falta el segundo;
  - **nada atado a la sesión abandonada (R24)**: el volcado de `events`, `mensajes` y `resumenes` de la sesión A es idéntico antes y después de reanudar B y hacer una petición con compactación; los eventos nuevos, las filas y el resumen llevan el identificador de B; un evento publicado a mano con el identificador de A no crea ninguna fila de `mensajes`; el compactador activo es el que devolvió la fábrica.

  **Rojo esperado**: no se publica ningún cierre (el historial queda con la llamada sin resultado). **Hecho cuando**: `bootstrap.py` al 100 % de lo nuevo; la prueba de compactación posterior al cierre no falla cerrada.

---

## Phase 6: La sesión de punta a punta (US1–US6 · Sp2-22)

- [x] T010 [US1] [US3] [US5] Integración central: AC-01, AC-02 y misma sesión (40 min). Cubre FR-005, FR-006, FR-008, FR-011, FR-013 a FR-017, FR-022, FR-027, FR-033, AC-01, AC-02, la regla 1, SC-001, SC-003, SC-005, SC-007. Archivo: nuevo `tests/integration/test_resume_agent_loop.py` (`compose()`, `run_session`, bases en `tmp_path`, `FakeProvider`/proveedor local que graba lo recibido).

  Pruebas:
  - **AC-01 con y sin compactación**: una sesión simulada con peticiones, herramientas (leer un archivo del área, un resultado de error, contenido externo) y respuestas; la prueba lleva su propio `history` (imitando `run_session`: renovación no aplica, compactación y bucle) y compara, **mensaje a mensaje**, el historial en memoria justo antes de salir con el reconstruido, con cero, una y **dos** compactaciones; las únicas diferencias admitidas son las tres excepciones declaradas, cada una con su caso aparte;
  - **continuar**: por `run_session` con `/reanudar <id>` y una petición, la primera llamada del proveedor recibe el historial reconstruido más la petición; los eventos anteriores son idénticos byte a byte (`SELECT` completo antes y después), los nuevos van en **la misma sesión** con `seq` continuo, sin duplicados, y reanudar no escribió nada;
  - **AC-02**: sesión larga reanudada → exactamente **una** llamada de resumen antes de la primera petición y el contexto enviado queda por debajo del umbral; sesión corta → 0 llamadas; con un modelo distinto de la configuración (otro umbral) la primera petición compacta o no según el umbral nuevo; después de reanudar la compactación **funciona** (no hay `provider_error` por no coincidir mensajes y eventos);
  - límites: con `max_turns` bajo, reanudar no los reinicia;
  - **SC-007**: una base con 5 000 mensajes (insertados en bloque con SQL, con sus eventos) se reconstruye y queda lista en menos de 5 s.

  **Rojo esperado**: sin guardado ni comando, `/reanudar` es desconocido y la tabla está vacía. **Hecho cuando**: AC-01 y AC-02 en verde con el bucle real; el historial completo sigue guardado e intacto tras reanudar.

- [x] T010b [US4] Integración de cortes y cierre idempotente (40 min). Cubre FR-019, FR-020, SC-004, SC-006. Archivo: nuevo `tests/integration/test_resume_cuts.py`.

  Pruebas:
  - una sesión completa con herramientas se **corta en cada punto** (después de la petición, después de la respuesta solo con llamadas, después de `tool_requested`, entre dos resultados de un grupo, después del último resultado, después de la respuesta final y entre el guardado de un mensaje y el de su evento: siete puntos en total) recortando eventos y filas como lo dejaría una muerte del proceso; en todos el historial reconstruido pasa `check_structure` y la validación real del bucle, **nunca** lleva una llamada sin resultado hacia el modelo, y el aviso de corte aparece cuando corresponde;
  - **cierre idempotente (R21)**: reanudar dos veces sin pedir, reanudar-pedir-reanudar, y dos cortes consecutivos: en cada caso, por `call_id`, un solo `tool_finished` de cierre y una sola fila;
  - publicación a medias: con una excepción en el segundo cierre, al reanudar se cierra solo el que falta;
  - la compactación posterior a un cierre **funciona** (resumen escrito, marcas, sin fallar cerrada);
  - una cancelación real (`BlockingTool` y `task.cancel()`) deja el evento de interrupción y la línea de estado dice que se había interrumpido.

  **Rojo esperado**: las llamadas sin resultado llegan al modelo o la compactación posterior falla cerrada. **Hecho cuando**: SC-004 y SC-006 en verde.

- [x] T010c [US5] Integración de seguridad (35 min). Cubre FR-004, FR-024, FR-029, FR-031, FR-032, SC-008, SC-012. Archivo: nuevo `tests/integration/test_resume_security.py` (patrón de `test_essential_context_security.py`).

  Pruebas:
  - con centinelas en el texto del historial, en argumentos, en resultados y en el identificador, **0** apariciones en eventos (salvo lo que el bucle ya publica por diseño), mensajes de error, avisos y salida de la terminal por esta historia;
  - una credencial de URL armada por partes en una petición, en un argumento y en un resultado: **0** apariciones en los bytes del archivo de la base (`rglob` y `read_bytes`, como la prueba de HU-05-04) y el marcador oculto presente; lo reconstruido lleva el marcador;
  - el **motivo de un rechazo** (centinela) pasando por `run_session`: 0 bytes en la base y el mensaje reconstruido es el estándar; prueba de contrato de la categoría `approval_rejected` del bucle;
  - la tabla no contiene el prefijo, el bloque, el resumen ni una salida de verificador simulada;
  - **el modelo no puede leer ni editar la tabla**: `leer_archivo`, `escribir_archivo`, `buscar_texto`, `listar_archivos` y el shell sobre la base reciben `[permission_denied]`; ninguna declaración de herramienta nombra `mensajes`; la tabla no cambia;
  - un texto que repite la marca de un resumen o del bloque no hace que se guarde como tal ni sustituye nada.

  **Rojo esperado**: sin redacción las credenciales aparecen en los bytes y el motivo se guarda. **Hecho cuando**: SC-008 y SC-012 en verde.

- [x] T010d [US2] [US4] Integración de errores y marca «sin detalle» (35 min). Cubre FR-002, FR-009, FR-010, FR-012, FR-018, FR-021, FR-034, SC-002, SC-006 (parte), SC-009, SC-013, la regla 2. Archivo: nuevo `tests/integration/test_resume_errors.py`.

  Pruebas:
  - inexistente, vacío, inválido, 129 caracteres, salto de línea, con centinela: mensaje fijo, sin eco, y la sesión actual (historial, eventos, filas) idéntica antes y después; **sesión activa**: «Esa ya es la sesión actual.» sin escribir;
  - **sesión de tarea** (`compose(task=…)` crea una sesión con criterios y contexto esencial): rechazada con el mensaje fijo, y **también la fila huérfana** (se borran las filas de `contexto_esencial`, quedan los criterios); 0 llamadas al modelo;
  - **sin detalle**: una sesión anterior a la historia (eventos sin filas) → mensaje fijo;
  - **marca no saltable (R22)**: (a) un almacén de mensajes que falla a mitad de un turno (archivo real en `tmp_path`, el registrador sí guarda el evento): `run_cli` termina con 1; una **conexión nueva** al archivo y luego **otro proceso** (`subprocess` con `sys.executable -I -c`, que abre el almacén y llama a la reanudación) obtienen el mensaje de «sin detalle»; (b) en la **misma ejecución** (fallan a la vez el mensaje y el evento y la base parece coherente), tras cambiar a otra sesión, `/reanudar` del identificador que falló sigue rechazado por `known_incomplete`; (c) tras el fallo no se guardó ningún mensaje más de esa sesión;
  - incoherente: filas borradas o alteradas (rol, orden, resultado huérfano) → mensaje fijo y 0 llamadas al modelo;
  - sesión vacía: se reanuda como nueva con el aviso y el prefijo; un evento de mensaje sin su fila falla cerrado y un mensaje sin su evento (cola) se reanuda.

  **Rojo esperado**: sin la comprobación, la sesión incompleta se reanuda a medias. **Hecho cuando**: SC-002, SC-009 y SC-013 en verde.

---

## Phase 7: Guardas, documentación y cierre

- [x] T011 Guardas de arquitectura y documentación (30 min). Cubre FR-017 (guarda de la sesión abandonada) y FR-026. Archivos:
  - nuevo `tests/architecture/test_conversation_boundaries.py` (autoprueba con fragmentos sintéticos y mutación sobre una copia en `tmp_path`; reutiliza los detectores de las guardas existentes, no los copia): `core/context/conversation.py` y `resume.py` solo stdlib y núcleo, sin E/S, entorno, terminal ni `sqlite3`, sin importar el bucle, `adapters`, `cli`, `core.permissions`, `core.tasks` ni `core.verification`; ningún `async`; nunca capturan `BaseException` ni `CancelledError`; `adapters/storage/message_store.py` sin conexión propia (`.connection()`), sin importar el bucle y sin definir `SessionStore`; **solo la composición** construye `ConversationCapture`, suscribe y llama a `resume_session` (en todo `src/`); en `bootstrap.py` la suscripción del guardado va **antes** de `attach_event_recorder`; dentro de `run_session` ninguna función interna usa `composition.session_id` (R24); `cli/app.py` no importa nada nuevo del núcleo;
  - skills (dos copias idénticas, `.claude/skills/` y `.agents/skills/`): fila nueva en `verificar-fronteras-hexagonales/SKILL.md`; `core/context/{conversation,resume}.py`, `adapters/storage/message_store.py` y el esquema 5 en `estructura-carpetas-harness/references/arbol.md`;
  - `CLAUDE.md`: fila de HU-03-04 en «Qué existe hoy» y nota en las convenciones (el guardado de mensajes se suscribe antes del registrador; el cierre `tool_interrupted`; solo sesiones sin tarea; `argument_commands`; dos procesos no soportado);
  - revisar contra el código la lista de comprobación de `capas-y-reglas.md` de `plan.md` y anotar cualquier «no» (script que conserve CRLF);
  - **detector de secretos** a mano sobre todos los archivos nuevos y modificados y **caracteres ocultos y CRLF** en `specs/032-resume-session-by-id/` y `docs/`.

  **Rojo esperado de la guarda**: las mutaciones (una copia de `resume.py` con `except BaseException`, con `async def`, importando el bucle; una copia del adaptador con `sqlite3.connect`; una copia de `bootstrap.py` con la suscripción tras el registrador o con `composition.session_id` dentro de `run_session`) la hacen fallar. **Hecho cuando**: `pytest tests/architecture` en verde con la guarda nueva; las dos copias de las skills idénticas (`cmp`); sin hallazgos del detector.

- [x] T012 Cierre (30 min). Cubre FR-026 y SC-011. Depende de T011.
  - Ejecutar las cuatro puertas: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`, todas en exit 0; anotar los conteos reales respecto de la línea base de T001, el 100 % de líneas y ramas de `conversation.py`, `resume.py`, `message_store.py`, `_schema.py` y del código nuevo de `bootstrap.py` y `cli/app.py`, y `pytest tests/architecture`.
  - Comprobar `git diff --exit-code $(git merge-base HEAD origin/main) -- <lo que no se toca, de arriba>` → 0; `git diff --stat -- src/harness_agent/cli` → solo `app.py`; y revisar a mano que las únicas pruebas existentes modificadas son las 24 de la lista de arriba.
  - Repetir el detector de secretos y la comprobación de caracteres ocultos y CRLF **después** de escribir `PROGRESO.md`.
  - En `docs/PROGRESO.md` (CRLF puro, **una fila** de HU-03-04 que pasa a **`En revisión`**, nunca `Hecha`; sin reescribir filas ajenas ni la tabla *Resumen*) con *Archivos* y *Evidencia* reales, una línea por tarea en *Registro de cambios* y, en la fila y en el bloque **Observaciones de HU-03-04**:
    1. **los eventos no bastan para reconstruir el historial** (los mensajes sin evento, los argumentos, los resultados, `is_external` y `usage` no se guardaban) y se añadió la **tabla de mensajes** (esquema 5, Q1 = B) alimentada desde la composición **sin tocar el bucle ni los eventos**;
    2. **interpretación de la regla 1** (Q2 = B: resumen vigente más mensajes no cubiertos; el historial completo sigue guardado) **pendiente de ratificar por el PO y por A** (el usuario actúa como A);
    3. **resultados de herramientas en disco sin redacción general** (HU-10-02 no existe): V-13 se cumple **solo en parte** (credenciales de URL); decisión del PO sobre guardar su contenido;
    4. **solo se reanudan sesiones sin tarea**; `main()` no carga tareas hoy; las sesiones de tarea (también la fila huérfana) se rechazan con un mensaje claro;
    5. las **sesiones anteriores al esquema 5 no se reanudan** (error claro, nunca una reconstrucción parcial);
    6. la **marca «sin detalle»**: un fallo al guardar un mensaje detiene el turno (código 1), el guardado es pegajoso y la sesión se rechaza al reanudar, también desde otra ejecución u otro proceso; límite: si fallan a la vez mensaje y evento y nada más se guarda, no se distingue de un corte normal;
    7. el **cierre `tool_interrupted`**: la llamada sin resultado se cierra con un `tool_finished` real **una sola vez** en la primera petición tras reanudar (sin él la compactación fallaría cerrada para siempre); la CLI muestra la línea genérica de error para esa categoría (aviso a C);
    8. **dos procesos sobre la misma sesión: no soportado**;
    9. el **cambio de sesión con un titular local** y una fábrica del compactador (sin volver a componer; los contadores de límites no se reinician; la sesión abandonada queda tal cual y nada la vuelve a escribir);
    10. **`argument_commands`** en `cli/app.py` para el visto bueno de C (único cambio en `cli/`); la CLI **no repinta** el historial al reanudar;
    11. las 24 pruebas existentes ajustadas («autorizado por el usuario, pendiente de ratificar»), la nota de proceso con los rojos observados y lo **pendiente** (H1–H8).
  - Marcar en este archivo solo T001–T012 (con sus letras) con su evidencia (tabla al final), con un script que conserve los CRLF; H1–H8 quedan sin marcar.

  **Hecho cuando**: las cuatro puertas en verde, el diff de lo que no se toca vacío, el detector sin hallazgos, sin caracteres ocultos y `PROGRESO.md` en CRLF con una sola fila de HU-03-04 en `En revisión`.

---

## Phase 8: Tareas humanas (Claude no las marca)

- [ ] H1 **Acuerdo de A, B y C** sobre la forma de lo persistido (tabla de mensajes alimentada desde la composición, sin tocar el bucle ni los eventos) y sobre la **interpretación de la regla 1** (Q2 = B). El usuario actúa como A: «autorizado por el usuario, pendiente de ratificar».
- [ ] H2 **Visto bueno de B** al esquema 5 de `adapters/storage/` (tabla `mensajes`, migración aditiva desde 1, 2, 3 y 4) y al modo de leer resúmenes y marcas al reanudar.
- [ ] H3 **Visto bueno de C** al cambio mínimo de `cli/app.py` (`argument_commands`, único cambio en `cli/`) y a `bootstrap.py` (suscripción antes del registrador, enlace, comando, titular de sesión, cierres).
- [ ] H4 El **PO decide** si el contenido de los resultados de herramientas puede guardarse en disco sin redacción general (HU-10-02 no existe; V-13 solo en parte) y con la base ya protegida frente a las herramientas por la política, y los topes de tamaño de lo guardado.
- [ ] H5 El **PO ratifica** la interpretación de la regla 1 (Q2 = B), que solo se reanudan sesiones sin tarea (Q3 = A), que los contadores de límites no se reinician dentro de la misma ejecución, que una sesión sin mensajes se reanuda como nueva, que el cierre de llamadas se publica como un `tool_finished` real al continuar (una vez por llamada) y que dos procesos sobre la misma sesión no se soportan.
- [ ] H6 **Revisión cruzada** por B o C (la historia es de A).
- [ ] H7 **CI remota** en verde en `ubuntu-latest` y `windows-latest`, con push y PR confirmados por una persona.
- [ ] H8 **Avisos**: a **B** (HU-02-03) la reanudación reutiliza la compactación sin cambios y se apoya en las marcas y en `resumenes`; a **B** (HU-02-06.1) las sesiones de tarea se rechazan al reanudar; a **C** (HU-06-04) el comando con argumento es el primero y la CLI muestra la línea genérica de error para `tool_interrupted`; a **B** (HU-03-03) el estado guardado de la sesión nunca cambia; a **A y B** (HU-10-02) ya se guardan resultados de herramientas en disco y la redacción general deberá cubrirlos.

---

## Dependencias y orden

```text
T001 ─▶ T002 ─▶ T003 ─▶ T003b ─▶ T004 ─▶ T005 ─▶ T005b ─▶ T006 ─▶ T007 ─┐
T001 ─▶ T008 [P] ───────────────────────────────────────────────────────┤
                                                                        ▼
                              T009 ─▶ T009b ─▶ T009c ─▶ T010 ─▶ T010b ─▶ T010c ─▶ T010d ─▶ T011 ─▶ T012 ─▶ (H1–H8)
```

- Es casi una cadena porque cada tarea añade exportaciones a `core/context/__init__.py` y `core/__init__.py` y la siguiente usa lo anterior: T003 usa `MessageRecord` y `clean_message` de T002; T005 usa `StoredConversation` y `check_structure` de T004; T005b usa `rebuild_conversation` de T005 y la captura de T003 para la prueba al azar; T007 usa los tipos de T002 y T004 y el esquema de T006; T009 usa la captura (T003b) y el almacén (T007); T009b usa `resume_session` (T005b), el almacén (T007) y `argument_commands` (T008); T009c usa el titular de T009b; T010 a T010d usan todo lo anterior.
- **T008 es paralelizable** con T002–T007 (solo toca `cli/app.py` y su prueba); se ejecuta antes de T009b.
- **US1** (reanudar y continuar): T002, T003, T005, T006, T007, T009, T009b, T010. **US2** (error claro): T004, T005b, T009b, T010d. **US3** (compactar): T005, T009b, T010. **US4** (corte abrupto): T005, T009c, T010b, T010d. **US5** (no cambia lo guardado y no duplica): T002, T003, T003b, T005b, T006, T007, T009, T009c, T010, T010c. **US6** (aviso breve): T005, T008, T009b.

## Estrategia de implementación

1. **MVP**: T001–T007. El registro, la captura, la reconstrucción y el almacén ya guardan y reconstruyen con falsos y con SQLite, sin comando.
2. **Incremento**: T008 a T009c (CLI y cableado: el comando funciona) y T010 a T010d (de punta a punta, cortes, seguridad y errores).
3. **Cierre**: T011 y T012. Después, H1–H8 son humanas y la historia no pasa a `Hecha` hasta completarlas y ratificar HU-00-01.

---

## Evidencia

Resultados reales (2026-10-28). Línea base de T001: 6956 pasadas y 47 omitidas, 533 pruebas de arquitectura, ruff y mypy limpios (387 archivos).

| Tarea | Rojo observado | Resultado |
|---|---|---|
| T001 | — (sin cambios de código) | Línea base anotada; las 24 pruebas pasan sin tocar; la fila pasa a `En curso` |
| T002 | `ImportError` de `ConversationSaveError` | `clean_message`, los tipos y el error; 7 pruebas |
| T003 | `ImportError` de `ConversationCapture` | Caminos felices; 10 pruebas |
| T003b | 8 fallos y 2 pasadas (excepción cruda, sin aviso ni estado pegajoso) | `conversation.py` al 100 % |
| T004 | `ImportError` del módulo `resume` | Identificador, errores, `check_structure` igual a la validación del bucle |
| T005 | `ImportError` de `rebuild_conversation` | Ejemplos E1-E8 y E10 mensaje a mensaje; `resume.py` al 100 % |
| T005b | `ImportError` de `resume_session`; mutando la regla de «sin evento» fallan 3, sin el cierre de la cola 4 | Pruebas al azar de semilla 20261101 (120 historias y cortes en cada evento) |
| T006 | 27 fallos de `test_schema_v5.py`; luego las 23 existentes fallan **exactamente** (23 fallos y 7076 pasadas) | 23 ajustadas; el resto sin cambios |
| T007 | `ImportError` de `SqliteMessageStore`; la 24 pasa sin tocar y falla al exportar | `message_store.py` al 100 %; contrato con ambos |
| T008 | 7 fallos por el parámetro inesperado | `cli/app.py` 100 %; solo `argument_commands` |
| T009 | 7 fallos y un error (no existen `capture` ni `SqliteMessageStore` en `bootstrap`) | Orden mensaje → evento → CLI, fallo del almacén, inerte sin enlazar |
| T009b | 13 fallos («Comando desconocido: '/reanudar'») | 14 pruebas; `bootstrap.py` al 100 % |
| T009c | 6 fallos (el cierre no se publicaba); luego una prueba halló que el cierre del turno guardaba el resultado sin su evento (rojo y corrección con la captura que retiene) | 9 pruebas; compactación posterior al cierre |
| T010 | Primera ejecución en verde; no vacía: sin `bind` fallan 9 y sin publicar el cierre fallan 6 | 12 pruebas; AC-01, AC-02 y 5 000 mensajes |
| T010b | Primera ejecución en verde (12 con las de T010) | 12 pruebas de cortes |
| T010c | Mutaciones: sin sustituir el rechazo fallan 2, sin ocultar las credenciales fallan 3 | 6 pruebas |
| T010d | Una expectativa corregida (4 filas, no 2) | 20 pruebas, con archivo real y un proceso hijo |
| T011 | — | 36 pruebas de la guarda; 569 de arquitectura |
| T012 | — | `ruff format --check .` y `ruff check .` en exit 0; `mypy src tests` sin errores (411 archivos); `pytest --cov=harness_agent --cov-branch` en exit 0: 7263 pasadas y 47 omitidas; 569 de arquitectura; 100 % de líneas y ramas de `conversation.py`, `resume.py`, `message_store.py`, `_schema.py`, `bootstrap.py` y `cli/app.py`; diff de lo protegido vacío; `cli/` solo `app.py` |

Pruebas existentes modificadas, **autorizadas por el usuario y pendientes de ratificar**: las 24 de la lista (`test_schema.py`, `test_schema_migration.py`, `test_schema_v3.py`, `test_schema_v4.py`, `test_rejection_reason_agent_loop.py` y `test_public_api.py`); tres líneas de la tabla se corrigieron al ajustarlas (la 5 es la 158, la segunda de 7-8 la 156 y la 23 la 301).

Pendientes humanos: H1-H8, sin marcar.
