# Tasks: HU-02-06.1 — Contexto esencial persistente fuera del historial compactable

**Input**: `specs/031-essential-context-block/` (spec.md con Clarifications, plan.md, research.md R1–R20, data-model.md, contracts/ ×5, quickstart.md)
**Rama**: `gustavo` (sin commit, push ni cambio de rama por parte de Claude)
**Responsable**: B — Estado | **PHU**: 1 | **Sprint**: 2
**Tareas de referencia**: Sp2-18, Sp2-19, Sp2-20

## Cómo leer este documento

- **Regla RITMO**: 1 PHU, pero el alcance real (módulos puros, adaptador y esquema, cableado, falla cerrada y seguridad) pide **12 tareas de implementación de ≤ 40 min** (T002–T010, con T004b, T007b y T009b), agrupadas por módulo, más el inicio (T001), el cierre (T011) y las humanas (H1–H8). Si una tarea supera 40 min al ejecutarla, se parte; no se recorta alcance por el presupuesto (Sp2-18 a Sp2-20 suman 300 min: es una advertencia, no un límite).
- **TDD dentro de cada tarea**:
  1. escribir las pruebas;
  2. ejecutarlas y ver el **rojo por la razón esperada** (anotarlo en la evidencia);
  3. implementar lo mínimo;
  4. pasar `ruff format --check .`, `ruff check .`, `mypy src tests` y las pruebas del módulo con cobertura (100 % de líneas y ramas del módulo nuevo).
- **Formato**: `- [ ] Tnnn [USn] descripción con ruta`.
  - US1: el bloque se guarda aparte y llega íntegro al modelo en cada llamada (FR-001 a FR-004, FR-021, FR-022; AC-01).
  - US2: la compactación no lo toca y sigue idéntico (FR-005, FR-006, FR-014; AC-01).
  - US3: los criterios se leen de su fuente protegida (FR-008 a FR-011; AC-02).
  - US4: tras compactar el agente sigue sabiendo el objetivo y las reglas (AC-03).
  - US5: cambios a mitad de tarea, tamaño y presupuesto (FR-007, FR-012, FR-013, FR-015 a FR-020).
- **Decisiones añadidas al plan** (research R15 a R20):
  1. (R15) **Sin tarea** y **con tarea sin elementos** no son lo mismo. Sin tarea la composición no crea renovador: no hay bloque y el contexto es el de hoy. Con tarea el renovador existe y **exige** `objetivo`, `criterios_ref` y al menos una `instrucciones`; si falta alguno (el segundo guardado falló, alguien borró filas, la base se alteró) **falla cerrado**, nunca se trata como sesión sin tarea. `RenewalOutcome` no tiene `NONE`.
  2. (R16) Los mensajes fijos nombran el **elemento** y el **tope** (en caracteres o en tokens) y nunca su contenido; tres textos exactos (ver abajo).
  3. (R17) Un fallo del segundo guardado tras `start_task` **no** deja una composición usable: `compose` ya cierra el almacén y relanza ante cualquier fallo de arranque, y eso se conserva.
  4. (R18) El movimiento en `compose()` (prefijo antes de abrir el almacén) se hace primero **solo** como refactor y se comprueban siete archivos de pruebas de arranque sin tocarlos.
  5. (R19) Orden de creación: `check_block` y `check_creation` nacen en T003 (necesitan `render_block`), no en T002; el renovador usa `find_blocks` y `block_message` creados en T004.
  6. (R20) Las 14 pruebas existentes: las 13 de esquema y de tablas se ajustan en T005 (tarea del esquema 4); la 14.ª (la API pública de `adapters/storage`) en T006, porque su nombre solo se exporta cuando existe el adaptador.
- **Mensajes fijos** (exactos, sin comillas inglesas):
  - tope de un elemento o del bloque: `El elemento «<elemento>» del contexto esencial supera el tope de <N> <caracteres|tokens>.` con `<elemento>` ∈ {`objetivo`, `reglas`, `ticket`, `criterios`, `bloque completo`}; ejemplos: `…«objetivo»… 8000 caracteres.` y `…«bloque completo»… 5120 tokens.`;
  - lectura: `No se pudo leer el contexto esencial de la tarea; la petición no se envía.`;
  - faltan elementos: `Faltan elementos del contexto esencial de la tarea; la petición no se envía.`
- **Lo que no se toca** (diff vacío al cerrar): `src/harness_agent/core/loop.py`, `core/interfaces/`, `core/events.py`, `core/in_memory_event_bus.py`, `core/redaction.py`, `core/permissions/`, `core/tasks/`, `core/verification/`, `core/context/cut.py`, `core/context/compactor.py`, `adapters/tools/`, `adapters/storage/task_store.py`, `cli/`, `tests/doubles/` y `docs/archivo/`. Si algo obliga a tocar uno de ellos: **detente y avisa** con la razón.
- **Pruebas existentes que cambian** (y solo estas 14; ejecutarlas **antes, sin tocar**, y ver que fallan por la versión o por la tabla nueva; solo entonces ajustar las líneas declaradas y registrarlas como «autorizado por el usuario, pendiente de ratificar»):

  | # | Prueba | Línea | Ajuste | Tarea |
  |---|---|---|---|---|
  | 1 | `tests/unit/adapters/storage/test_schema.py::test_schema_version_is_current` | 46 | `SCHEMA_VERSION == 3` → `== 4` | T005 |
  | 2 | `tests/unit/adapters/storage/test_schema_migration.py::test_schema_version_is_two` | 84 | `== 3` → `== 4` | T005 |
  | 3 | `…/test_schema_migration.py::test_new_database_gets_the_criteria_tables` | 90 | `user_version == 3` → `== 4` | T005 |
  | 4 | `…/test_schema_migration.py::test_version_one_database_migrates_without_losing_data` | 124 | `user_version == 3` → `== 4` | T005 |
  | 5 | `…/test_schema_migration.py::test_unknown_versions_are_still_refused` | 158 | `PRAGMA user_version = 4` → `= 5` | T005 |
  | 6 | `tests/unit/adapters/storage/test_schema_v3.py::test_the_version_is_three` | 140 | `SCHEMA_VERSION == 3` → `== 4` | T005 |
  | 7–8 | `…/test_schema_v3.py::test_an_old_database_migrates_to_three_and_keeps_every_row[1]` y `[2]` | 153 y 154–158 | `user_version == 3` → `== 4` y una aserción `after.pop("contexto_esencial") == []` junto a la de `resumenes` | T005 |
  | 9–10 | `…/test_schema_v3.py::test_reopening_a_migrated_database_changes_nothing[1]` y `[2]` | 171 | `user_version == 3` → `== 4` | T005 |
  | 11–12 | `…/test_schema_v3.py::test_a_migrated_database_has_the_same_table_as_a_new_one[1]` y `[2]` | 184 | `user_version == 3` → `== 4` | T005 |
  | 13 | `tests/integration/test_rejection_reason_agent_loop.py::test_the_reason_is_not_stored_in_the_database` | 295 | el conjunto de tablas gana `"contexto_esencial"` | T005 |
  | 14 | `tests/unit/adapters/storage/test_public_api.py::test_all_lists_exactly_the_public_names` | 7–26 (`EXPECTED`) | gana `"SqliteEssentialStore"` | T006 |

  - **Revisadas y sin cambio esperado** (se ejecutan sin tocar; si una falla, es un hallazgo): `history_prefix` (FR-022), el recorte `[2:]` de `test_bootstrap_main.py`, los suscriptores del registrador, `core.__all__`, y las sesiones con tarea que pasan por el ejecutor (`test_bootstrap_verification.py`, `test_criteria_verification_agent_loop.py`).
  - **Cualquier otra prueba existente que falle: detente y avisa con la razón antes de ajustarla.** En particular, si alguna de las siete de arranque de T007 falla por el movimiento de `compose()`.
- **Caracteres ocultos**: en `specs/` y `docs/` escribe `U+202E` y `U+200B` como texto. En código y pruebas se construyen con `chr(0x202E)`, `chr(0x200B)` y `chr(27)`, nunca con secuencias `\u...` en el texto que escribe la herramienta.
- **Finales de línea**: todo archivo de `specs/` y `docs/` en CRLF, con scripts que lean y escriban bytes; nunca `sed -i`. Rutas siempre relativas al repositorio.
- **Secretos**: ninguna asignación con forma de clave ni URL con credenciales literales; se arman por partes (`"https://" + "usuario" + ":" + "clave" + "@servidor.example/repo.git"`). Detector a mano sobre todos los archivos nuevos y modificados.
- **Sin red**: todo con `FakeProvider` (o un proveedor de prueba local en el archivo cuando haga falta responder según el contexto recibido); las bases de datos son archivos en `tmp_path`.
- **Ventanas de prueba**: el 20 % del umbral por defecto son 5 120 tokens; con la ventana mínima de 1 000 y el 45 % (umbral 450) el tope del bloque baja a 90 tokens y un bloque como E1 (115) **no cabe**. Las pruebas que necesitan un bloque que quepa usan una ventana mayor (por ejemplo 4 000 tokens al 50 %: umbral 2 000, tope del bloque 400).

## Mapeo a tareas del sprint

| Tarea | Descripción (03-plan-sprints) | Presupuesto | Tareas aquí |
|---|---|---|---|
| **Sp2-18** | Tabla `contexto_esencial` fuera de los eventos con el objetivo, las instrucciones, las reglas y el ticket | 120 min | T002 (40), T005 (30), T006 (35) |
| **Sp2-19** | Inyectar el bloque en el prefijo en cada ensamblado y excluirlo de lo resumible | 90 min | T003 (35), T004 (40), T004b (35), T007 (40), T007b (35) |
| **Sp2-20** | Prueba de una compactación con el proveedor simulado | 90 min | T008 (40), T009 (40), T009b (35) |
| — | Inicio, guardas/documentación y cierre | — | T001 (15), T010 (30), T011 (30) |

**Total de Claude: 480 min** (T001 15 + T002 40 + T003 35 + T004 40 + T004b 35 + T005 30 + T006 35 + T007 40 + T007b 35 + T008 40 + T009 40 + T009b 35 + T010 30 + T011 30) frente a 300 min presupuestados en Sp2-18 a Sp2-20. **Humanas: H1–H8.**

---

## Phase 1: Inicio

- [x] T001 Inicio (15 min). Sin cambios de código:
  - **Línea base**: ejecutar las cuatro puertas y las guardas tal como están (`ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest --cov=harness_agent --cov-report=term-missing -q -rs` y `pytest tests/architecture -q`), todas en exit 0; anotar los conteos reales (pruebas pasadas y omitidas, archivos de `ruff` y `mypy`, pruebas de arquitectura) en la evidencia al final de este archivo.
  - Ejecutar **sin tocar** las 14 pruebas de la lista de arriba con el esquema 3 vigente: deben pasar (es la línea base de lo que luego cambia).
  - `docs/PROGRESO.md` (solo documentación; CRLF puro; un script que lea y escriba bytes y conserve los CRLF, derivado del que se usó para HU-02-03 cambiando el prefijo por `| [HU-02-06.1](04b-historias-estado.md#hu-02-06.1) |` y la cabecera por `**Observaciones de HU-02-06.1**:`): la fila **existente** de HU-02-06.1 pasa de `Pendiente` a `En curso` (responsable B; la implementa Claude en `gustavo`; `specs/031-essential-context-block/`), una línea en *Registro de cambios* y un bloque **Observaciones de HU-02-06.1** con dos viñetas (alcance y decisiones Q1 = A y Q2 = A; y la decisión conservadora de las sesiones sin tarea). No se toca ninguna otra fila ni la tabla *Resumen*.
  - Comprobar que `.specify/feature.json` apunta a `specs/031-essential-context-block`.

  **Hecho cuando**: la línea base está anotada y en verde, las 14 pruebas pasan sin tocar, la fila está en `En curso` y `PROGRESO.md` sigue en CRLF puro con una sola fila existente modificada.

---

## Phase 2: El texto del bloque (US1, US3, US5 · Sp2-18, Sp2-19)

- [x] T002 [US1] [US5] Elementos, limpieza, topes por elemento y errores (40 min). Cubre FR-001, FR-002, FR-013 (por elemento), FR-016 (mensajes fijos) y SC-006, SC-007 (parte). Archivos:
  - `src/harness_agent/core/context/errors.py`: `EssentialContextError(ValueError)`, `EssentialContextTooLarge(element, limit, unit)` y `EssentialContextUnavailable(missing: bool)`, con los **mensajes fijos exactos** de arriba (el de tope usa el elemento, el número y la unidad; el de lectura y el de «faltan elementos» son textos constantes; ninguno recibe ni repite un valor);
  - nuevo `src/harness_agent/core/context/essential.py` (parte 1): constantes `KEY_OBJECTIVE`, `KEY_RULES`, `KEY_TICKET`, `KEY_CRITERIA_REF`, `KEY_INSTRUCTIONS`, `MARK`, `MAX_ELEMENT_CHARS = 8_000`, `MAX_BLOCK_SHARE_PERCENT = 20`; `EssentialItem` (`@dataclass(frozen=True)`: `key`, `order`, `value`, `origin`; valida clave conocida, `order ≥ 1`, valor y origen no vacíos); `make_items(*, ticket, objective, rules, instructions) -> tuple[EssentialItem, ...]` (limpia con `clean_summary`: caracteres ocultos fuera y credenciales de URL ocultas con `core/redaction.py`; el ticket en una línea; omite el ticket y las reglas ausentes o vacías; comprueba `MAX_ELEMENT_CHARS` sobre el valor **limpio** y nunca trunca; `instructions: Sequence[tuple[str, str]]` = (origen, texto) → una fila por mensaje con el texto **exacto**, sin limpiar y sin tope; exige objetivo y al menos una instrucción) y `criteria_reference(session_id) -> EssentialItem` (`criterios_ref`, orden 1, el identificador de la sesión como valor y `criterios protegidos (HU-11-01)` como origen);
  - exportaciones en `core/context/__init__.py` y `core/__init__.py`.

  Pruebas primero, `tests/unit/core/context/test_essential_items.py`:
  - constantes (la marca exacta de 31 caracteres, 8 000 y 20) y las cinco claves;
  - `EssentialItem`: clave desconocida, orden 0, valor o origen vacíos o en blanco → `EssentialContextError`;
  - `make_items`: ticket con saltos y espacios → una línea; objetivo con `chr(0x200B)`, `chr(0x202E)` y `chr(27)` sale limpio; una credencial de URL armada por partes sale con `<secreto oculto>` y la clave **no** está en ningún valor; ticket y reglas ausentes o solo espacios → sin fila; las instrucciones se guardan idénticas (con espacios finales incluidos), en orden 1, 2, 3 y con su origen; sin objetivo o sin instrucciones → error; `criteria_reference("s1")`;
  - topes: un valor de exactamente 8 000 caracteres se acepta, de 8 001 → `EssentialContextTooLarge` para `objetivo`, `reglas` y `ticket` (cada uno con su nombre); el tope se mide **después de limpiar** (8 004 caracteres con 4 ocultos se acepta); el valor se mide una sola vez y **nunca se trunca**;
  - **mensajes** (centinela `VALOR-DE-PRUEBA-123` en el valor excedido): `str(error)` es exactamente `El elemento «objetivo» del contexto esencial supera el tope de 8000 caracteres.` (y los de `reglas` y `ticket`), sin el centinela ni parte del valor; `EssentialContextUnavailable(missing=False)` y `(missing=True)` dan los otros dos textos exactos;
  - las excepciones llevan `element`, `limit` y `unit` como atributos y ningún contenido.

  **Rojo esperado**: `ImportError` de los símbolos nuevos de `harness_agent.core.context.essential`. **Hecho cuando**: `essential.py` (parte 1) y `errors.py` al 100 % de líneas y ramas; `core/loop.py` y `core/interfaces/` sin diff.

- [x] T003 [US1] [US3] [US5] El texto del bloque y su validación de tamaño (35 min). Cubre FR-003, FR-009, FR-011, FR-013 (bloque), FR-015, FR-021 y SC-006, SC-008 (parte). Archivos:
  - `src/harness_agent/core/context/essential.py` (parte 2): `render_block(items, criteria) -> str` con el formato de `contracts/block_format.md` (cabecera fija, orden Ticket, Objetivo, Reglas, Criterios, una línea en blanco entre secciones, sin encabezados vacíos, sin salto final, criterios numerados con `pendiente` o `cumplido` y descripción limpia en una línea con credenciales ocultas, sin comando, condición ni evidencia; ignora la clave `instrucciones`; el resultado no depende del orden de `items`); `block_fits(text, settings, model) -> bool` y `check_block(items, criteria, settings, model) -> str` (arma el texto, lanza `EssentialContextTooLarge("criterios", 8000, "caracteres")` si la sección de criterios mide más de 8 000 caracteres y `EssentialContextTooLarge("bloque completo", <límite>, "tokens")` si el mensaje supera `threshold_tokens × 20 // 100`; devuelve el texto) y `check_creation(items, criteria_descriptions, settings, model) -> str` (arma los criterios **pendientes** de las descripciones de la definición y llama a `check_block`; se usa antes de abrir el almacén); `instruction_messages(items) -> list[Message]` (los `SYSTEM` de la clave `instrucciones`, en orden de `order`);
  - exportaciones en `core/context/__init__.py` y `core/__init__.py`.

  Pruebas primero, `tests/unit/core/context/test_essential_block.py`:
  - los ejemplos **E1 a E6** de `block_format.md` **carácter a carácter** (E1: 444 caracteres y 115 tokens; E2: 443; E3: 254 y 68; E4 sin criterios; E5 con `chr(0x200B)`; E6 con la credencial por partes), el orden fijo aunque se barajen los `items`, y que dos llamadas dan el mismo texto;
  - ningún texto de `instrucciones` aparece en el bloque; un `TaskCriteriaItem` con comando y evidencia centinela **no** los deja salir; el estado sale de `passes`; la numeración sigue el orden de la fuente;
  - **E7** de tamaño: con la ventana por defecto un bloque de 20 464 caracteres cabe y de 20 465 lanza `EssentialContextTooLarge` con `str(error)` exacto `El elemento «bloque completo» del contexto esencial supera el tope de 5120 tokens.`; con ventana 1 000 y 45 % el tope es 90 tokens y E1 (115) no cabe (`…tope de 90 tokens.`); una sección de criterios de 8 001 caracteres → `«criterios»… 8000 caracteres.`; centinela en el contenido excedido ausente del mensaje;
  - `check_creation`: con descripciones pendientes arma y valida; coincide con `check_block` sobre los mismos datos;
  - `instruction_messages`: devuelve los `SYSTEM` en orden y con el texto exacto (igual, uno a uno, al de una lista de mensajes de prueba que hace de prefijo): la **reconstrucción** de FR-015.

  **Rojo esperado**: `ImportError` de `render_block`, `check_block`, `check_creation`, `block_fits` e `instruction_messages`. **Hecho cuando**: `essential.py` al 100 %; los ejemplos del contrato coinciden carácter a carácter (si uno no se pudiera cumplir tal como está escrito, detente y dime cuál y por qué); `core/redaction.py` sin diff.

---

## Phase 3: El renovador (US1, US2, US3, US5 · Sp2-19)

- [x] T004 [US1] [US2] El renovador: localizar, insertar y sustituir el bloque (40 min). Cubre FR-003, FR-004, FR-005, FR-008, FR-012 (sustitución), FR-017 y SC-001, SC-002 (parte). Archivos:
  - `src/harness_agent/core/context/essential.py` (parte 3): `find_blocks(history) -> list[int]` (solo mensajes `SYSTEM` del prefijo `SYSTEM` contiguo del principio cuyo contenido es exactamente `MARK` o empieza por `MARK` y un salto de línea) y `block_message(text) -> Message`;
  - nuevo `src/harness_agent/core/context/renewer.py`: protocolos de solo lectura `EssentialSource` (`items(session_id)`) y `CriteriaReader` (`load_criteria(session_id)`), `RenewalOutcome` (`INSERTED`, `REPLACED`, `UNCHANGED`) y `EssentialRenewer(source, criteria, settings, *, session_id, model)` con `renew(history: list[Message]) -> RenewalOutcome` **síncrono**: lee los elementos, lee los criterios con la **referencia guardada** (`criterios_ref`), arma el texto con `check_block`, y inserta en la posición `len(prefijo SYSTEM)`, sustituye in situ, no toca nada si el texto es idéntico (mismo objeto) y borra los bloques sobrantes; **en esta tarea todavía no se manejan los fallos** (lo hace T004b con sus pruebas en rojo primero);
  - exportaciones en `core/context/__init__.py` y `core/__init__.py`.

  Pruebas primero, `tests/unit/core/context/test_essential_renewer.py` (falsos de los dos protocolos en el archivo; `FakeProvider` no hace falta):
  - `find_blocks` con la tabla de **imitaciones** de `block_marker.md`: la marca en `USER` (no externo), `USER` externo, `TOOL`, `ASSISTANT`, un `SYSTEM` con la marca en medio del texto, un `SYSTEM` con la marca tras un `USER` y un objetivo que contiene la marca: solo el `SYSTEM` real del prefijo es el bloque;
  - ejemplos **E1 a E6** de `block_marker.md`: inserción tras 2 provisionales (posición 2) y tras 3 (posición 3), sustitución en el mismo índice con longitud y demás objetos intactos, idempotencia (`UNCHANGED` y `history[2] is` el mismo objeto), duplicado (queda uno), historial vacío (inserta en 0), imitación (solo cambia la posición del bloque real);
  - el lector recibe la **referencia guardada** (`criterios_ref` con un valor distinto del identificador de sesión) y no el identificador que tiene el renovador; la lista se modifica **in situ** (misma lista); no se publica ningún evento (un bus de prueba sin llamadas); el texto insertado es el de `check_block`.

  **Rojo esperado**: `ImportError` de `harness_agent.core.context.renewer`. **Hecho cuando**: lo anterior en verde; `core/interfaces/`, `core/loop.py` y `core/context/{cut,compactor}.py` sin diff.

- [x] T004b [US3] [US5] El renovador: falla cerrada, elementos obligatorios y azar de semilla fija (35 min). Cubre FR-010, FR-011, FR-013 (bloque, por modelo), FR-016, decisión R15 y SC-005, SC-006. Archivos: `src/harness_agent/core/context/renewer.py` (se completa) y las pruebas `tests/unit/core/context/test_essential_renewer_failures.py` y `tests/unit/core/context/test_essential_renewer_properties.py` (nuevos). Implementación, **después** de ver las pruebas en rojo: elementos obligatorios `objetivo`, `criterios_ref` y al menos una `instrucciones` (si falta alguno → `EssentialContextUnavailable(missing=True)`, también con la lista vacía: **con tarea y sin elementos nunca es una sesión sin tarea**); cualquier `Exception` de la fuente o del lector → `EssentialContextUnavailable(missing=False)` **sin** causa (`from None`) y sin su texto; el tope del bloque con el umbral del modelo que devuelve `model()` **en cada llamada**; solo `except Exception` (nunca `BaseException` ni `CancelledError`); el historial no cambia si algo falla.

  Pruebas primero:
  - la fuente lanza (`RuntimeError` con centinela) → error de lectura exacto, historial intacto, `__cause__` nulo y sin centinela en `str` ni en `args`; el lector lanza (incluido un error con el nombre de uno de integridad de criterios) → igual;
  - **con tarea sin elementos**: fuente vacía → `Faltan elementos del contexto esencial de la tarea; la petición no se envía.`; y cada elemento obligatorio ausente por separado (objetivo, `criterios_ref`, instrucciones) → el mismo error; historial intacto en todos;
  - bloque que no cabe: `«bloque completo»` con el límite en tokens, y sección de criterios de más de 8 000 caracteres → `«criterios»`, textos exactos y con centinelas en los valores **ausentes** de los mensajes; **cambio de modelo**: `model()` devuelve un modelo de ventana grande (cabe) y luego uno de ventana pequeña (no cabe) y el tope se recalcula en la segunda llamada;
  - la cancelación (`asyncio.CancelledError`) y `KeyboardInterrupt` lanzados por el lector se propagan sin captura;
  - **azar** (`random.Random(20261031)`, 2 000 historiales): prefijo `SYSTEM` de 0 a 4 mensajes, de 0 a 2 bloques previos (iguales o viejos) y el resto de roles al azar, con imitaciones de la marca en `USER`, `TOOL` y `ASSISTANT`; tras `renew`: **exactamente un** bloque en el prefijo, el resto de objetos en el mismo orden y los mismos objetos, la posición del primer bloque previo se conserva (o es `len(prefijo)` si no había), una segunda llamada devuelve `UNCHANGED` y el texto es el de `check_block`.

  **Rojo esperado**: los fallos se propagan crudos o no se valida ningún elemento. **Hecho cuando**: `renewer.py` y `essential.py` al 100 % (líneas y ramas); `core/redaction.py` y `core/verification/` sin diff.

---

## Phase 4: El esquema 4 y el adaptador (US1, US5 · Sp2-18)

- [x] T005 [US5] Esquema 4 y migración desde 1, 2 y 3 (30 min). Cubre FR-018, FR-020 (13 de las 14 pruebas) y SC-011. Archivos:
  - `src/harness_agent/adapters/storage/_schema.py`: `SCHEMA_VERSION = 4` y `_V4` con **solo** la tabla `contexto_esencial` de `data-model.md` (`_STEPS = {1: _V1, 2: _V2, 3: _V3, 4: _V4}`); `events`, `resumenes` y `criterios*` no se tocan; el docstring del módulo menciona la versión 4;
  - **ajustes declarados** de las pruebas 1 a 13 de la lista de arriba, **solo después** de ejecutarlas sin tocar y ver el rojo.

  Pruebas primero, nuevo `tests/unit/adapters/storage/test_schema_v4.py` (el SQL literal de las versiones 1, 2 y 3 escrito en el archivo, como en `test_schema_v3.py`):
  - bases **reales en `tmp_path`** creadas con el esquema anterior (versiones 1, 2 y 3) con datos (sesiones, eventos con y sin `compacted_by`, criterios con sello y un resumen en la 3) → al abrirlas con `SqliteSessionStore` pasan a la versión 4, `contexto_esencial` existe vacía y **todas las filas de todas las tablas anteriores son idénticas** (volcado comparado; en la 1 las tablas `criterios*` y `resumenes` llegan vacías por el camino); reabrir no cambia nada; una base nueva tiene la misma definición de `contexto_esencial` que una migrada;
  - restricciones: `orden ≥ 1`, `clave`, `valor` y `origen` no vacíos ni en blanco, clave foránea de `sesion_id`, clave primaria `(sesion_id, clave, orden)`; no hay `CHECK` sobre el conjunto de claves (HU-02-06.2 añadirá `decisiones`);
  - **antes de implementar**: ejecutar `pytest tests/unit/adapters/storage tests/integration/test_rejection_reason_agent_loop.py` con la versión 4 puesta **sin tocar** las 13 pruebas: deben fallar **exactamente** esas 13 (las de los números 1 a 13) y por la versión o la tabla nueva; si falla otra, **detente y avisa**.

  **Rojo esperado**: `contexto_esencial` no existe y `SCHEMA_VERSION == 4` falla; después, las 13 pruebas existentes fallan por la versión o la tabla. **Hecho cuando**: toda la suite de `adapters/storage` y `test_rejection_reason_agent_loop.py` en verde; ninguna otra prueba existente cambió; `core/interfaces/` sin diff.

- [x] T006 [US1] [US5] `SqliteEssentialStore` (35 min). Cubre FR-001, FR-015, FR-016 (el adaptador no revela valores), FR-020 (la prueba 14) y SC-007 (parte). Archivos:
  - nuevo `src/harness_agent/adapters/storage/essential_store.py`: `SqliteEssentialStore(store: SqliteSessionStore, *, clock=…)` con `save_items(session_id, items)` (una transacción `BEGIN IMMEDIATE` … `COMMIT`; escritura **única**; sin actualizar ni borrar) e `items(session_id) -> list[EssentialItem]` (ordenados por clave y orden), sobre `store.connection()` y **sin** abrir otra conexión; errores del motor → `SessionStoreError` con mensaje fijo sin valores; cumple `EssentialSource`;
  - `src/harness_agent/adapters/storage/__init__.py`: exportar `SqliteEssentialStore`;
  - **ajuste declarado** de la prueba 14 (`test_public_api.py::test_all_lists_exactly_the_public_names`, el nombre nuevo en `EXPECTED`), **solo después** de ejecutarla sin tocar y verla fallar por el nombre nuevo.

  Pruebas primero, nuevo `tests/unit/adapters/storage/test_essential_store.py`, con un **archivo real** en `tmp_path`:
  - **E1** de `essential_store.md`: 7 filas guardadas (4 del bloque y 3 instrucciones) y devueltas ordenadas; `creado` en UTC con el reloj inyectado; **escritura única**: guardar de nuevo la misma sesión → `SessionStoreError` y las 7 filas intactas;
  - **E2**: rollback con disparadores SQL (`RAISE(ABORT)`) en la tercera fila: ninguna fila nueva y fuera de transacción; **E3**: una sesión sin filas devuelve `[]`; sesión inexistente al guardar → `SessionStoreError`;
  - no toca `events`, `resumenes` ni `criterios*` (volcado antes y después); el error del motor no contiene valores (centinela); almacén cerrado → `SessionStoreError`;
  - **R17**: `sqlite3.connect` sustituido por una función que falla durante las operaciones del adaptador; `save_event` antes y después de guardar los elementos en la misma base sin bloqueos; una segunda conexión de lectura lee el resultado tras el `COMMIT`;
  - **reconstrucción** (FR-015): con `make_items` y un prefijo de prueba, `instruction_messages(store.items(...))` es igual, uno a uno, al prefijo y `render_block` sobre lo leído es igual al texto armado antes de guardar.

  **Rojo esperado**: `ImportError` de `SqliteEssentialStore`; después, `test_all_lists_exactly_the_public_names` falla por el nombre nuevo. **Hecho cuando**: `essential_store.py` al 100 %; `core/interfaces/` (`SessionStore`) y `adapters/storage/task_store.py` sin diff.

---

## Phase 5: El cableado (US1, US3, US5 · Sp2-19)

- [x] T007 [US1] [US5] `compose()`: validar antes de abrir, guardar tras `start_task` y fallar cerrado (40 min). Cubre FR-002, FR-013, FR-022, decisiones R15 (sin tarea frente a con tarea), R16, R17 y R18 y SC-006, SC-010. Archivos:
  - `src/harness_agent/bootstrap.py` (solo cableado; visto bueno de C en H2). **Paso 0 (refactor, sin comportamiento nuevo)**: construir el prefijo provisional **antes** de abrir el almacén, guardando para cada mensaje su **origen** (`entorno`, `git`, `comandos`); `Composition.history_prefix` queda **igual**. Después de este paso y **antes** de añadir nada, ejecutar **sin tocarlos** `tests/unit/test_bootstrap_compose.py`, `test_bootstrap_shell.py`, `test_bootstrap_main.py`, `test_bootstrap_git.py`, `test_bootstrap_verification.py`, `test_bootstrap_task_commands.py` y `test_bootstrap_compaction.py`: deben pasar; **si alguno falla por el movimiento, detente y avisa con la razón antes de ajustarlo**;
  - **Paso 1 (con tarea)**: antes de abrir nada, `make_items(…)` (ticket = `task.title`, objetivo = `task.objective`, reglas = `task.rules`, instrucciones = el prefijo con sus orígenes) y `check_creation(…)` con las descripciones de los criterios, el `config.context` y `config.model`; un `EssentialContextTooLarge` sale como `StartupError` con **el mensaje fijo** del error (que nombra el elemento y el tope). Tras `start_task`, `SqliteEssentialStore(store, …).save_items(session_id, (*items, criteria_reference(session_id)))` **dentro** del bloque que ya cierra el almacén y relanza ante cualquier fallo de arranque;
  - sin tarea: no se calcula ni se guarda nada (FR-002).

  Pruebas primero, nuevo `tests/unit/test_bootstrap_essential.py` (parte de composición; patrón de `test_bootstrap_compaction.py` y `bootstrap_support.py`):
  - con tarea: `contexto_esencial` tiene las 4 filas del bloque (según lo declarado) más una fila por provisional, con los **textos exactos** de `history_prefix` y sus orígenes; `history_prefix` es **idéntico** al de antes (longitud y contenido, con y sin comandos de la tarea; FR-022); una credencial de URL armada por partes en el objetivo se guarda **oculta**; sin título ni reglas no hay esas filas;
  - sin tarea: **cero** filas y el contexto es el de hoy;
  - **validación antes de abrir nada** (objetivo de 8 001 caracteres, reglas de 8 001, título de 8 001, una ventana tan pequeña que el bloque no cabe): `compose` lanza `StartupError` con el mensaje fijo exacto (`…«objetivo»… 8000 caracteres.`, `…«bloque completo»… <N> tokens.`), **no** se crea el archivo de la base y un centinela del valor no aparece en el mensaje;
  - **el guardado falla tras `start_task`** (se sustituye `SqliteEssentialStore.save_items` en `bootstrap` por una función que lanza `SessionStoreError`): `compose` **lanza**, el almacén queda **cerrado** (patrón `RecordingStore` de `test_bootstrap_compose.py`) y no se devuelve ninguna composición: nunca queda una sesión activa y usable ni se trata como sesión sin tarea; la fila de la sesión creada por `start_task` sigue en la base (riesgo conocido y documentado);
  - `compose` sin tarea y con tarea cierra el almacén si falla cualquier paso posterior (se mantiene).

  **Rojo esperado**: la tabla queda vacía y los límites no se validan (`StartupError` no se lanza); el paso 0 es verde. **Hecho cuando**: las siete pruebas de arranque pasan sin cambios; las pruebas nuevas en verde; `bootstrap.py` sin cobertura perdida; `tests/architecture/test_bootstrap_boundaries.py` en verde.

- [x] T007b [US1] [US3] [US5] `run_session` y las rondas: renovar antes de compactar y antes de cada ronda (35 min). Cubre FR-004, FR-012, FR-016 (el aviso), FR-017 y decisión R15 (código de salida 1). Archivos:
  - `src/harness_agent/bootstrap.py`: `Composition.essential: EssentialRenewer | None = None` (con valor por defecto; solo con tarea); `compose` construye el renovador (almacén de elementos, `task_store` como lector, `config.context`, `config.model`, el identificador de la sesión); `run_session` llama a `essential.renew(history)` **antes** de la compactación en cada petición; `_verifying_runner` recibe el renovador y lo llama **antes de cada llamada al bucle** en la función de la ronda (`VerifyingRunner` y `core/verification/` **no se tocan**); un ayudante único `renew-o-informar` que, ante un `EssentialContextError`, escribe su **mensaje fijo** por el `WarningSink` y **relanza** (la CLI lo muestra como línea con el tipo y sale con código 1, comportamiento existente); sin renovador (sin tarea) los dos puntos no hacen nada.

  Pruebas primero, `tests/unit/test_bootstrap_essential.py` (parte de renovación):
  - con tarea `Composition.essential` es un `EssentialRenewer` y sin tarea es `None`; `history_prefix` igual que antes;
  - en `run_session` el orden es **renovar → compactar → ejecutar**: un compactador de prueba (`replace(composition, compactor=…)`) comprueba que, cuando lo llaman, el historial **ya lleva** el bloque; la primera petición recibida por el proveedor tiene el bloque en la posición `len(history_prefix)` y la petición de la persona justo después;
  - **entre rondas**: con `composition.runner.run("trabaja", list(composition.history_prefix))` y un criterio que el verificador marca como cumplido tras la ronda 1, el bloque de la ronda 1 dice `pendiente`, el de la ronda 2 dice `cumplido`, y en cada petición del proveedor hay **un solo** bloque;
  - **falla cerrada con tarea**: con el renovador sustituido por uno que lanza `EssentialContextUnavailable`, `run_session` escribe el **mensaje fijo exacto** en su salida, devuelve **1** y el proveedor **no recibe ninguna llamada**; lo mismo con `EssentialContextTooLarge`; **sin tarea** el mismo historial sigue sin renovador y la petición se envía (la diferencia de R15);
  - ningún evento nuevo (suscripción a todos los tipos: solo los que ya existían).

  **Rojo esperado**: `AttributeError` de `Composition.essential` y el bloque no aparece en lo que recibe el proveedor. **Hecho cuando**: lo anterior en verde; `bootstrap.py` al 100 %; `core/verification/` y `core/loop.py` sin diff; las siete pruebas de arranque de T007 siguen en verde.

---

## Phase 6: La sesión simulada de punta a punta (US1–US5 · Sp2-20)

- [x] T008 [US1] [US2] [US3] [US4] Sesión larga con el bucle real: AC-01, AC-02, AC-03, cambios a mitad de tarea y presupuesto (40 min). Cubre AC-01, AC-02, AC-03, FR-003, FR-004, FR-005, FR-008, FR-012, FR-014, FR-019, FR-021, SC-001, SC-002, SC-004, SC-008, SC-009. Archivo nuevo `tests/integration/test_essential_context_agent_loop.py` (`compose(task=…)` real con SQLite en `tmp_path`, `run_session` con entradas en `io.StringIO`, `FakeProvider` con guion exacto y, solo para AC-03, un proveedor de prueba **local al archivo** que responde según el contexto recibido; el generador de la sesión larga —mensajes con **cinco centinelas** distintos: objetivo, reglas, ticket, un criterio y una instrucción (el texto de un comando de la tarea)— se escribe dentro del archivo, con llamadas a `listar_archivos` y respuestas con y sin texto):
  - **AC-01**: en **cada** llamada al modelo que no es de resumen, el contexto lleva el bloque **exactamente una vez**, con los cuatro elementos completos, en la posición `len(history_prefix)` y **idéntico byte a byte** entre llamadas, y tras **dos compactaciones** seguidas (las posiciones de las llamadas de resumen se afirman en la prueba); el texto de cada instrucción aparece **exactamente una vez** (como su mensaje) y el registro del almacén no aparece en ninguna llamada;
  - **AC-02**: tras compactar, los mensajes provisionales siguen idénticos; los criterios se leen de su fuente: se marca un criterio con `composition.task_store.mark_passes` entre dos peticiones y la siguiente petición lo muestra `cumplido`; un resumen simulado que lleva una copia **vieja** del criterio (`pendiente`) no gana al bloque;
  - **AC-03**: tras dos compactaciones con un resumen que **pierde** el objetivo, el proveedor local, al preguntarle por el objetivo, responde el centinela porque el contexto lo lleva; lo mismo para las reglas y el ticket;
  - **cambios a mitad de tarea**: un criterio que el verificador marca tras una ronda cambia el bloque en la ronda siguiente, nunca hay dos bloques y el texto viejo no queda en el historial;
  - **presupuesto** (ejemplo E4 de `context_order.md`): con una ventana y un umbral calculados a mano, el mismo historial **sin** el bloque no compacta y **con** él sí, y la diferencia de estimaciones es el tamaño estimado del bloque;
  - posición: el bloque está antes de la petición inicial y del resumen en toda llamada (orden de `context_order.md`).

  **Rojo esperado**: retirando temporalmente el cableado de `bootstrap.py` (copia de seguridad y restauración del archivo, **sin** `git stash`) las pruebas fallan porque el bloque no aparece; anota el número de fallos. **Hecho cuando**: todo en verde; `git stash list` conserva solo el `stash@{0}` de la spec 017; ninguna petición hace más de una llamada de resumen.

- [x] T009 [US3] [US5] Falla cerrada: sin tarea frente a con tarea sin elementos, no cabe y fuente alterada (40 min). Cubre FR-002, FR-010, FR-011, FR-013, FR-016 (avisos), decisión R15 y SC-005, SC-006, SC-010. Se añade a `tests/integration/test_essential_context_agent_loop.py`:
  - **sin tarea**: la sesión recibe exactamente el contexto de hoy (los provisionales, la petición y sus respuestas), 0 filas en `contexto_esencial`, ningún bloque, y `Composition.essential` es `None`;
  - **con tarea y elementos borrados**: se borran **todas** las filas de la sesión en `contexto_esencial` con una tarea activa y se lanza una petición por `run_session`: el proveedor **no** recibe ninguna llamada, la salida lleva `Faltan elementos del contexto esencial de la tarea; la petición no se envía.` y el código de salida es **1**; **nunca** se trata como sesión sin tarea; lo mismo borrando solo `objetivo`, solo `criterios_ref` y solo las instrucciones;
  - **guardado que falla tras `start_task`** con un disparador SQL real (`RAISE(ABORT)` sobre la inserción en `contexto_esencial`, creado antes de `compose` en una base preparada): `compose` lanza, el almacén queda cerrado y no hay composición usable;
  - **fuente de criterios alterada** (se cambia la huella del sello o una fila de `criterios` con SQL directo): la petición no llega al modelo (0 llamadas), la salida lleva `No se pudo leer el contexto esencial de la tarea; la petición no se envía.`, el código es 1, **no** se usa un bloque viejo ni criterios del historial, y el evento que ya existía (`criteria_tampered`, solo el motivo) se publica **una sola vez**; ningún otro evento nuevo;
  - **no cabe**: con una ventana pequeña `compose` lanza `StartupError` con `…«bloque completo»… tokens.`; un objetivo de 8 001 caracteres → `…«objetivo»… 8000 caracteres.`; los mensajes **no** contienen el centinela del valor;
  - **sin criterios legibles**: una lista vacía de criterios del lector con `criterios_ref` presente (renovador montado a mano con un lector falso) da un bloque sin sección de criterios y sin encabezados vacíos.

  **Rojo esperado**: sin el manejo de R15 y de la falla cerrada las peticiones llegan al modelo con un bloque viejo o sin bloque. **Hecho cuando**: todo en verde; los mensajes coinciden con los textos exactos de este archivo; ninguna prueba existente cambió.

- [x] T009b [US2] [US5] Seguridad: no filtración, la llamada de resumen real y el modelo no edita el almacén (35 min). Cubre FR-006, FR-007, FR-009, FR-016 y SC-003, SC-007. Archivo nuevo `tests/integration/test_essential_context_security.py` (mismo montaje que T008):
  - **no filtración**: con centinelas en los cinco elementos, en el historial y en el texto de una excepción inyectada, **0** apariciones en las filas de `events` (incluidos `provider_error`, `criteria_tampered` y `context_compacted`), en los mensajes de error y en los avisos de la salida; la credencial de URL del objetivo (armada por partes) está oculta en `contexto_esencial` y en el bloque enviado;
  - **la llamada de resumen real del compactador**: su entrada **no** contiene el bloque ni ninguno de sus valores ni el registro de las instrucciones (se inspecciona lo que graba el proveedor simulado en la llamada sin herramientas);
  - **el modelo no edita el bloque ni su almacén** con la política real de la composición: un guion del proveedor pide `escribir_archivo` sobre el archivo de la base y un `shell` que nombra la base y la tabla `contexto_esencial`; ambos se deniegan (`[permission_denied]`), las filas de la tabla no cambian y ninguna definición de herramienta (nombre, descripción o esquema) nombra la tabla;
  - **repetir la marca no sustituye al bloque**: una respuesta del modelo y el resultado de leer un archivo que contienen la marca; tras renovar sigue habiendo **un solo** bloque y su texto no cambió;
  - **criterios sin comando**: un criterio con comando y condición centinela nunca aparece en lo enviado al modelo (ni en el bloque ni en el aviso de verificación).

  **Rojo esperado**: ninguna de estas pruebas puede pasar sin el bloque; sin el cableado fallan por la ausencia del bloque, y una prueba mutada que filtra un valor la hace fallar. **Hecho cuando**: todo en verde; los 0 de SC-003 y SC-007 comprobados con centinelas únicos.

---

## Phase 7: Guardas, documentación y cierre

- [x] T010 Guardas de arquitectura y documentación (30 min). Archivos:
  - nuevo `tests/architecture/test_essential_boundaries.py` (autoprueba con fragmentos sintéticos y mutación sobre una copia en `tmp_path`; reutiliza los detectores de las guardas existentes, no los copia): `core/context/essential.py` y `renewer.py` solo stdlib y núcleo, sin E/S, sin entorno ni terminal (los detectores de `test_context_boundaries.py`), sin importar el bucle, `adapters`, `cli`, `core.permissions`, `core.tasks`, `core.verification` ni el puerto `TaskCriteria`; en `renewer.py` nunca se captura `BaseException`, un `except` desnudo ni `CancelledError`, y `renew` **no** es asíncrono ni tiene `await`; `adapters/storage/essential_store.py` no llama a `sqlite3.connect`, no importa `core.loop` y no define `SessionStore`; **solo la composición renueva**: en todo `src/` el nombre `EssentialRenewer` solo se importa o construye en `bootstrap.py` (y en las exportaciones) y las llamadas `.renew(` solo están en `bootstrap.py`; `core/loop.py`, `core/verification/` y `cli/` no lo nombran; los dos módulos nuevos no tienen ningún `async def`. Cada regla con su mutación;
  - skills (dos copias idénticas, `.claude/skills/` y `.agents/skills/`): fila nueva en `verificar-fronteras-hexagonales/SKILL.md`; `core/context/{essential,renewer}.py` y `adapters/storage/essential_store.py` en `estructura-carpetas-harness/references/arbol.md`;
  - `CLAUDE.md`: fila de HU-02-06.1 en «Qué existe hoy» y nota en las convenciones (el bloque se renueva en `run_session` antes de compactar y antes de cada ronda; es un `SYSTEM` tras los provisionales; solo con `compose(task=…)`; sin tarea no hay bloque; con tarea la falta de elementos falla cerrado; las instrucciones son los provisionales y su registro no se inyecta; esquema 4);
  - revisar contra el código la lista de comprobación de `capas-y-reglas.md` de `plan.md` y anotar cualquier «no» (script que conserve CRLF);
  - **detector de secretos** a mano sobre todos los archivos nuevos y modificados (script con `secret_patterns_in` de `tests/architecture/test_no_secrets_in_repo.py`) y **caracteres ocultos y CRLF** en `specs/031-essential-context-block/` y `docs/`.

  **Rojo esperado de la guarda**: la prueba de mutación (una copia de `renewer.py` con `except BaseException`, con un `async def`, o llamada desde `core/loop.py`; una copia del adaptador que llame a `sqlite3.connect`) la hace fallar. **Hecho cuando**: `pytest tests/architecture` en verde con la guarda nueva, las copias de las skills idénticas (`cmp`), el detector sin hallazgos y sin caracteres ocultos ni saltos de línea sueltos.

- [x] T011 Cierre (30 min). Depende de T010.
  - Ejecutar las cuatro puertas: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`, todas en exit 0; anotar los conteos reales respecto de la línea base de T001, el 100 % de líneas y ramas de `essential.py`, `renewer.py`, `errors.py`, `essential_store.py` y `bootstrap.py`, y `pytest tests/architecture`.
  - Comprobar `git diff --exit-code $(git merge-base HEAD origin/main) -- <lo que no se toca, de arriba>` → 0, y revisar a mano que las únicas pruebas existentes modificadas son las 14 de la lista de arriba.
  - Repetir el detector de secretos y la comprobación de caracteres ocultos y CRLF **después** de escribir `PROGRESO.md`.
  - En `docs/PROGRESO.md` (CRLF puro, **una fila** de HU-02-06.1 que pasa a **`En revisión`**, nunca `Hecha`; sin reescribir filas ajenas ni la tabla *Resumen*) con *Archivos* y *Evidencia* reales, una línea por tarea en *Registro de cambios* y, en la fila y en el bloque **Observaciones de HU-02-06.1**:
    1. el **paso 5 del flujo de HU-11-01 estaba sin hacer** y este bloque es la **primera vez que el modelo recibe la tarea**; solo es alcanzable por `compose(task=…)` (`main()` no carga tareas), como HU-11-04.1;
    2. para **A**: el **gancho único futuro en el bucle** resolvería la renovación del bloque y la compactación **dentro** de una tarea larga; **limitación conocida** mientras tanto; las decisiones Q1 = A y Q2 = A y R15 a R20;
    3. **topes**: 8 000 caracteres por elemento frente a los 20 000 por sección del analizador de tareas (una tarea válida puede no arrancar) y 20 % del umbral para el bloque, a revisar por el PO;
    4. los **criterios semánticos en espera** de validación humana se muestran como `pendiente` (el puerto de lectura no expone el tipo);
    5. el **identificador del ticket es el título** de la tarea (en un issue de GitHub, el título, no el número);
    6. el guardado **no es atómico con `start_task`** (una segunda transacción; un fallo deja una sesión huérfana en la base y `compose` falla y cierra el almacén) y la distinción sin tarea / con tarea sin elementos (falla cerrada);
    7. **base para HU-03-04**: el bloque y el registro de instrucciones se rearman desde el almacén sin el resumen; y para HU-02-06.2 (la misma tabla admitirá `decisiones`);
    8. las 14 pruebas existentes ajustadas («autorizado por el usuario, pendiente de ratificar»), la nota de proceso con los rojos observados y lo **pendiente** (H1–H8; SPK-03 con un modelo real no bloquea).
  - Marcar en este archivo solo T001–T011 (con T004b, T007b y T009b) con su evidencia (tabla al final), con un script que conserve los CRLF; H1–H8 quedan sin marcar.

  **Hecho cuando**: las cuatro puertas en verde, el diff de lo que no se toca vacío, el detector sin hallazgos, sin caracteres ocultos y `PROGRESO.md` en CRLF con una sola fila de HU-02-06.1 en `En revisión`.

---

## Phase 8: Tareas humanas (Claude no las marca)

- [ ] H1 **Acuerdo de A** sobre un único gancho futuro en `core/loop.py` antes de cada llamada al modelo (resolvería la renovación del bloque y la compactación dentro de una tarea larga) y **aviso a A** de que el paso 5 del flujo de HU-11-01 (inyectar el objetivo, las reglas y los criterios en el prefijo) estaba sin hacer y lo cubre esta historia. Cualquier cambio del bucle, de los puertos o del catálogo necesita el acuerdo de A, B y C.
- [ ] H2 **Visto bueno de B** al esquema 4 de `adapters/storage/` (tabla `contexto_esencial`, migración aditiva desde 1, 2 y 3); **visto bueno de C** al cableado en `bootstrap.py`.
- [ ] H3 **Revisión cruzada** por A o C (la historia es de B).
- [ ] H4 El **PO decide qué entra al bloque**: los cuatro elementos y que las instrucciones sean los mensajes provisionales sin repetirse, que los criterios se muestren sin comando, que el contexto libre de la tarea quede fuera, los **topes** (8 000 caracteres por elemento y 20 % del umbral; el analizador admite 20 000 por sección) y si las **sesiones sin tarea** deberían recibir también un bloque.
- [ ] H5 **Corrida de SPK-03 con un modelo real** cuando D-IA lo permita: comprobar AC-03 («¿cuál era el objetivo original?») y la calidad del resumen con el bloque presente (no bloquea esta historia).
- [ ] H6 **CI remota** en verde en `ubuntu-latest` y `windows-latest`, con push y PR confirmados por una persona.
- [ ] H7 **Avisos**: a **A** (HU-03-04) el bloque y el registro de instrucciones se rearman desde el almacén; a **B** (HU-02-06.2) las decisiones acumuladas se añadirán a la misma tabla; a **A y B** (HU-02-01) el bloque debería formar parte del prefijo del ensamblador cuando se integre.
- [ ] H8 **Aviso a A y C**: `main()` no carga tareas, así que el bloque solo se alcanza con `compose(task=…)`; en un issue de GitHub el identificador del ticket es el título (el número no se conserva).

---

## Dependencias y orden

```text
T001 ─▶ T002 ─▶ T003 ─▶ T004 ─▶ T004b ─▶ T005 ─▶ T006 ─▶ T007 ─▶ T007b ─▶ T008 ─▶ T009 ─▶ T009b ─▶ T010 ─▶ T011 ─▶ (H1–H8)
```

- Es una cadena porque cada tarea añade exportaciones a `core/context/__init__.py` y `core/__init__.py` y la siguiente usa lo anterior: T003 usa `EssentialItem` y los errores de T002; T004 usa `render_block` y `check_block` de T003; T004b completa el renovador de T004; T006 usa `EssentialItem` (T002) y el esquema de T005; T007 usa `make_items`, `check_creation` y `criteria_reference` (T002, T003) y el adaptador (T006); T007b usa el renovador (T004, T004b); T008 a T009b usan todo. T005 (esquema) no depende de T002–T004 y podría adelantarse, pero no compensa.
- **US1** (guardar y entregar íntegro): T002, T003, T004, T006, T007, T007b, T008. **US2** (la compactación no lo toca): T004, T008, T009b. **US3** (criterios desde su fuente): T003, T004b, T007b, T008, T009. **US4** (objetivo recordado): T008. **US5** (cambios, tamaño y presupuesto, seguridad): T002, T003, T004b, T005, T006, T007, T009, T009b.

## Estrategia de implementación

1. **MVP**: T001–T004b. El texto del bloque y el renovador ya arman, sustituyen y fallan de forma segura (probados con falsos).
2. **Incremento**: T005 y T006 (el almacén), T007 y T007b (el cableado) y T008 a T009b (de punta a punta y seguridad).
3. **Cierre**: T010 y T011. Después, H1–H8 son humanas y la historia no pasa a `Hecha` hasta completarlas y ratificar HU-00-01.

---

## Evidencia

Resultados reales (2026-10-27). Línea base de T001: 6754 pasadas y 47 omitidas, 510 pruebas de arquitectura, ruff y mypy limpios (372 archivos).

| Tarea | Rojo observado | Resultado |
|---|---|---|
| T001 | — (sin cambios) | Línea base anotada; las 14 pruebas pasan sin tocar; la fila pasa a `En curso` |
| T002 | `ImportError` de los símbolos nuevos | `essential.py` (parte 1) y `errors.py` al 100 % |
| T003 | `ImportError` de `block_fits` | Ejemplos E1-E7 carácter a carácter; al 100 % |
| T004 | `ImportError` de `EssentialRenewer` | Insertar, sustituir, idempotencia, imitación de la marca |
| T004b | Fallos crudos y sin elementos obligatorios (8 fallos) | `renewer.py` al 100 %; azar de semilla fija |
| T005 | Tabla y versión 4 inexistentes (22 fallos); luego las 13 pruebas existentes fallan **exactamente** | 13 ajustadas |
| T006 | `ImportError`; luego `test_all_lists_exactly_the_public_names` | La 14 ajustada; `essential_store.py` al 100 % |
| T007 | Paso 0 (movimiento del prefijo): las siete pruebas de arranque pasan sin tocar; luego 10 fallos esperados | Validar, guardar y fallar cerrado |
| T007b | `AttributeError` de `Composition.essential` (8 fallos) | Una prueba existente más falló (`test_a_tampered_database_runs_nothing`): detenido, ajuste autorizado |
| T008 | Con la renovación apagada fallan 7 de 9 | 9 pruebas; conversores OpenAI y Anthropic aceptan el bloque |
| T009 | Sin exigir los elementos obligatorios fallan 4 de 18 | 18 pruebas en el archivo de integración |
| T009b | Una mutación que deja salir el comando hace fallar 1 | 7 pruebas de seguridad |
| T010 | Cada regla falla sobre su copia mutada | 23 pruebas; copias de las skills idénticas (`cmp`) |
| T011 | — | `ruff format --check .` y `ruff check .` en exit 0; `mypy src tests` sin errores (387 archivos); `pytest --cov=harness_agent --cov-branch` en exit 0: 6956 pasadas y 47 omitidas; 533 de arquitectura; 100 % de líneas y ramas de `essential.py`, `renewer.py`, `errors.py`, `essential_store.py`, `_schema.py` y `bootstrap.py`; diff de lo protegido vacío; `grep NONE` solo en frases que dicen que `RenewalOutcome` ya no lo tiene |

Pruebas existentes modificadas, **autorizadas por el usuario y pendientes de ratificar**: las 14 de la lista (`test_schema.py`, `test_schema_migration.py`, `test_schema_v3.py`, `test_rejection_reason_agent_loop.py` y `test_public_api.py`) y, además, `tests/integration/test_criteria_verification_agent_loop.py::test_a_tampered_database_runs_nothing`: la alteración de la base ocurre ahora **después** de que sale la primera ronda, con las aserciones intactas. Razón: la falla cerrada nueva de la renovación (FR-010, SC-005, T009) intercepta la fuente alterada antes de la primera ronda.

Pendientes humanos: H1-H8, sin marcar.
